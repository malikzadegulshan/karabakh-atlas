#!/usr/bin/python3
"""Tests for the security hardening: session revocation on password
reset, cross-origin write blocking, tolerant JSON-body handling, and
region-delete cleanup — plus regression guards that the per-IP rate
limiters key on the real visitor behind the proxy (ProxyFix's default
x_for=1) rather than collapsing into one shared bucket."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from models import storage
from models.favorite import Favorite
from models.user import User

TEST_PASSWORD = "correcthorsebattery"
NEW_PASSWORD = "anotherlongpassword"
EVIL = "https://evil.example"
FRONTEND = "http://localhost:8000"


def _email():
    return "user-{}@example.com".format(uuid.uuid4())


def _post(client, url, payload, headers=None):
    return client.post(
        url, data=json.dumps(payload), content_type="application/json",
        headers=headers or {})


def _admin_client():
    client = app.test_client()
    admin = User(name="Hardening Admin", email=_email(), role="admin")
    admin.set_password(TEST_PASSWORD)
    admin.save()
    _post(client, "/api/v1/auth/login",
          {"email": admin.email, "password": TEST_PASSWORD})
    return client


class TestProxyAwareRateLimiting(unittest.TestCase):
    """The limiter keys on the visitor's IP from X-Forwarded-For (the
    last hop, which is the one the hosting proxy adds)."""

    def setUp(self):
        for limiter in (auth_utils.login_limiter,
                        auth_utils.register_limiter):
            limiter._attempts.clear()
        self.email = _email()
        _post(app.test_client(), "/api/v1/auth/register", {
            "name": "Limited", "email": self.email,
            "password": TEST_PASSWORD})

    def _failed_login(self, forwarded_for):
        return _post(
            app.test_client(), "/api/v1/auth/login",
            {"email": self.email, "password": "wrong-password"},
            headers={"X-Forwarded-For": forwarded_for})

    def test_one_visitors_failures_do_not_lock_out_another(self):
        for _ in range(auth_utils.LOGIN_MAX_ATTEMPTS):
            self._failed_login("203.0.113.1")
        self.assertEqual(self._failed_login("203.0.113.1").status_code, 429)
        self.assertEqual(self._failed_login("203.0.113.2").status_code, 401)

    def test_a_client_cannot_spoof_its_way_out_of_the_limit(self):
        """Only the last (proxy-added) entry counts, so inventing an
        earlier one doesn't start a fresh bucket."""
        for i in range(auth_utils.LOGIN_MAX_ATTEMPTS):
            self._failed_login("10.0.0.{}, 203.0.113.9".format(i))
        resp = self._failed_login("192.0.2.77, 203.0.113.9")
        self.assertEqual(resp.status_code, 429)


class TestSessionRevocationOnPasswordReset(unittest.TestCase):
    """A password reset signs out every other session."""

    def setUp(self):
        for limiter in (auth_utils.login_limiter,
                        auth_utils.register_limiter,
                        auth_utils.password_reset_attempt_limiter):
            limiter._attempts.clear()

    def test_old_cookie_stops_working_after_reset(self):
        email = _email()
        old_device = app.test_client()
        _post(old_device, "/api/v1/auth/register", {
            "name": "Resetter", "email": email, "password": TEST_PASSWORD})
        self.assertEqual(old_device.get("/api/v1/auth/me").status_code, 200)

        user = [u for u in storage.all(User).values()
                if u.email == email][0]
        otp = user.generate_password_reset_otp()
        user.save()
        new_device = app.test_client()
        resp = _post(new_device, "/api/v1/auth/reset-password", {
            "email": email, "otp": otp, "password": NEW_PASSWORD})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(new_device.get("/api/v1/auth/me").status_code, 200)
        self.assertEqual(old_device.get("/api/v1/auth/me").status_code, 401)

    def test_new_login_after_reset_works(self):
        email = _email()
        _post(app.test_client(), "/api/v1/auth/register", {
            "name": "Resetter", "email": email, "password": TEST_PASSWORD})
        user = [u for u in storage.all(User).values()
                if u.email == email][0]
        otp = user.generate_password_reset_otp()
        user.save()
        _post(app.test_client(), "/api/v1/auth/reset-password", {
            "email": email, "otp": otp, "password": NEW_PASSWORD})
        client = app.test_client()
        resp = _post(client, "/api/v1/auth/login",
                     {"email": email, "password": NEW_PASSWORD})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(client.get("/api/v1/auth/me").status_code, 200)


class TestCrossOriginWrites(unittest.TestCase):
    """State-changing requests from another site are refused."""

    def setUp(self):
        auth_utils.login_limiter._attempts.clear()

    def _login(self, origin=None):
        headers = {"Origin": origin} if origin else {}
        return _post(app.test_client(), "/api/v1/auth/login",
                     {"email": "nobody@example.com", "password": "x" * 12},
                     headers=headers)

    def test_foreign_origin_is_blocked(self):
        self.assertEqual(self._login(EVIL).status_code, 403)

    def test_foreign_origin_cannot_upload_as_admin(self):
        """The multipart upload is the request CORS alone doesn't stop."""
        admin = _admin_client()
        resp = admin.post(
            "/api/v1/images", data={}, headers={"Origin": EVIL},
            content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 403)

    def test_frontend_origin_is_allowed(self):
        self.assertEqual(self._login(FRONTEND).status_code, 401)

    def test_own_origin_is_allowed(self):
        """Swagger UI at the API's own origin keeps working."""
        self.assertEqual(self._login("http://localhost").status_code, 401)

    def test_no_origin_header_is_allowed(self):
        self.assertEqual(self._login().status_code, 401)

    def test_reads_are_not_affected(self):
        resp = app.test_client().get(
            "/api/v1/news", headers={"Origin": EVIL})
        self.assertEqual(resp.status_code, 200)


class TestMalformedBodies(unittest.TestCase):
    """Wrong-shaped JSON is a 400, never a 500."""

    def setUp(self):
        auth_utils.forum_post_limiter._attempts.clear()
        self.admin = _admin_client()

    def test_list_body_is_rejected_everywhere(self):
        for url in ("/api/v1/forum/posts", "/api/v1/favorites",
                    "/api/v1/news", "/api/v1/historical-events",
                    "/api/v1/regions", "/api/v1/auth/login"):
            resp = _post(self.admin, url, ["not", "an", "object"])
            self.assertEqual(resp.status_code, 400, url)

    def test_non_string_topic_is_rejected(self):
        for topic in ([], {}, ["global"], 5):
            resp = _post(self.admin, "/api/v1/forum/posts",
                         {"body": "x", "topic": topic})
            self.assertEqual(resp.status_code, 400, repr(topic))


class TestRegionDeleteCleanup(unittest.TestCase):
    """Deleting a region leaves no favorites pointing at its cities."""

    def test_favorites_of_deleted_cities_are_removed(self):
        admin = _admin_client()
        region = json.loads(_post(admin, "/api/v1/regions", {
            "name": "Region-{}".format(uuid.uuid4())}).data)
        city = json.loads(_post(
            admin, "/api/v1/regions/{}/cities".format(region["id"]),
            {"name": "City", "latitude": 39.8, "longitude": 46.75}).data)
        resp = _post(admin, "/api/v1/favorites", {"city_id": city["id"]})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(any(
            f.city_id == city["id"] for f in storage.all(Favorite).values()))

        resp = admin.delete("/api/v1/regions/{}".format(region["id"]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(any(
            f.city_id == city["id"] for f in storage.all(Favorite).values()))


if __name__ == "__main__":
    unittest.main()
