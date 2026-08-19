#!/usr/bin/python3
"""Sends transactional email (verification links, password-reset codes)
via the Resend API (https://resend.com).

Falls back to printing the message when RESEND_API_KEY isn't
configured, so registration/verification/reset stay fully testable in
local dev without a real account.

This used to talk to Gmail over raw SMTP, but PaaS hosts commonly
block or restrict outbound SMTP ports (25/465/587) on free/starter
tiers to cut down on spam abuse, while leaving normal outbound HTTPS
wide open — that's exactly what broke delivery in production here
(a connection-level "Network is unreachable", not an auth failure).
An HTTP-based provider sidesteps the whole problem instead of chasing
which port might be open.
"""
import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
# Resend's own keyless sender for accounts that haven't verified a
# custom sending domain yet — works out of the box, good enough for
# getting this running before anyone bothers with domain verification.
DEFAULT_FROM = "Karabakh Atlas <onboarding@resend.dev>"


def _resend_config():
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return None
    return {
        "api_key": api_key,
        "from_addr": os.environ.get("RESEND_FROM", DEFAULT_FROM),
    }


def send_email(to_addr, subject, body):
    """Send a plain-text email, or print it to stderr if Resend isn't
    configured. Never raises — a mail failure shouldn't break the
    request that triggered it (e.g. registration should still succeed
    even if the verification email couldn't be sent).
    """
    config = _resend_config()
    if config is None:
        logger.info(
            "RESEND_API_KEY not configured — printing email instead of "
            "sending it:\n  To: %s\n  Subject: %s\n  Body:\n%s",
            to_addr, subject, body,
        )
        return True

    payload = json.dumps({
        "from": config["from_addr"],
        "to": [to_addr],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    request = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer {}".format(config["api_key"]),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            pass
        return True
    except urllib.error.HTTPError as error:
        detail = ""
        if error.fp is not None:
            detail = error.fp.read().decode("utf-8", "replace")
        logger.error(
            "Failed to send email to %s: HTTP %s %s%s",
            to_addr, error.code, error.reason,
            " - {}".format(detail) if detail else "",
        )
        return False
    except (urllib.error.URLError, OSError) as error:
        logger.error("Failed to send email to %s: %s", to_addr, error)
        return False
