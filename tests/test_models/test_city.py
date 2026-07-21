#!/usr/bin/python3
"""Unit tests for models.city.City."""
import unittest
from models.base_model import BaseModel
from models.city import City


class TestCity(unittest.TestCase):
    """Test cases for the City class."""

    def test_is_subclass_of_base_model(self):
        """City inherits from BaseModel."""
        city = City()
        self.assertIsInstance(city, BaseModel)

    def test_coordinates_can_be_set(self):
        """Latitude and longitude can be assigned and read back."""
        city = City()
        city.name = "Sample City"
        city.latitude = 39.75
        city.longitude = 46.75
        self.assertEqual(city.latitude, 39.75)
        self.assertEqual(city.longitude, 46.75)

    def test_region_id_defaults_unset(self):
        """A city created without a region_id has none set."""
        city = City()
        self.assertFalse(hasattr(city, "region_id") and city.region_id)


if __name__ == "__main__":
    unittest.main()
