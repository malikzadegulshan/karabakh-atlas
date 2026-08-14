#!/usr/bin/python3
"""Tests for the /forum/posts views: creation, moderation-gated
visibility, deletion permissions, and abuse protections."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from models.user import User

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


class TestForumViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """Reset the in-memory rate limiter and register two accounts:
        a regular user (self.client, logged in) and an admin
        (self.admin_client, logged in) — most tests only need one."""
        auth_utils.forum_post_limiter._attempts.clear()
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()

        self.client = app.test_client()
        self.user_email = _unique_email()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Forum User", "email": self.user_email,
                "password": TEST_PASSWORD}),
            content_type="application/json")
        self.user_id = json.loads(resp.data)["id"]

        self.admin_client = app.test_client()
        admin = User(
            name="Test Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        self.admin_id = admin.id
        self.admin_client.post(
            "/api/v1/auth/login",
            data=json.dumps(
                {"email": admin.email, "password": TEST_PASSWORD}),
            content_type="application/json")

    def _create_post(self, client=None, body="This region is beautiful.",
                      target_city_id=None):
        client = client or self.client
        payload = {"body": body}
        if target_city_id is not None:
            payload["target_city_id"] = target_city_id
        return client.post(
            "/api/v1/forum/posts",
            data=json.dumps(payload),
            content_type="application/json")

    # -- Creation --------------------------------------------------

    def test_create_requires_login(self):
        """Posting without a session is rejected with 401."""
        anon = app.test_client()
        resp = self._create_post(client=anon)
        self.assertEqual(resp.status_code, 401)

    def test_create_starts_pending(self):
        """A freshly created post is "pending", never immediately public."""
        resp = self._create_post()
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["author_id"], self.user_id)

    def test_admin_post_is_auto_approved(self):
        """An admin's own post skips the moderation queue entirely."""
        resp = self._create_post(client=self.admin_client, body="Admin opinion")
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["status"], "approved")
        self.assertEqual(body["moderated_by"], self.admin_id)
        self.assertIsNotNone(body["moderated_at"])

        public_bodies = [
            p["body"] for p in
            json.loads(self.client.get("/api/v1/forum/posts").data)]
        self.assertIn("Admin opinion", public_bodies)

    def test_admin_posting_is_not_rate_limited(self):
        """An admin can post past the regular per-account rate limit."""
        limit = auth_utils.forum_post_limiter.max_attempts
        last_status = None
        for _ in range(limit + 2):
            last_status = self._create_post(client=self.admin_client).status_code
        self.assertEqual(last_status, 201)

    def test_create_rejects_empty_body(self):
        """A blank/whitespace-only body is rejected."""
        resp = self._create_post(body="   ")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_body_over_max_length(self):
        """A body longer than the max length is rejected."""
        resp = self._create_post(body="x" * 2001)
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_status_field_tampering(self):
        """A client can't force a post straight to "approved" on create."""
        resp = self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps({"body": "Nice place.", "status": "approved"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_author_id_field_tampering(self):
        """A client can't post "as" a different user."""
        resp = self.client.post(
            "/api/v1/forum/posts",
            data=json.dumps(
                {"body": "Nice place.", "author_id": "someone-else"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_nonexistent_target_city(self):
        """A target_city_id that doesn't reference a real city is rejected."""
        resp = self._create_post(target_city_id="not-a-real-city-id")
        self.assertEqual(resp.status_code, 400)

    def test_create_stores_html_payload_as_plain_text(self):
        """A script-tag payload is stored verbatim as inert text, not
        executed or mangled — escaping is the frontend's job at render
        time, so the API itself just needs to round-trip it exactly."""
        payload = "<script>alert(1)</script>"
        resp = self._create_post(body=payload)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(json.loads(resp.data)["body"], payload)

    def test_create_is_rate_limited(self):
        """Repeated posting eventually gets rate-limited."""
        last_status = None
        limit = auth_utils.forum_post_limiter.max_attempts
        for _ in range(limit + 1):
            last_status = self._create_post().status_code
        self.assertEqual(last_status, 429)

    # -- Visibility --------------------------------------------------

    def test_pending_post_not_publicly_visible(self):
        """A pending post doesn't show up in the public listing."""
        self._create_post(body="Should stay hidden")
        resp = self.client.get("/api/v1/forum/posts")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertNotIn("Should stay hidden", bodies)

    def test_mine_shows_own_pending_post(self):
        """The author can see their own post via ?mine=true even while
        it's still pending."""
        self._create_post(body="My own pending opinion")
        resp = self.client.get("/api/v1/forum/posts?mine=true")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertIn("My own pending opinion", bodies)

    def test_mine_requires_login(self):
        """?mine=true without a session is rejected with 401."""
        anon = app.test_client()
        resp = anon.get("/api/v1/forum/posts?mine=true")
        self.assertEqual(resp.status_code, 401)

    def test_status_filter_ignored_for_non_admin(self):
        """A non-admin passing ?status=pending still only gets approved
        posts — the moderation queue never leaks to a guessed query
        param."""
        self._create_post(body="Sneaky pending read attempt")
        resp = self.client.get("/api/v1/forum/posts?status=pending")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertNotIn("Sneaky pending read attempt", bodies)

    def test_status_filter_works_for_admin(self):
        """An admin passing ?status=pending gets the moderation queue."""
        self._create_post(body="Awaiting review")
        resp = self.admin_client.get("/api/v1/forum/posts?status=pending")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertIn("Awaiting review", bodies)

    def test_approved_post_is_publicly_visible(self):
        """Once approved, a post shows up in the public listing."""
        create_resp = self._create_post(body="Now approved")
        post_id = json.loads(create_resp.data)["id"]
        approve_resp = self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")
        self.assertEqual(approve_resp.status_code, 200)

        resp = self.client.get("/api/v1/forum/posts")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertIn("Now approved", bodies)

    def test_rejected_post_stays_hidden(self):
        """A rejected post is not shown publicly, and records who
        moderated it."""
        create_resp = self._create_post(body="Should be rejected")
        post_id = json.loads(create_resp.data)["id"]
        reject_resp = self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "rejected"}),
            content_type="application/json")
        self.assertEqual(reject_resp.status_code, 200)
        body = json.loads(reject_resp.data)
        self.assertEqual(body["moderated_by"], self.admin_id)
        self.assertIsNotNone(body["moderated_at"])

        resp = self.client.get("/api/v1/forum/posts")
        bodies = [p["body"] for p in json.loads(resp.data)]
        self.assertNotIn("Should be rejected", bodies)

    # -- Moderation permissions ---------------------------------------

    def test_moderate_requires_admin(self):
        """A non-admin can't approve/reject posts, even their own."""
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        resp = self.client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_moderate_requires_login(self):
        """Anonymous requests can't approve/reject posts."""
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        anon = app.test_client()
        resp = anon.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    # -- Deletion --------------------------------------------------

    def test_author_can_delete_own_post(self):
        """A post's own author can delete it without being an admin."""
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        resp = self.client.delete("/api/v1/forum/posts/{}".format(post_id))
        self.assertEqual(resp.status_code, 200)

    def test_other_user_cannot_delete_post(self):
        """A different logged-in user can't delete someone else's post."""
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]

        other_client = app.test_client()
        other_client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Other User", "email": _unique_email(),
                "password": TEST_PASSWORD}),
            content_type="application/json")
        resp = other_client.delete("/api/v1/forum/posts/{}".format(post_id))
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_delete_any_post(self):
        """An admin can delete a post they didn't author."""
        create_resp = self._create_post()
        post_id = json.loads(create_resp.data)["id"]
        resp = self.admin_client.delete(
            "/api/v1/forum/posts/{}".format(post_id))
        self.assertEqual(resp.status_code, 200)

    # -- City-scoped posts and cascade delete --------------------------

    def _create_city(self):
        region = json.loads(self.admin_client.post(
            "/api/v1/regions",
            data=json.dumps({"name": "Region-{}".format(uuid.uuid4())}),
            content_type="application/json").data)
        city = json.loads(self.admin_client.post(
            "/api/v1/regions/{}/cities".format(region["id"]),
            data=json.dumps(
                {"name": "City", "latitude": 39.8, "longitude": 46.75}),
            content_type="application/json").data)
        return city["id"]

    def test_city_scoped_post_only_shows_under_that_city(self):
        """A post about a specific city doesn't show in the general
        (target_city_id is null) listing, and vice versa."""
        city_id = self._create_city()
        create_resp = self._create_post(
            body="About this city", target_city_id=city_id)
        post_id = json.loads(create_resp.data)["id"]
        self.admin_client.put(
            "/api/v1/forum/posts/{}/status".format(post_id),
            data=json.dumps({"status": "approved"}),
            content_type="application/json")

        general_bodies = [
            p["body"] for p in
            json.loads(self.client.get("/api/v1/forum/posts").data)]
        self.assertNotIn("About this city", general_bodies)

        city_bodies = [
            p["body"] for p in json.loads(self.client.get(
                "/api/v1/forum/posts?city_id={}".format(city_id)).data)]
        self.assertIn("About this city", city_bodies)

    def test_deleting_city_cascades_to_its_forum_posts(self):
        """Deleting a city also removes any forum posts about it."""
        city_id = self._create_city()
        self._create_post(body="About a soon-deleted city",
                           target_city_id=city_id)

        resp = self.admin_client.delete(
            "/api/v1/cities/{}".format(city_id))
        self.assertEqual(resp.status_code, 200)

        mine_bodies = [
            p["body"] for p in
            json.loads(self.client.get(
                "/api/v1/forum/posts?mine=true&city_id={}".format(
                    city_id)).data)]
        self.assertNotIn("About a soon-deleted city", mine_bodies)


if __name__ == "__main__":
    unittest.main()
