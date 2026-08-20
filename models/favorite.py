#!/usr/bin/python3
"""Defines the Favorite class — a logged-in user bookmarking a city or
point of interest to find again later."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, ForeignKey


class Favorite(BaseModel, Base):
    """A user's saved place. Uniqueness (a user can't favorite the same
    place twice) is enforced in the view layer, not a DB constraint —
    FileStorage has no equivalent, so both storage engines need to agree
    on the same rule regardless."""

    __tablename__ = "favorites"

    user_id = Column(String(60), ForeignKey("users.id"), nullable=False)
    city_id = Column(String(60), ForeignKey("cities.id"), nullable=False)
