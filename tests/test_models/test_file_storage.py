#!/usr/bin/python3
"""Unit tests for models.engine.file_storage.FileStorage."""
import unittest
from models import storage
from models.region import Region
from models.city import City


class TestFileStorage(unittest.TestCase):
    """Test cases for the FileStorage engine."""

    def test_new_and_all(self):
        """new() registers an object so it is returned by all()."""
        region = Region(name="Test Region")
        region.save()
        key = "Region.{}".format(region.id)
        self.assertIn(key, storage.all())

    def test_all_filters_by_class(self):
        """all(cls) only returns objects of the requested class."""
        region = Region(name="Filter Region")
        region.save()
        city = City(name="Filter City", latitude=1.0, longitude=1.0)
        city.save()
        regions = storage.all(Region)
        self.assertTrue(all(isinstance(o, Region) for o in regions.values()))

    def test_delete_removes_object(self):
        """delete() removes the object from storage.all()."""
        region = Region(name="Delete Me")
        region.save()
        key = "Region.{}".format(region.id)
        region.delete()
        storage.save()
        self.assertNotIn(key, storage.all())


if __name__ == "__main__":
    unittest.main()
