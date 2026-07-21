#!/usr/bin/python3
"""Defines the City class, a point of interest shown on the map."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Float, Text, ForeignKey


class City(BaseModel, Base):
    """Represents a city or point of interest with map coordinates."""

    __tablename__ = "cities"
    name = Column(String(128), nullable=False)
    region_id = Column(String(60), ForeignKey("regions.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    alt_names = Column(String(255), nullable=True)
