#!/usr/bin/python3
"""Unit tests for models.forum_post.ForumPost."""
import unittest
from models.base_model import BaseModel
from models.forum_post import ForumPost


class TestForumPost(unittest.TestCase):
    """Test cases for the ForumPost class."""

    def test_is_subclass_of_base_model(self):
        """ForumPost inherits from BaseModel."""
        post = ForumPost()
        self.assertIsInstance(post, BaseModel)

    def test_fields_can_be_set(self):
        """Core fields can be assigned and read back."""
        post = ForumPost()
        post.author_id = "some-user-id"
        post.body = "Beautiful region."
        post.status = "pending"
        self.assertEqual(post.author_id, "some-user-id")
        self.assertEqual(post.body, "Beautiful region.")
        self.assertEqual(post.status, "pending")

    def test_target_city_id_defaults_unset(self):
        """A post created without a target_city_id has none set — it's a
        general opinion, not one about a specific city/POI."""
        post = ForumPost()
        self.assertFalse(
            hasattr(post, "target_city_id") and post.target_city_id)


if __name__ == "__main__":
    unittest.main()
