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


DANGEROUS_TAG_RE = re.compile(
    r"<\s*/?\s*(?:script|img|iframe|object|embed|svg|style|link|meta|"
    r"applet|form|input|button|base|video|audio)\b",
    re.IGNORECASE)
EVENT_HANDLER_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)
SCRIPT_URI_RE = re.compile(
    r"(?:javascript|vbscript|data\s*:\s*text/html)\s*:", re.IGNORECASE)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]\r\n]{0,500}\]\([^)\r\n]{0,2000}\)")
EXECUTABLE_REF_RE = re.compile(
    r"\b[a-zA-Z0-9_\-]+\.(?:exe|bat|cmd|sh|vbs|scr|msi|dll|apk|bin|elf|"
    r"ps1|com|pif|jar|scr)\b",
    re.IGNORECASE)
EXECUTABLE_URL_RE = re.compile(
    r"https?://[^\s?#]+\.(?:exe|bat|cmd|sh|vbs|scr|msi|dll|apk|bin|elf|ps1|"
    r"com|pif|jar|scr)(?:[?#\s]|$)",
    re.IGNORECASE)
BIDI_OVERRIDE_RE = re.compile(r"[\u202A-\u202E\u2066-\u2069]")
NAME_SPECIAL_RE = re.compile(r"[<>{}\\]|\bhttps?://")


def require_safe_text(data, field, max_length=MAX_TEXT_LENGTH):
    """Raise ValidationError if data[field] is empty, overlength, or
    contains suspicious code, HTML/script tags, executable links, embedded
    images, or control characters."""
    require_non_empty_string(data, field, max_length=max_length)
    value = data[field]

    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ValidationError(
            "{} contains invalid control characters".format(field))

    if BIDI_OVERRIDE_RE.search(value):
        raise ValidationError(
            "{} contains invalid bidirectional formatting".format(field))

    if DANGEROUS_TAG_RE.search(value):
        raise ValidationError(
            "{} contains disallowed HTML or script tags".format(field))

    if EVENT_HANDLER_RE.search(value):
        raise ValidationError(
            "{} contains disallowed script attributes".format(field))

    if SCRIPT_URI_RE.search(value):
        raise ValidationError(
            "{} contains disallowed script URIs".format(field))

    if MARKDOWN_IMAGE_RE.search(value):
        raise ValidationError(
            "{} cannot contain embedded images".format(field))

    if EXECUTABLE_URL_RE.search(value) or EXECUTABLE_REF_RE.search(value):
        raise ValidationError(
            "{} cannot contain links to or names of executable files"
            .format(field))


def require_safe_name(data, field="name", max_length=MAX_NAME_LENGTH):
    """Validate that data[field] is a clean person or entity name.

    Names cannot contain tags, special bracket characters, or URLs.
    """
    require_safe_text(data, field, max_length=max_length)
    value = data[field]
    if NAME_SPECIAL_RE.search(value):
        raise ValidationError(
            "{} cannot contain special characters or URLs".format(field))


def optional_string(data, field, max_length=MAX_TEXT_LENGTH):
    """Raise ValidationError if data[field] is present but not a valid
    string."""
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
    """Raise ValidationError unless data[field] is a number in
    [minimum, maximum]."""
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("{} must be a number".format(field))
    if not (minimum <= value <= maximum):
        raise ValidationError(
            "{} must be between {} and {}".format(field, minimum, maximum))


def require_integer_in_range(data, field, minimum, maximum):
    """Raise ValidationError unless data[field] is an integer in
    [minimum, maximum]."""
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("{} must be an integer".format(field))
    if not (minimum <= value <= maximum):
        raise ValidationError(
            "{} must be between {} and {}".format(field, minimum, maximum))


ALLOWED_I18N_LANGS = {"en", "az", "tr", "ru"}


def optional_i18n_dict(data, field, max_length=MAX_TEXT_LENGTH):
    """Raise ValidationError if data[field] is present but not a
    dict mapping supported language codes to bounded safe strings."""
    if field not in data or data[field] is None:
        return
    value = data[field]
    if not isinstance(value, dict):
        raise ValidationError("{} must be an object".format(field))
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, str):
            raise ValidationError(
                "{} entries must map language codes to strings".format(field))
        if key not in ALLOWED_I18N_LANGS:
            raise ValidationError(
                "{} contains unsupported language code".format(field))
        if len(val) > max_length:
            raise ValidationError(
                "{} entries must be at most {} characters".format(
                    field, max_length))
        if BIDI_OVERRIDE_RE.search(val) or any(
            ord(c) < 32 and c not in "\n\r\t" for c in val
        ):
            raise ValidationError(
                "{} contains invalid control characters".format(field))


def optional_enum(data, field, choices):
    """Raise ValidationError if data[field] is present but not in choices."""
    if field not in data or data[field] is None:
        return
    # A list/object here would make the membership test below raise
    # TypeError (unhashable) and surface as a 500 instead of a 400.
    if not isinstance(data[field], str) or data[field] not in choices:
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
