#!/usr/bin/python3
"""Defines the User class."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String


class User(BaseModel, Base):
    """Represents an application user."""

    __tablename__ = "users"

    name = Column(String(128), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
