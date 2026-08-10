#!/usr/bin/python3
"""Unit tests for models.region.Region."""
import unittest
from models.base_model import BaseModel
from models.region import Region


class TestRegion(unittest.TestCase):
    """Test cases for the Region class."""

    def test_is_subclass_of_base_model(self):
        """Region inherits from BaseModel."""
        region = Region()
        self.assertIsInstance(region, BaseModel)

    def test_default_name_is_empty_string(self):
        """A region created without a name has no name attribute set."""
        region = Region()
        self.assertFalse(hasattr(region, "name") and region.name)

    def test_name_can_be_set(self):
        """The name attribute can be assigned and read back."""
        region = Region()
        region.name = "Sample Region"
        self.assertEqual(region.name, "Sample Region")

    def test_cities_property_starts_empty(self):
        """A brand new region has no linked cities."""
        region = Region()
        region.name = "Sample Region"
        region.save()
        self.assertEqual(region.cities, [])


if __name__ == "__main__":
    unittest.main()
