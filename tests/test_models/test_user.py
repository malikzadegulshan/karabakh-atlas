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

    def test_set_password_hashes_it(self):
        """set_password() never stores the raw password."""
        user = User()
        user.set_password("correcthorsebattery")
        self.assertNotEqual(user.password_hash, "correcthorsebattery")
        self.assertTrue(len(user.password_hash) > 20)

    def test_check_password_accepts_correct_password(self):
        """check_password() returns True for the password it was set to."""
        user = User()
        user.set_password("correcthorsebattery")
        self.assertTrue(user.check_password("correcthorsebattery"))

    def test_check_password_rejects_wrong_password(self):
        """check_password() returns False for any other password."""
        user = User()
        user.set_password("correcthorsebattery")
        self.assertFalse(user.check_password("wrong-password"))

    def test_public_dict_excludes_password_hash(self):
        """public_dict() never leaks the password hash."""
        user = User(name="Test User", email="test@example.com")
        user.set_password("correcthorsebattery")
        self.assertNotIn("password_hash", user.public_dict())

    def test_to_dict_keeps_password_hash(self):
        """to_dict() keeps password_hash — FileStorage round-trips objects
        to disk through it, so stripping it there would lose it."""
        user = User(name="Test User", email="test@example.com")
        user.set_password("correcthorsebattery")
        self.assertIn("password_hash", user.to_dict())


if __name__ == "__main__":
    unittest.main()
