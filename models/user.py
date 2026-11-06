#!/usr/bin/python3
"""Defines the User class."""
import secrets
from datetime import datetime, timedelta
from models.base_model import BaseModel, Base
from sqlalchemy import Column, String, Boolean, DateTime, Integer
from werkzeug.security import generate_password_hash, check_password_hash

VALID_ROLES = ("user", "admin")
# Short on purpose: a 6-digit OTP only has 1,000,000 possible values, so
# it needs a tight window — combined with
# password_reset_attempt_limiter in api/v1/views/auth.py, 15 minutes
# keeps an online guessing attack infeasible within any one code's
# lifetime.
PASSWORD_RESET_OTP_LIFETIME = timedelta(minutes=15)


class User(BaseModel, Base):
    """Represents an application user (public account or admin)."""

    __tablename__ = "users"

    name = Column(String(128), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="user")
    # Legacy: email verification was replaced by admin approval (see
    # `approved`). Kept because existing databases have this column as
    # NOT NULL, so dropping it from the model would break inserts there.
    email_verified = Column(Boolean, nullable=False, default=False)
    # Admin approval. New registrations are saved with approved=False and
    # can't log in until an admin flips it to True. Nullable on purpose:
    # accounts created before this column existed get NULL when it's
    # added to a populated table, and those must stay usable — so only an
    # explicit False means "awaiting approval" (see is_approved).
    approved = Column(Boolean, nullable=True)
    # Why the person wants to join, as typed on the registration form —
    # shown to the admin when deciding whether to approve.
    join_reason = Column(String(500), nullable=True)
    # Preferred UI language ("en", "az", "tr", "ru") captured at sign-up
    # so admin-approval and account emails arrive in their language.
    lang = Column(String(8), nullable=True, default="en")
    # Admin ban flag. Nullable so existing rows default to unbanned.
    banned = Column(Boolean, nullable=True, default=False)
    password_reset_otp = Column(String(6), nullable=True)
    password_reset_otp_expires_at = Column(DateTime, nullable=True)
    # Bumped whenever the password is reset. Each login stores the value
    # in its session cookie (see log_in in api/v1/auth_utils.py), and a
    # cookie carrying an older one stops working — sessions are stateless
    # signed cookies, so this is the only way to sign other devices out.
    session_epoch = Column(Integer, nullable=False, default=0)

    @property
    def is_approved(self):
        """True unless an admin hasn't approved this account yet.

        Only an explicit False is "pending"; None (accounts that predate
        the approval column) counts as approved.
        """
        return self.approved is not False

    @property
    def is_banned(self):
        """True when an admin has banned this account."""
        return self.banned is True

    def set_password(self, raw_password):
        """Hash `raw_password` with a salted, slow KDF and store the hash.

        The plain password itself is never stored or logged.
        """
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Return True if `raw_password` matches the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def generate_password_reset_otp(self):
        """Create a fresh, time-limited 6-digit password-reset code and
        return it. Overwrites any previous unused code, so requesting a
        new one invalidates whatever was sent before."""
        otp = "{:06d}".format(secrets.randbelow(1_000_000))
        self.password_reset_otp = otp
        self.password_reset_otp_expires_at = (
            datetime.utcnow() + PASSWORD_RESET_OTP_LIFETIME)
        return otp

    def consume_password_reset_otp(self, otp):
        """If `otp` matches this user's current, unexpired reset code,
        clear it (so it can't be reused) and return True. Returns False
        on any mismatch/expiry/missing-code — the caller is responsible
        for rate-limiting attempts, since a 6-digit code is only safe
        against online guessing with that in place."""
        if not self.password_reset_otp or not otp:
            return False
        if not secrets.compare_digest(self.password_reset_otp, otp):
            return False
        if (self.password_reset_otp_expires_at is None
                or datetime.utcnow() > self.password_reset_otp_expires_at):
            return False
        self.password_reset_otp = None
        self.password_reset_otp_expires_at = None
        return True

    def public_dict(self):
        """Same as to_dict(), but never includes the password hash or the
        raw password-reset code.

        Use this (not to_dict()) whenever serializing a user for an API
        response. to_dict() itself must keep including every field —
        FileStorage round-trips objects to disk through it, so stripping
        fields there would silently lose them on every reload.
        """
        data = self.to_dict()
        data.pop("password_hash", None)
        data.pop("password_reset_otp", None)
        data.pop("password_reset_otp_expires_at", None)
        data.pop("session_epoch", None)
        return data
