#!/usr/bin/python3
"""Defines FileStorage, a JSON-file-backed persistence engine."""
import json
from models.region import Region
from models.city import City

classes = {"Region": Region, "City": City}


class FileStorage:
    """Serializes instances to a JSON file and deserializes them back."""

    __file_path = "kba_file.json"
    __objects = {}

    def all(self, cls=None):
        """Return stored objects, optionally filtered by class."""
        if cls is None:
            return self.__objects
        if isinstance(cls, str):
            cls = classes.get(cls)
        return {k: v for k, v in self.__objects.items() if type(v) is cls}

    def new(self, obj):
        """Register a new object under storage."""
        key = "{}.{}".format(type(obj).__name__, obj.id)
        self.__objects[key] = obj

    def save(self):
        """Serialize all stored objects to the JSON file."""
        d = {k: v.to_dict() for k, v in self.__objects.items()}
        with open(self.__file_path, "w") as f:
            json.dump(d, f)

    def reload(self):
        """Deserialize the JSON file back into objects, if it exists."""
        try:
            with open(self.__file_path, "r") as f:
                d = json.load(f)
        except FileNotFoundError:
            return
        for key, value in d.items():
            cls = classes.get(value.get("__class__"))
            if cls:
                self.__objects[key] = cls(**value)

    def delete(self, obj=None):
        """Delete obj from __objects if it is present."""
        if obj is None:
            return
        key = "{}.{}".format(type(obj).__name__, obj.id)
        self.__objects.pop(key, None)

    def close(self):
        """Call reload, kept for interface parity with DBStorage."""
        self.reload()
