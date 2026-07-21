#!/usr/bin/python3
"""Defines the Region class, a geographic grouping of cities."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
import models


class Region(BaseModel, Base):
    """Represents a region/district that groups cities on the map."""

    __tablename__ = "regions"
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

    if models.storage_t == "db":
        cities = relationship(
            "City", backref="region", cascade="all, delete-orphan")
    else:
        @property
        def cities(self):
            """Return City instances linked to this region (FileStorage)."""
            from models.city import City
            return [c for c in models.storage.all(City).values()
                    if c.region_id == self.id]
