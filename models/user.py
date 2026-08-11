#!/usr/bin/python3
"""Defines the User class."""
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String
from werkzeug.security import generate_password_hash, check_password_hash

VALID_ROLES = ("user", "admin")


class User(BaseModel, Base):
    """Represents an application user (public account or admin)."""

    __tablename__ = "users"

    name = Column(String(128), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="user")

    def set_password(self, raw_password):
        """Hash `raw_password` with a salted, slow KDF and store the hash.

        The plain password itself is never stored or logged.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Return True if `raw_password` matches the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def public_dict(self):
        """Same as to_dict(), but never includes the password hash.

        Use this (not to_dict()) whenever serializing a user for an API
        response. to_dict() itself must keep including password_hash —
        FileStorage round-trips objects to disk through it, so stripping
        the hash there would silently lose it on every reload.
        """
        data = self.to_dict()
        data.pop("password_hash", None)
        return data
