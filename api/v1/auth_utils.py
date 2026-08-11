#!/usr/bin/python3
"""Session-based authentication helpers shared by the API views."""
import time
from functools import wraps
from flask import session, jsonify
from models import storage
from models.user import User

LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300

# In-memory, per-process. Good enough to blunt naive password-guessing
# scripts on a single small deployment; a multi-worker/multi-instance
# setup would need a shared store (e.g. Redis) to enforce the limit
# consistently across processes.
_login_attempts = {}


def _recent_failures(key, now):
    return [t for t in _login_attempts.get(key, [])
            if now - t < LOGIN_WINDOW_SECONDS]


def is_login_rate_limited(key):
    """Return True if `key` (e.g. "<ip>:<email>") has failed too many
    logins within the current window."""
    now = time.time()
    attempts = _recent_failures(key, now)
    _login_attempts[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def record_login_failure(key):
    """Record a failed login attempt against `key`."""
    now = time.time()
    attempts = _recent_failures(key, now)
    attempts.append(now)
    _login_attempts[key] = attempts


def clear_login_failures(key):
    """Forget recorded failures for `key` after a successful login."""
    _login_attempts.pop(key, None)


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
