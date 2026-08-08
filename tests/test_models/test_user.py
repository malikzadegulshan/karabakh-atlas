#!/usr/bin/python3
"""Unit tests for User."""
import unittest
from models.base_model import BaseModel
from models.user import User


class TestUser(unittest.TestCase):
    """Test User model."""

    def test_user_is_base_model(self):
        """User inherits from BaseModel."""
        user = User()
        self.assertIsInstance(user, BaseModel)

    def test_user_name(self):
        """User name can be assigned."""
        user = User()
        user.name = "Test User"
        self.assertEqual(user.name, "Test User")

    def test_user_email(self):
        """User email can be assigned."""
        user = User()
        user.email = "test@example.com"
        self.assertEqual(user.email, "test@example.com")


if __name__ == "__main__":
    unittest.main()
