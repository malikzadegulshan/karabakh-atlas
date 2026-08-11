#!/usr/bin/python3
"""Tests for the /auth/* views (register, login, logout, me)."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


class TestAuthViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Create a fresh client and reset the in-memory rate limiter."""
        self.client = app.test_client()
        auth_utils._login_attempts.clear()

    def test_register_creates_account_and_logs_in(self):
        """A successful registration also starts a logged-in session."""
        email = _unique_email()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["email"], email)
        self.assertEqual(body["role"], "user")
        self.assertNotIn("password_hash", body)

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(json.loads(me_resp.data)["email"], email)

    def test_register_rejects_short_password(self):
        """Passwords under the minimum length are rejected."""
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": _unique_email(),
                 "password": "short"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_invalid_email(self):
        """Malformed email addresses are rejected."""
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": "not-an-email",
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_duplicate_email(self):
        """A second registration with the same email is rejected."""
        email = _unique_email()
        first = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "First", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "Second", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(second.status_code, 409)

    def test_login_with_correct_credentials(self):
        """Logging in with the right password succeeds and sets a session."""
        email = _unique_email()
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)

    def test_login_with_wrong_password_fails(self):
        """A wrong password is rejected with 401."""
        email = _unique_email()
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.client.post("/api/v1/auth/logout")

        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": email, "password": "wrong-password"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_login_with_unknown_email_fails(self):
        """An email with no account gets the same generic error."""
        resp = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": _unique_email(), "password": TEST_PASSWORD}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_clears_session(self):
        """After logout, /auth/me is unauthenticated again."""
        email = _unique_email()
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.client.post("/api/v1/auth/logout")

        me_resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(me_resp.status_code, 401)

    def test_me_without_session_is_401(self):
        """/auth/me with no session cookie at all returns 401."""
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_login_rate_limited_after_repeated_failures(self):
        """Repeated bad-password attempts eventually get rate-limited."""
        email = _unique_email()
        self.client.post(
            "/api/v1/auth/register",
            data=json.dumps(
                {"name": "New User", "email": email,
                 "password": TEST_PASSWORD}),
            content_type="application/json")
        self.client.post("/api/v1/auth/logout")

        last_status = None
        for _ in range(auth_utils.LOGIN_MAX_ATTEMPTS + 1):
            resp = self.client.post(
                "/api/v1/auth/login",
                data=json.dumps(
                    {"email": email, "password": "wrong-password"}),
                content_type="application/json")
            last_status = resp.status_code
        self.assertEqual(last_status, 429)


if __name__ == "__main__":
    unittest.main()
