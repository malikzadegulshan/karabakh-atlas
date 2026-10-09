#!/usr/bin/python3
"""Unit tests for api.v1.forum_utils."""
import unittest
from api.v1.forum_utils import delete_forum_posts, publicly_visible


class _Post:
    def __init__(self, id, parent_id=None, status="approved", log=None):
        self.id = id
        self.parent_id = parent_id
        self.status = status
        self._log = log

    def delete(self):
        self._log.append(self.id)


class TestForumUtils(unittest.TestCase):
    """Replies are removed before the posts they answer."""

    def test_replies_are_deleted_before_their_parents(self):
        log = []
        parent = _Post("p", log=log)
        reply = _Post("r", parent_id="p", log=log)
        other = _Post("o", log=log)
        delete_forum_posts([parent, other, reply])
        self.assertLess(log.index("r"), log.index("p"))
        self.assertEqual(sorted(log), ["o", "p", "r"])

    def test_visibility_follows_the_parent(self):
        parent = _Post("p")
        reply = _Post("r", parent_id="p")
        by_id = {"p": parent, "r": reply}
        self.assertTrue(publicly_visible(reply, by_id))
        parent.status = "rejected"
        self.assertFalse(publicly_visible(reply, by_id))
        self.assertFalse(publicly_visible(parent, by_id))

    def test_pending_posts_are_not_visible(self):
        self.assertFalse(publicly_visible(_Post("x", status="pending"), {}))

    def test_reply_with_missing_parent_is_not_visible(self):
        self.assertFalse(publicly_visible(_Post("r", parent_id="gone"), {}))


if __name__ == "__main__":
    unittest.main()
