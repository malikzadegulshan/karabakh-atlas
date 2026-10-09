#!/usr/bin/python3
"""Tests for contribution tiers (api/v1/contributions.py): the tier
boundary logic itself, and that it actually shows up on /auth/me and
in the forum post feed."""
import json
import unittest
import uuid
from api.v1.app import app
from api.v1.contributions import approved_post_count, contribution_tier
from models.user import User
from models.forum_post import ForumPost

TEST_PASSWORD = "correcthorsebattery"


def _unique_email():
    return "contrib-{}@example.com".format(uuid.uuid4())


def _make_post(author_id, status="approved", body="Test post"):
    post = ForumPost(author_id=author_id, body=body, status=status)
    post.save()
    return post


class TestContributionTier(unittest.TestCase):
    """Pure boundary tests for contribution_tier() — no app/db needed."""

    def test_zero_posts_has_no_tier(self):
        self.assertIsNone(contribution_tier(0))

    def test_below_first_threshold_has_no_tier(self):
        # First tier starts at 1, so this only matters if that ever
        # changes — guards against an off-by-one at the boundary.
        self.assertIsNone(contribution_tier(0))

    def test_newcomer_boundary(self):
        self.assertEqual(contribution_tier(1), "newcomer")
        self.assertEqual(contribution_tier(2), "newcomer")

    def test_contributor_boundary(self):
        self.assertEqual(contribution_tier(3), "contributor")
        self.assertEqual(contribution_tier(9), "contributor")

    def test_local_expert_boundary(self):
        self.assertEqual(contribution_tier(10), "local_expert")
        self.assertEqual(contribution_tier(1000), "local_expert")


class TestApprovedPostCount(unittest.TestCase):
    """approved_post_count() only counts a given user's own approved
    posts — not pending/rejected ones, and not other users'."""

    def setUp(self):
        self.user = User(name="Counter", email=_unique_email(), role="user")
        self.user.set_password(TEST_PASSWORD)
        self.user.save()
        self.other = User(name="Other", email=_unique_email(), role="user")
        self.other.set_password(TEST_PASSWORD)
        self.other.save()

    def test_counts_only_approved(self):
        _make_post(self.user.id, status="approved")
        _make_post(self.user.id, status="pending")
        _make_post(self.user.id, status="rejected")
        self.assertEqual(approved_post_count(self.user.id), 1)

    def test_ignores_other_users(self):
        _make_post(self.user.id, status="approved")
        _make_post(self.other.id, status="approved")
        _make_post(self.other.id, status="approved")
        self.assertEqual(approved_post_count(self.user.id), 1)
        self.assertEqual(approved_post_count(self.other.id), 2)

    def test_zero_for_a_user_with_no_posts(self):
        self.assertEqual(approved_post_count(self.user.id), 0)


class TestContributionsInApiResponses(unittest.TestCase):
    """End-to-end: contribution_count/contribution_tier actually reach
    /auth/me, and author_tier reaches the forum post feed."""

    def setUp(self):
        self.client = app.test_client()
        self.email = _unique_email()
        resp = self.client.post(
            "/api/v1/auth/register",
            data=json.dumps({
                "name": "Tiered User", "email": self.email,
                "password": TEST_PASSWORD}),
            content_type="application/json")
        self.user_id = json.loads(resp.data)["id"]

    def test_me_has_no_tier_with_zero_posts(self):
        resp = self.client.get("/api/v1/auth/me")
        data = json.loads(resp.data)
        self.assertEqual(data["contribution_count"], 0)
        self.assertIsNone(data["contribution_tier"])

    def test_me_reflects_approved_post_count(self):
        for _ in range(3):
            _make_post(self.user_id, status="approved")
        resp = self.client.get("/api/v1/auth/me")
        data = json.loads(resp.data)
        self.assertEqual(data["contribution_count"], 3)
        self.assertEqual(data["contribution_tier"], "contributor")

    def test_pending_posts_dont_count_toward_me(self):
        _make_post(self.user_id, status="pending")
        resp = self.client.get("/api/v1/auth/me")
        data = json.loads(resp.data)
        self.assertEqual(data["contribution_count"], 0)
        self.assertIsNone(data["contribution_tier"])

    def test_forum_feed_includes_author_tier(self):
        # Three approved posts puts this author at "contributor" — the
        # feed should reflect their *total* count on every one of
        # their posts, not just whichever one happens to be post #3.
        for _ in range(3):
            _make_post(self.user_id, status="approved")
        resp = self.client.get("/api/v1/forum/posts")
        posts = json.loads(resp.data)
        own_posts = [p for p in posts if p["author_id"] == self.user_id]
        self.assertEqual(len(own_posts), 3)
        for post in own_posts:
            self.assertEqual(post["author_tier"], "contributor")
