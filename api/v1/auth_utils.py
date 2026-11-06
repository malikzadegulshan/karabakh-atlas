#!/usr/bin/python3
"""Session-based authentication helpers shared by the API views."""
import time
from functools import wraps
from flask import session, jsonify
from models import storage
from models.user import User


class RateLimiter:
    """A bounded fixed-window rate limiter, keyed by an arbitrary string.

    In-memory, per-process. Good enough to blunt naive abuse (password
    guessing, verification-email spam) on a single small deployment; a
    multi-worker/multi-instance setup would need a shared store (e.g.
    Redis) to enforce the limit consistently across processes.

    Tracks at most max_tracked_keys in memory, automatically pruning
    expired keys and evicting oldest entries to prevent memory
    exhaustion under high cardinality or random-key attacks.
    """

    def __init__(self, max_attempts, window_seconds, max_tracked_keys=5000):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_tracked_keys = max_tracked_keys
        self._attempts = {}

    def _recent(self, key, now):
        return [t for t in self._attempts.get(key, [])
                if now - t < self.window_seconds]

    def _prune(self, now):
        """Remove expired keys, and evict oldest if still over capacity."""
        expired = [
            k for k, timestamps in self._attempts.items()
            if not timestamps or now - timestamps[-1] >= self.window_seconds
        ]
        for k in expired:
            self._attempts.pop(k, None)
        if len(self._attempts) >= self.max_tracked_keys:
            sorted_keys = sorted(
                self._attempts.keys(),
                key=lambda k: self._attempts[k][-1] if self._attempts[k] else 0
            )
            to_remove = len(self._attempts) - self.max_tracked_keys + 1
            for k in sorted_keys[:to_remove]:
                self._attempts.pop(k, None)

    def is_limited(self, key):
        """Return True if `key` has hit the limit within the window.

        Cleans up empty or expired entries rather than holding empty
        lists in memory.
        """
        now = time.time()
        attempts = self._recent(key, now)
        if attempts:
            self._attempts[key] = attempts
        else:
            self._attempts.pop(key, None)
        return len(attempts) >= self.max_attempts

    def record(self, key):
        """Record an attempt against `key`."""
        now = time.time()
        if len(self._attempts) >= self.max_tracked_keys:
            self._prune(now)
        attempts = self._recent(key, now)
        attempts.append(now)
        self._attempts[key] = attempts

    def clear(self, key):
        """Forget recorded attempts for `key` (e.g. after success)."""
        self._attempts.pop(key, None)


login_limiter = RateLimiter(max_attempts=5, window_seconds=300)
# Aggregate per-IP login limiter: prevents credential stuffing / password
# spraying across hundreds or thousands of distinct emails from one IP.
login_ip_limiter = RateLimiter(max_attempts=30, window_seconds=900)
# Keyed by IP, not email — an unlimited registration endpoint is both a
# bulk-account-creation vector and a way to flood the admin's approval
# queue with junk requests. This doesn't stop one signup per genuine
# visitor; it stops scripting hundreds of them from one source.
register_limiter = RateLimiter(max_attempts=5, window_seconds=3600)
# Blunts a single account flooding the moderation queue with spam —
# generous enough for genuine back-and-forth use, tight enough that
# scripting registrations-then-posts doesn't scale.
forum_post_limiter = RateLimiter(max_attempts=5, window_seconds=600)
# Keyed by user id: a handful of reports is normal, hundreds is someone
# using the report button to flood the admin's review list.
report_limiter = RateLimiter(max_attempts=10, window_seconds=3600)
# Keyed by user id (or IP): prevents rapid image upload floods that could
# exhaust storage or server memory.
image_upload_limiter = RateLimiter(max_attempts=20, window_seconds=900)
# Keyed by IP (same reasoning as register_limiter): caps how many
# password-reset emails a single source can trigger.
password_reset_request_limiter = RateLimiter(
    max_attempts=5, window_seconds=3600)
# Keyed by "ip:email" (same convention as login's rate_key). A 6-digit
# OTP is only 1,000,000 possible values, so this — not the code's own
# secrecy — is what actually stops it from being guessed: 5 attempts
# per window, and the window matches the OTP's own 15-minute lifetime
# (see PASSWORD_RESET_OTP_LIFETIME in models/user.py), so exhausting
# the guess budget never outlasts the code it's guessing against.
password_reset_attempt_limiter = RateLimiter(
    max_attempts=5, window_seconds=900)

# Kept as module-level names for backward compatibility with existing
# call sites/tests.
LOGIN_MAX_ATTEMPTS = login_limiter.max_attempts
LOGIN_WINDOW_SECONDS = login_limiter.window_seconds


def is_login_rate_limited(key, ip=None):
    """Return True if `key` (e.g. "<ip>:<email>") or `ip` has failed too many
    logins within the current window."""
    if ip and login_ip_limiter.is_limited(ip):
        return True
    return login_limiter.is_limited(key)


def record_login_failure(key, ip=None):
    """Record a failed login attempt against `key` and optional `ip`."""
    login_limiter.record(key)
    if ip:
        login_ip_limiter.record(ip)


def clear_login_failures(key):
    """Forget recorded failures for `key` after a successful login."""
    login_limiter.clear(key)


def log_in(user):
    """Start a fresh session for `user`: any previous session data is
    dropped (no session fixation) and the user's current session epoch
    is recorded, so a later password reset can invalidate it."""
    session.clear()
    session["user_id"] = user.id
    session["epoch"] = user.session_epoch or 0


def get_current_user():
    """Return the logged-in User for this request's session, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = storage.all(User).get("User.{}".format(user_id))
    if user is None:
        return None
    # A password reset bumps the epoch, so cookies issued before it
    # (sessions on other devices, a stolen cookie) stop working.
    if session.get("epoch", 0) != (user.session_epoch or 0):
        return None
    # An account an admin hasn't approved yet or has banned never counts
    # as signed in, even if a session cookie exists for it.
    if not user.is_approved or user.is_banned:
        return None
    return user


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
