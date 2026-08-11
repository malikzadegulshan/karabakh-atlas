#!/usr/bin/python3
"""Defines BaseModel, the parent class of every model in this project."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


class BaseModel:
    """Common attributes/methods shared by all Karabakh Atlas models."""

    id = Column(String(60), primary_key=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __init__(self, *args, **kwargs):
        """Initialize a new instance, or rebuild one from kwargs."""
        if kwargs:
            for key, value in kwargs.items():
                if key == "__class__":
                    continue
                # Every DateTime column in this codebase is named with an
                # "_at" suffix (created_at, updated_at,
                # verification_token_expires_at, ...) — reload from
                # FileStorage's JSON hands these back as strings, so
                # parse any of them back into real datetime objects.
                if key.endswith("_at") and isinstance(value, str):
                    value = datetime.strptime(value, TIME_FORMAT)
                setattr(self, key, value)
            if "id" not in kwargs:
                self.id = str(uuid.uuid4())
            if "created_at" not in kwargs:
                self.created_at = datetime.utcnow()
            if "updated_at" not in kwargs:
                self.updated_at = datetime.utcnow()
        else:
            self.id = str(uuid.uuid4())
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()
            # Not registered with storage here — only save() does that.
            # A schema-enforcing database (unlike FileStorage) will
            # reject an incomplete object like this the moment anything
            # in the session flushes, even if this instance itself is
            # never explicitly saved.

    def __str__(self):
        """Return the informal string representation of the instance."""
        attrs = {k: v for k, v in self.__dict__.items()
                 if k != "_sa_instance_state"}
        return "[{}] ({}) {}".format(type(self).__name__, self.id, attrs)

    def __repr__(self):
        """Return the same representation as __str__."""
        return self.__str__()

    def save(self):
        """Update updated_at and persist the instance through storage."""
        import models
        self.updated_at = datetime.utcnow()
        models.storage.new(self)
        models.storage.save()

    def to_dict(self):
        """Return a JSON-serializable dictionary of the instance."""
        new_dict = self.__dict__.copy()
        new_dict["__class__"] = type(self).__name__
        for key, value in new_dict.items():
            if isinstance(value, datetime):
                new_dict[key] = value.isoformat()
        new_dict.pop("_sa_instance_state", None)
        return new_dict

    def delete(self):
        """Delete the instance from storage."""
        import models
        models.storage.delete(self)
