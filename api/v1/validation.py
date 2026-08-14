#!/usr/bin/python3
"""Shared request-body validation helpers for the API views."""
import re
from urllib.parse import urlsplit

MAX_NAME_LENGTH = 128
MAX_TEXT_LENGTH = 5000
MAX_SHORT_TEXT_LENGTH = 500

# Deliberately simple (not a full RFC 5322 parser) — good enough to catch
# typos/garbage input; the account is only ever reachable by whoever set
# the password, so a stricter regex buys little real security here.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class ValidationError(Exception):
    """Raised when request data fails validation; carries a user message."""

    def __init__(self, message):
        """Store the human-readable validation failure message."""
        super().__init__(message)
        self.message = message


def require_non_empty_string(data, field, max_length=MAX_NAME_LENGTH):
    """Raise ValidationError unless data[field] is a non-empty string."""
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("{} must be a non-empty string".format(field))
    if len(value) > max_length:
        raise ValidationError(
            "{} must be at most {} characters".format(field, max_length))


def optional_string(data, field, max_length=MAX_TEXT_LENGTH):
    """Raise ValidationError if data[field] is present but not a valid string."""
    if field not in data or data[field] is None:
        return
    value = data[field]
    if not isinstance(value, str):
        raise ValidationError("{} must be a string".format(field))
    if len(value) > max_length:
        raise ValidationError(
            "{} must be at most {} characters".format(field, max_length))


SAFE_URL_SCHEMES = {"http", "https"}


def optional_url(data, field, max_length=MAX_TEXT_LENGTH):
    """Raise ValidationError if data[field] is present but not an
    http(s) URL.

    Rejects any other scheme outright — most importantly javascript:,
    which the frontend renders straight into an <a href="..."> for
    website links (city.website in buildDetailCardHtml). Without this,
    a stored value there is a stored-XSS payload against every visitor
    who views that place's Website button, not just whoever entered it.
    """
    if field not in data or data[field] is None:
        return
    value = data[field]
    if not isinstance(value, str):
        raise ValidationError("{} must be a string".format(field))
    if len(value) > max_length:
        raise ValidationError(
            "{} must be at most {} characters".format(field, max_length))
    scheme = urlsplit(value.strip()).scheme.lower()
    if scheme not in SAFE_URL_SCHEMES:
        raise ValidationError(
            "{} must be an http:// or https:// URL".format(field))


def require_number_in_range(data, field, minimum, maximum):
    """Raise ValidationError unless data[field] is a number in [minimum, maximum]."""
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("{} must be a number".format(field))
    if not (minimum <= value <= maximum):
        raise ValidationError(
            "{} must be between {} and {}".format(field, minimum, maximum))


def optional_i18n_dict(data, field):
    """Raise ValidationError if data[field] is present but not a
    dict mapping string language codes to string values."""
    if field not in data or data[field] is None:
        return
    value = data[field]
    if not isinstance(value, dict):
        raise ValidationError("{} must be an object".format(field))
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, str):
            raise ValidationError(
                "{} entries must map language codes to strings".format(field))


def optional_enum(data, field, choices):
    """Raise ValidationError if data[field] is present but not in choices."""
    if field not in data or data[field] is None:
        return
    if data[field] not in choices:
        raise ValidationError(
            "{} must be one of: {}".format(field, ", ".join(sorted(choices))))


def require_email(data, field="email"):
    """Raise ValidationError unless data[field] looks like an email address."""
    value = data.get(field)
    if not isinstance(value, str) or not EMAIL_RE.match(value.strip()):
        raise ValidationError("{} must be a valid email address".format(field))
    if len(value) > 254:
        raise ValidationError(
            "{} must be at most 254 characters".format(field))


def require_password(data, field="password"):
    """Raise ValidationError unless data[field] is a usable password."""
    value = data.get(field)
    if not isinstance(value, str):
        raise ValidationError("{} must be a string".format(field))
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            "{} must be at least {} characters".format(
                field, MIN_PASSWORD_LENGTH))
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValidationError(
            "{} must be at most {} characters".format(
                field, MAX_PASSWORD_LENGTH))


def only_allowed_fields(data, allowed):
    """Raise ValidationError if data contains keys outside `allowed`."""
    unexpected = set(data) - allowed
    if unexpected:
        raise ValidationError(
            "Unexpected field(s): {}".format(", ".join(sorted(unexpected))))
