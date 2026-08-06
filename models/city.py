#!/usr/bin/python3
"""Defines the City class, a point of interest shown on the map."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Float, Text, ForeignKey, JSON


class City(BaseModel, Base):
    """Represents a city or point of interest with map coordinates."""

    __tablename__ = "cities"
    name = Column(String(128), nullable=False)
    region_id = Column(String(60), ForeignKey("regions.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    alt_names = Column(String(255), nullable=True)
    image_url = Column(String(500), nullable=True)
    image_credit = Column(String(255), nullable=True)
    # "city" for regular cities (map label + sidebar entry); anything else
    # (cafe/restaurant/hotel/...) is a user-added point of interest,
    # rendered as a small marker only when zoomed in.
    category = Column(String(32), nullable=False, default="city")
    # Optional per-language overrides, e.g. {"az": "...", "tr": "...",
    # "ru": "..."}.
    # `name`/`description` above remain the English fallback when a
    # translation is missing for the requested language.
    name_i18n = Column(JSON, nullable=True)
    description_i18n = Column(JSON, nullable=True)
