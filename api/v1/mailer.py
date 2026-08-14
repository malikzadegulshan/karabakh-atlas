#!/usr/bin/python3
"""Sends transactional email (currently just verification emails) over
SMTP — Gmail's by default, but any standard SMTP/STARTTLS server works.

Falls back to printing the message when KBA_SMTP_* isn't configured, so
registration/verification stay fully testable in local dev without a
real mail account.
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _smtp_config():
    host = os.environ.get("KBA_SMTP_HOST")
    user = os.environ.get("KBA_SMTP_USER")
    password = os.environ.get("KBA_SMTP_PASSWORD")
    if not (host and user and password):
        return None
    return {
        "host": host,
        "port": int(os.environ.get("KBA_SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "from_addr": os.environ.get("KBA_SMTP_FROM", user),
    }


def send_email(to_addr, subject, body):
    """Send a plain-text email, or print it to stderr if SMTP isn't
    configured. Never raises — a mail failure shouldn't break the
    request that triggered it (e.g. registration should still succeed
    even if the verification email couldn't be sent).
    """
    config = _smtp_config()
    if config is None:
        logger.info(
            "KBA_SMTP_* not configured — printing email instead of "
            "sending it:\n  To: %s\n  Subject: %s\n  Body:\n%s",
            to_addr, subject, body,
        )
        return True

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = config["from_addr"]
    message["To"] = to_addr

    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=10) as smtp:
            smtp.starttls()
            smtp.login(config["user"], config["password"])
            smtp.sendmail(config["from_addr"], [to_addr], message.as_string())
        return True
    except (smtplib.SMTPException, OSError) as error:
        logger.error("Failed to send email to %s: %s", to_addr, error)
        return False
