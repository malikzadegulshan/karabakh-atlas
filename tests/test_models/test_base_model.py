#!/usr/bin/python3
"""Unit tests for models.base_model.BaseModel."""
import unittest
from datetime import datetime
from models.base_model import BaseModel
from models.region import Region


class TestBaseModel(unittest.TestCase):
    """Test cases for the BaseModel class."""

    def test_init_no_args_sets_defaults(self):
        """A freshly created instance gets id, created_at, updated_at."""
        obj = BaseModel()
        self.assertIsInstance(obj.id, str)
        self.assertIsInstance(obj.created_at, datetime)
        self.assertIsInstance(obj.updated_at, datetime)

    def test_two_instances_have_different_ids(self):
        """Each instance gets a unique id."""
        obj1 = BaseModel()
        obj2 = BaseModel()
        self.assertNotEqual(obj1.id, obj2.id)

    def test_str_representation(self):
        """__str__ includes the class name, id, and attribute dict."""
        obj = BaseModel()
        text = str(obj)
        self.assertIn("[BaseModel]", text)
        self.assertIn(obj.id, text)

    def test_to_dict_contains_class_key(self):
        """to_dict() adds a __class__ key with the class name."""
        obj = BaseModel()
        d = obj.to_dict()
        self.assertEqual(d["__class__"], "BaseModel")
        self.assertIsInstance(d["created_at"], str)
        self.assertIsInstance(d["updated_at"], str)

    def test_init_from_kwargs_rebuilds_instance(self):
        """Passing kwargs (as from to_dict) reconstructs an equivalent
        instance."""
        original = BaseModel()
        original.name = "test"
        d = original.to_dict()
        rebuilt = BaseModel(**d)
        self.assertEqual(original.id, rebuilt.id)
        self.assertEqual(original.created_at, rebuilt.created_at)

    def test_save_updates_updated_at(self):
        """save() refreshes updated_at to a later timestamp."""
        # A real mapped subclass, not bare BaseModel: save() persists
        # through storage, and BaseModel itself isn't a mapped table.
        obj = Region(name="Save Test Region")
        old_updated_at = obj.updated_at
        obj.save()
        self.assertGreaterEqual(obj.updated_at, old_updated_at)


if __name__ == "__main__":
    unittest.main()
