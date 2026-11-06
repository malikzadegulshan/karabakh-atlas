#!/usr/bin/python3
"""Sends transactional email (password-reset codes)
via the Brevo HTTP API (https://www.brevo.com).

Falls back to printing the message when BREVO_API_KEY or
BREVO_SENDER_EMAIL isn't configured, so password reset stays fully
testable in local dev without a real account.

Why Brevo over HTTPS instead of SMTP or Resend:
- PaaS hosts commonly block outbound SMTP ports (25/465/587) on
  free/starter tiers while leaving outbound HTTPS (443) open.
- Resend requires owning and verifying a custom DNS domain before it
  will deliver to anyone other than the account owner's own address.
- Brevo's free tier (300 emails/day) lets you verify a single personal
  sender email address (e.g. a Gmail or Outlook address) via a
  confirmation link and send to any recipient without owning a domain.
"""
from email.utils import parseaddr
import json
import logging
import os
import re
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
DEFAULT_SENDER_NAME = "Karabakh Atlas"
MAX_EMAIL_LENGTH = 254
MAX_SENDER_NAME_LENGTH = 128
MAX_ERROR_LOG_CHARS = 500
_SAFE_EMAIL_RE = re.compile(r"^[^@\s<>\"']+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _has_control_chars(value):
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _is_valid_email(addr):
    return (
        isinstance(addr, str)
        and 3 <= len(addr) <= MAX_EMAIL_LENGTH
        and not _has_control_chars(addr)
        and bool(_SAFE_EMAIL_RE.match(addr))
    )


def _is_production():
    env = (os.environ.get("KBA_ENV") or "").strip().lower()
    return env in ("prod", "production") or bool(os.environ.get("RENDER"))


def _sanitize_for_log(text, max_len=MAX_ERROR_LOG_CHARS):
    cleaned = "".join(
        " " if (ord(ch) < 32 or ord(ch) == 127) else ch
        for ch in str(text)
    )
    return cleaned[:max_len]


def _brevo_config():
    api_key = (os.environ.get("BREVO_API_KEY") or "").strip()
    raw_sender = (os.environ.get("BREVO_SENDER_EMAIL") or "").strip()
    if not api_key or not raw_sender:
        return None
    # Reject control or non-ASCII chars in API key (HTTP header safety)
    if any(ord(ch) <= 32 or ord(ch) >= 127 for ch in api_key):
        logger.error("Invalid characters in BREVO_API_KEY")
        return None
    # Guard against CVE-2023-27043 / multi-angle-bracket address injection
    if _has_control_chars(raw_sender) or raw_sender.count("<") > 1:
        logger.error("Invalid BREVO_SENDER_EMAIL configuration")
        return None
    parsed_name, sender_email = parseaddr(raw_sender)
    if not _is_valid_email(sender_email):
        logger.error("Invalid BREVO_SENDER_EMAIL address")
        return None
    sender_name = (
        os.environ.get("BREVO_SENDER_NAME") or ""
    ).strip() or parsed_name or DEFAULT_SENDER_NAME
    if _has_control_chars(sender_name):
        logger.error("Invalid characters in BREVO_SENDER_NAME")
        return None
    return {
        "api_key": api_key,
        "sender_email": sender_email,
        "sender_name": sender_name[:MAX_SENDER_NAME_LENGTH],
    }


def send_email(to_addr, subject, body):
    """Send a plain-text email, or log it if Brevo isn't configured.
    Never raises — a mail failure shouldn't break the request that
    triggered it (e.g. a password-reset request should still return
    200 even if the email couldn't be sent).
    """
    if not _is_valid_email(to_addr) or not isinstance(subject, str):
        logger.error("Refusing to send email to invalid recipient")
        return False
    if _has_control_chars(subject) or not isinstance(body, str):
        logger.error("Refusing to send email with invalid subject/body")
        return False

    config = _brevo_config()
    if config is None:
        if _is_production():
            # Never log plaintext password-reset OTP bodies in production
            logger.warning(
                "BREVO_API_KEY / BREVO_SENDER_EMAIL not configured in "
                "production — dropping email to %s",
                _sanitize_for_log(to_addr, MAX_EMAIL_LENGTH),
            )
            return False
        logger.info(
            "BREVO_API_KEY / BREVO_SENDER_EMAIL not configured — "
            "printing email instead of sending it:\n"
            "  To: %s\n  Subject: %s\n  Body:\n%s",
            to_addr, subject, body,
        )
        return True

    payload = json.dumps({
        "sender": {
            "name": config["sender_name"],
            "email": config["sender_email"],
        },
        "to": [{"email": to_addr}],
        "subject": subject,
        "textContent": body,
    }).encode("utf-8")
    request = urllib.request.Request(
        BREVO_API_URL,
        data=payload,
        method="POST",
        headers={
            "api-key": config["api_key"],
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Avoid generic "Python-urllib/x.y" User-Agent blocks on
            # Cloudflare-fronted APIs (error 1010).
            "User-Agent": "karabakh-atlas-mailer/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            pass
        return True
    except urllib.error.HTTPError as error:
        detail = ""
        if error.fp is not None:
            raw = error.fp.read(MAX_ERROR_LOG_CHARS * 2)
            detail = _sanitize_for_log(raw.decode("utf-8", "replace"))
        logger.error(
            "Failed to send email to %s: HTTP %s %s%s",
            _sanitize_for_log(to_addr, MAX_EMAIL_LENGTH),
            error.code,
            _sanitize_for_log(error.reason, 128),
            " - {}".format(detail) if detail else "",
        )
        return False
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error(
            "Failed to send email to %s: %s",
            _sanitize_for_log(to_addr, MAX_EMAIL_LENGTH),
            _sanitize_for_log(error),
        )
        return False
