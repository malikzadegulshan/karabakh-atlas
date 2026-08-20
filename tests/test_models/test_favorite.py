#!/usr/bin/python3
"""Unit tests for models.favorite.Favorite."""
import unittest
from models.base_model import BaseModel
from models.favorite import Favorite


class TestFavorite(unittest.TestCase):
    """Test cases for the Favorite class."""

    def test_is_subclass_of_base_model(self):
        """Favorite inherits from BaseModel."""
        favorite = Favorite()
        self.assertIsInstance(favorite, BaseModel)

    def test_fields_can_be_set(self):
        """Core fields can be assigned and read back."""
        favorite = Favorite()
        favorite.user_id = "some-user-id"
        favorite.city_id = "some-city-id"
        self.assertEqual(favorite.user_id, "some-user-id")
        self.assertEqual(favorite.city_id, "some-city-id")


if __name__ == "__main__":
    unittest.main()
