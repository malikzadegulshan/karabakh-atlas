#!/usr/bin/python3
"""Session-based authentication helpers shared by the API views."""
import time
from functools import wraps
from flask import session, jsonify
from models import storage
from models.user import User


class RateLimiter:
    """A simple fixed-window rate limiter, keyed by an arbitrary string.

    In-memory, per-process. Good enough to blunt naive abuse (password
    guessing, verification-email spam) on a single small deployment; a
    multi-worker/multi-instance setup would need a shared store (e.g.
    Redis) to enforce the limit consistently across processes.
    """

    def __init__(self, max_attempts, window_seconds):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts = {}

    def _recent(self, key, now):
        return [t for t in self._attempts.get(key, [])
                if now - t < self.window_seconds]

    def is_limited(self, key):
        """Return True if `key` has hit the limit within the window."""
        now = time.time()
        attempts = self._recent(key, now)
        self._attempts[key] = attempts
        return len(attempts) >= self.max_attempts

    def record(self, key):
        """Record an attempt against `key`."""
        now = time.time()
        attempts = self._recent(key, now)
        attempts.append(now)
        self._attempts[key] = attempts

    def clear(self, key):
        """Forget recorded attempts for `key` (e.g. after success)."""
        self._attempts.pop(key, None)


login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
resend_verification_limiter = RateLimiter(max_attempts=3, window_seconds=3600)
# Blunts a single account flooding the moderation queue with spam —
# generous enough for genuine back-and-forth use, tight enough that
# scripting registrations-then-posts doesn't scale.
forum_post_limiter = RateLimiter(max_attempts=5, window_seconds=600)

# Kept as module-level names for backward compatibility with existing
# call sites/tests.
LOGIN_MAX_ATTEMPTS = login_limiter.max_attempts
LOGIN_WINDOW_SECONDS = login_limiter.window_seconds


def is_login_rate_limited(key):
    """Return True if `key` (e.g. "<ip>:<email>") has failed too many
    logins within the current window."""
    return login_limiter.is_limited(key)


def record_login_failure(key):
    """Record a failed login attempt against `key`."""
    login_limiter.record(key)


def clear_login_failures(key):
    """Forget recorded failures for `key` after a successful login."""
    login_limiter.clear(key)


def get_current_user():
    """Return the logged-in User for this request's session, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return storage.all(User).get("User.{}".format(user_id))


def login_required(f):
    """View decorator: reject with 401 unless a session user is logged in."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if get_current_user() is None:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """View decorator: reject unless the session user has the admin role."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "Login required"}), 401
        if user.role != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        return f(*args, **kwargs)
    return wrapper
