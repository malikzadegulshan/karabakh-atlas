#!/usr/bin/python3
"""Tests for the /news views: public reads, admin-only writes,
validation, and comments (which reuse the moderated forum pipeline)."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1 import auth_utils
from models import storage
from models.forum_post import ForumPost
from models.user import User

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "user-{}@example.com".format(uuid.uuid4())


def _json(client, method, url, payload=None):
    return getattr(client, method)(
        url,
        data=json.dumps(payload) if payload is not None else None,
        content_type="application/json")


class TestNewsViews(unittest.TestCase):
    """End-to-end tests against the Flask test client."""

    def setUp(self):
        """An admin client and a regular-user client, both logged in."""
        auth_utils.forum_post_limiter._attempts.clear()
        auth_utils.login_limiter._attempts.clear()
        auth_utils.register_limiter._attempts.clear()

        self.admin_client = app.test_client()
        admin = User(
            name="News Admin", email=_unique_email(), role="admin")
        admin.set_password(TEST_PASSWORD)
        admin.save()
        _json(self.admin_client, "post", "/api/v1/auth/login",
              {"email": admin.email, "password": TEST_PASSWORD})

        self.client = app.test_client()
        resp = _json(self.client, "post", "/api/v1/auth/register", {
            "name": "Reader", "email": _unique_email(),
            "password": TEST_PASSWORD})
        self.reader_id = json.loads(resp.data)["id"]

    def _create_news(self, **overrides):
        payload = {"title": "Headline", "body": "Story text."}
        payload.update(overrides)
        return _json(self.admin_client, "post", "/api/v1/news", payload)

    # -- Admin-only writes -----------------------------------------

    def test_create_requires_login(self):
        """An anonymous caller can't create news."""
        resp = _json(app.test_client(), "post", "/api/v1/news",
                     {"title": "X", "body": "Y"})
        self.assertEqual(resp.status_code, 401)

    def test_create_rejects_non_admin(self):
        """A logged-in regular user can't create news."""
        resp = _json(self.client, "post", "/api/v1/news",
                     {"title": "X", "body": "Y"})
        self.assertEqual(resp.status_code, 403)

    def test_update_and_delete_reject_non_admin(self):
        """A regular user can't edit or delete an existing post."""
        news_id = json.loads(self._create_news().data)["id"]
        put = _json(self.client, "put", "/api/v1/news/" + news_id,
                    {"title": "Hijacked"})
        self.assertEqual(put.status_code, 403)
        delete = self.client.delete("/api/v1/news/" + news_id)
        self.assertEqual(delete.status_code, 403)

    def test_create_succeeds_for_admin(self):
        """An admin can create a post, including a picture."""
        resp = self._create_news(image_url="https://example.com/p.jpg")
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.data)
        self.assertEqual(body["title"], "Headline")
        self.assertEqual(body["image_url"], "https://example.com/p.jpg")
        self.assertEqual(body["comment_count"], 0)

    def test_create_rejects_blank_title_and_body(self):
        """Title and body are required and can't be blank."""
        self.assertEqual(self._create_news(title="  ").status_code, 400)
        self.assertEqual(self._create_news(body="").status_code, 400)

    def test_create_rejects_javascript_image_url(self):
        """image_url and source_url only accept http(s) URLs."""
        self.assertEqual(
            self._create_news(image_url="javascript:alert(1)").status_code,
            400)
        self.assertEqual(
            self._create_news(source_url="javascript:alert(1)").status_code,
            400)

    def test_create_rejects_unknown_fields(self):
        """Fields outside the allowed set are rejected."""
        self.assertEqual(self._create_news(id="x").status_code, 400)

    def test_update_changes_fields(self):
        """An admin can update a post."""
        news_id = json.loads(self._create_news().data)["id"]
        resp = _json(self.admin_client, "put", "/api/v1/news/" + news_id,
                     {"title": "Edited"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.data)["title"], "Edited")

    def test_update_missing_returns_404(self):
        """Updating a nonexistent post is a 404."""
        resp = _json(self.admin_client, "put", "/api/v1/news/nope",
                     {"title": "X"})
        self.assertEqual(resp.status_code, 404)

    # -- Public reads ----------------------------------------------

    def test_list_is_public_and_newest_first(self):
        """Anyone can read the list; the newest post comes first."""
        self._create_news(title="Older story")
        self._create_news(title="Newer story")
        resp = app.test_client().get("/api/v1/news")
        self.assertEqual(resp.status_code, 200)
        titles = [n["title"] for n in json.loads(resp.data)]
        self.assertLess(
            titles.index("Newer story"), titles.index("Older story"))

    def test_i18n_round_trips(self):
        """title_i18n/body_i18n are stored as given."""
        resp = self._create_news(
            title_i18n={"az": "Başlıq"}, body_i18n={"az": "Mətn"})
        body = json.loads(resp.data)
        self.assertEqual(body["title_i18n"]["az"], "Başlıq")
        self.assertEqual(body["body_i18n"]["az"], "Mətn")

    # -- Comments ---------------------------------------------------

    def _comment(self, client, news_id, body="Great news"):
        return _json(client, "post", "/api/v1/forum/posts",
                     {"body": body, "target_news_id": news_id})

    def test_comment_requires_login(self):
        """Commenting needs an account."""
        news_id = json.loads(self._create_news().data)["id"]
        resp = self._comment(app.test_client(), news_id)
        self.assertEqual(resp.status_code, 401)

    def test_comment_starts_pending_and_is_hidden(self):
        """A user's comment is moderated like any forum post."""
        news_id = json.loads(self._create_news().data)["id"]
        resp = self._comment(self.client, news_id)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(json.loads(resp.data)["status"], "pending")
        listing = app.test_client().get(
            "/api/v1/forum/posts?news_id=" + news_id)
        self.assertEqual(json.loads(listing.data), [])

    def test_approved_comment_shows_under_its_news_only(self):
        """Once approved, a comment appears under its news item, counts
        toward comment_count, and never leaks into the general forum."""
        news_id = json.loads(self._create_news().data)["id"]
        other_id = json.loads(self._create_news(title="Other").data)["id"]
        post_id = json.loads(self._comment(
            self.client, news_id, body="Approved comment").data)["id"]
        _json(self.admin_client, "put",
              "/api/v1/forum/posts/{}/status".format(post_id),
              {"status": "approved"})

        under = json.loads(app.test_client().get(
            "/api/v1/forum/posts?news_id=" + news_id).data)
        self.assertEqual([p["body"] for p in under], ["Approved comment"])
        self.assertEqual(under[0]["target_news_title"], "Headline")
        elsewhere = json.loads(app.test_client().get(
            "/api/v1/forum/posts?news_id=" + other_id).data)
        self.assertEqual(elsewhere, [])
        general = json.loads(app.test_client().get(
            "/api/v1/forum/posts").data)
        self.assertNotIn(
            "Approved comment", [p["body"] for p in general])

        news = json.loads(app.test_client().get("/api/v1/news").data)
        counts = {n["id"]: n["comment_count"] for n in news}
        self.assertEqual(counts[news_id], 1)

    def test_moderation_queue_includes_news_comments(self):
        """An admin's pending queue spans every target, so a news
        comment awaiting review is actually reachable by moderation."""
        news_id = json.loads(self._create_news().data)["id"]
        body = "Queued comment {}".format(uuid.uuid4())
        self._comment(self.client, news_id, body=body)
        queue = json.loads(self.admin_client.get(
            "/api/v1/forum/posts?status=pending").data)
        queued = [p for p in queue if p["body"] == body]
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["target_news_title"], "Headline")

    def test_comment_on_missing_news_is_rejected(self):
        """target_news_id must point at a real post."""
        resp = self._comment(self.client, "does-not-exist")
        self.assertEqual(resp.status_code, 400)

    def test_comment_cannot_target_city_and_news(self):
        """A post targets a city or a news item, not both."""
        news_id = json.loads(self._create_news().data)["id"]
        resp = _json(self.client, "post", "/api/v1/forum/posts", {
            "body": "Both", "target_news_id": news_id,
            "target_city_id": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_deleting_news_deletes_its_comments(self):
        """Removing a post also removes the comments on it."""
        news_id = json.loads(self._create_news().data)["id"]
        post_id = json.loads(self._comment(self.client, news_id).data)["id"]
        resp = self.admin_client.delete("/api/v1/news/" + news_id)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(
            "ForumPost.{}".format(post_id), storage.all(ForumPost))
        self.assertEqual(
            self.admin_client.delete("/api/v1/news/" + news_id).status_code,
            404)


if __name__ == "__main__":
    unittest.main()
