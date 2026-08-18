#!/usr/bin/python3
"""Defines the City class, a point of interest shown on the map."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
import models


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
    phone = Column(String(30), nullable=True)
    website = Column(String(500), nullable=True)
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

    # Declared purely so DBStorage's flush knows forum_posts rows must be
    # deleted before their referenced cities row — without this,
    # SQLAlchemy has no way to know that dependency (it isn't inferred
    # from a bare ForeignKey column alone) and can emit the DELETE
    # statements in the wrong order, violating the FK constraint. The
    # views still do the actual cascading delete explicitly (see
    # delete_city/delete_region in api/v1/views/) since FileStorage has
    # no ORM cascade mechanism at all — this relationship is a
    # correctness fix for DBStorage's statement ordering, not a
    # replacement for that manual cleanup.
    if models.storage_t == "db":
        forum_posts = relationship("ForumPost", cascade="all, delete-orphan")
    else:
        @property
        def forum_posts(self):
            """Return ForumPost instances that target this city
            (FileStorage)."""
            from models.forum_post import ForumPost
            return [p for p in models.storage.all(ForumPost).values()
                    if p.target_city_id == self.id]
