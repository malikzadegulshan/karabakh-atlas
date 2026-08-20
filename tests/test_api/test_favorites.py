#!/usr/bin/python3
"""Tests for the /favorites views: saving/unsaving places, listing a
user's own favorites, and idempotence/isolation between users."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from models.user import User

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


class TestFavoritesViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        auth_utils.register_limiter._attempts.clear()
        auth_utils.login_limiter._attempts.clear()

        self.client = app.test_client()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Favorites User", "email": _unique_email(),
                "password": TEST_PASSWORD}),
            content_type="application/json")
        self.user_id = json.loads(resp.data)["id"]

        # Region/city writes are admin-gated (see require_admin_for_writes
        # in api/v1/app.py) — unrelated to favorites' own login-only
        # gate, just needed to create a city to favorite in the first
        # place, same as test_forum.py's _create_city() helper.
        self.admin_client = app.test_client()
        admin = User(name="Test Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        self.admin_client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")

        region = json.loads(self.admin_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region-{}".format(uuid.uuid4())}),
            content_type="application/json").data)
        city = json.loads(self.admin_client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "City", "latitude": 39.8, "longitude": 46.75}),
            content_type="application/json").data)
        self.city_id = city["id"]

    def _other_client(self):
        other = app.test_client()
        other.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Other User", "email": _unique_email(),
                "password": TEST_PASSWORD}),
            content_type="application/json")
        return other

    # -- Auth gating ---------------------------------------------------

    def test_add_requires_login(self):
        anon = app.test_client()
        resp = anon.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_list_requires_login(self):
        anon = app.test_client()
        resp = anon.get("/api/v1/favorites")
        self.assertEqual(resp.status_code, 401)

    def test_remove_requires_login(self):
        anon = app.test_client()
        resp = anon.delete("/api/v1/favorites/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 401)

    # -- Add/list/remove -------------------------------------------------

    def test_add_and_list_favorite(self):
        resp = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 201)

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual([c["id"] for c in listed], [self.city_id])

    def test_add_rejects_nonexistent_city(self):
        resp = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": "not-a-real-city-id"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_add_rejects_missing_city_id(self):
        resp = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_add_is_idempotent(self):
        """Favoriting the same place twice doesn't create a duplicate
        entry — the second call just returns the existing one."""
        first = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        second = self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            json.loads(first.data)["id"], json.loads(second.data)["id"])

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual(len(listed), 1)

    def test_remove_favorite(self):
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        resp = self.client.delete(
            "/api/v1/favorites/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 200)

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual(listed, [])

    def test_remove_is_idempotent(self):
        """Removing a place that was never favorited is a no-op 200,
        not an error."""
        resp = self.client.delete(
            "/api/v1/favorites/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 200)

    # -- Isolation between users -----------------------------------------

    def test_favorites_are_per_user(self):
        """One user's favorites never show up in another user's list."""
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")

        other = self._other_client()
        other_listed = json.loads(other.get("/api/v1/favorites").data)
        self.assertEqual(other_listed, [])

    def test_cannot_remove_another_users_favorite(self):
        """Deleting doesn't accept a favorite id — only city_id scoped
        to the caller's own session — so there's no way to target
        someone else's bookmark in the first place."""
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")

        other = self._other_client()
        other.delete("/api/v1/favorites/{}".format(self.city_id))

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual([c["id"] for c in listed], [self.city_id])

    # -- Cascade delete ---------------------------------------------------

    def test_deleting_city_removes_favorites_of_it(self):
        self.client.post(
            "/api/v1/favorites",
            data=json.dumps({"city_id": self.city_id}),
            content_type="application/json")
        resp = self.admin_client.delete(
            "/api/v1/cities/{}".format(self.city_id))
        self.assertEqual(resp.status_code, 200)

        listed = json.loads(self.client.get("/api/v1/favorites").data)
        self.assertEqual(listed, [])


if __name__ == "__main__":
    unittest.main()
