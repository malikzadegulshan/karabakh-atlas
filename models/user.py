#!/usr/bin/python3
"""Defines the User class."""
import secrets
from datetime import datetime, timedelta
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Boolean, DateTime
from werkzeug.security import generate_password_hash, check_password_hash

VALID_ROLES = ("user", "admin")
VERIFICATION_TOKEN_LIFETIME = timedelta(hours=24)


class User(BaseModel, Base):
    """Represents an application user (public account or admin)."""

    __tablename__ = "users"

    name = Column(String(128), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="user")
    email_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String(64), nullable=True)
    verification_token_expires_at = Column(DateTime, nullable=True)

    def set_password(self, raw_password):
        """Hash `raw_password` with a salted, slow KDF and store the hash.

        The plain password itself is never stored or logged.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Return True if `raw_password` matches the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def generate_verification_token(self):
        """Create a fresh, time-limited email-verification token and
        return it. Overwrites any previous unused token."""
        token = secrets.token_urlsafe(32)
        self.verification_token = token
        self.verification_token_expires_at = (
            datetime.utcnow() + VERIFICATION_TOKEN_LIFETIME)
        return token

    def consume_verification_token(self, token):
        """If `token` matches this user's current, unexpired token, mark
        the email verified and clear the token (so it can't be reused).
        Returns True on success, False otherwise — the caller decides
        what a failure means (wrong token vs. already verified)."""
        if not self.verification_token or not token:
            return False
        if not secrets.compare_digest(self.verification_token, token):
            return False
        if (self.verification_token_expires_at is None
                or datetime.utcnow() > self.verification_token_expires_at):
            return False
        self.email_verified = True
        self.verification_token = None
        self.verification_token_expires_at = None
        return True

    def public_dict(self):
        """Same as to_dict(), but never includes the password hash or the
        raw verification token.

        Use this (not to_dict()) whenever serializing a user for an API
        response. to_dict() itself must keep including every field —
        FileStorage round-trips objects to disk through it, so stripping
        fields there would silently lose them on every reload.
        """
        data = self.to_dict()
        data.pop("password_hash", None)
        data.pop("verification_token", None)
        return data
