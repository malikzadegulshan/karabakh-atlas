#!/usr/bin/python3
"""Standalone unit tests for validation, Brevo mailer, and CSV parser."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import urllib.error
from unittest.mock import MagicMock, patch
from api.v1 import mailer
from api.v1.validation import (
    ValidationError,
    require_safe_name,
    require_safe_text,
)

SCRIPT = Path(__file__).with_name("csv_test.js")


class TestSecurityValidation(unittest.TestCase):
    """Ensure text and name validators reject suspicious code and payloads."""

    def test_clean_text_accepted(self):
        """Normal text passes validation."""
        valid_samples = [
            "I grew up in Shusha and want to share memories.",
            "Historical landmarks from 1992-2020.",
            "Dadivank monastery (Kalbajar region) — beautiful place!",
            "Salam! Qarabağ haqqında məlumat toplamaq istəyirəm.",
            "Привет! Хочу поделиться фотографиями.",
        ]
        for sample in valid_samples:
            require_safe_text({"field": sample}, "field")
            require_safe_name({"name": "Leyla Aliyeva"}, "name")

    def test_rejects_html_and_script_tags(self):
        """HTML, script, img, iframe, and svg tags are rejected."""
        payloads = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<IMG SRC='http://evil.com/logger.png'>",
            "<iframe src='http://evil.com'></iframe>",
            "<svg onload=alert(1)>",
            "<style>body{display:none}</style>",
            "<embed src='exploit.swf'>",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_rejects_event_handlers(self):
        """Standalone event handler strings are rejected."""
        payloads = [
            "text onclick=alert(1)",
            "test onmouseover=doBadThing()",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_rejects_script_uris(self):
        """javascript: and data: URIs are rejected."""
        payloads = [
            "javascript:void(0)",
            "JAVASCRIPT:alert(document.cookie)",
            "data:text/html,<script>alert(1)</script>",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_rejects_markdown_image_injections(self):
        """Markdown image syntax (![alt](url)) is rejected."""
        payloads = [
            "![tracker](https://evil.com/pixel.png)",
            "Look at this: ![photo](http://attacker.com/img.jpg)",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_rejects_executable_references_and_links(self):
        """Executable extensions (.exe, .sh, .bat, etc.) are rejected."""
        payloads = [
            "Download this: http://evil.com/installer.exe",
            "Run payload.sh to see photos",
            "Here is update.bat",
            "check file.vbs please",
            "app.apk installer",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_rejects_bidi_overrides(self):
        """Trojan Source bidirectional Unicode overrides are rejected."""
        payloads = [
            "doc\u202Efdp.exe",
            "test\u202Ahack",
            "reverse\u2066text",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_rejects_null_bytes_and_control_chars(self):
        """Null bytes and raw ASCII control characters are rejected."""
        payloads = [
            "bad\x00data",
            "hello\x07bell",
            "test\x1b[31mcolor",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_text({"field": p}, "field")

    def test_safe_name_rejects_special_chars_and_urls(self):
        """Names cannot contain angle brackets, curly braces, or URLs."""
        payloads = [
            "<Admin>",
            "User {admin}",
            "http://evil.com",
            "https://phish.com",
            "Name\\Escape",
        ]
        for p in payloads:
            with self.assertRaises(ValidationError):
                require_safe_name({"name": p}, "name")


class TestMailer(unittest.TestCase):
    """Unit tests against send_email() directly, not through a view."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_without_config_prints_instead_of_sending(self, mock_urlopen):
        """Missing BREVO_API_KEY or BREVO_SENDER_EMAIL -> logged, not
        sent, and still returns True (a missing config shouldn't fail
        the caller's request)."""
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertTrue(result)
        mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {"BREVO_API_KEY": "xkeysib-123"}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_without_sender_email_prints_instead_of_sending(
            self, mock_urlopen):
        """BREVO_API_KEY without BREVO_SENDER_EMAIL also falls back to
        logging rather than sending an invalid payload."""
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertTrue(result)
        mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_with_config_posts_to_brevo(self, mock_urlopen):
        """Configured key + sender sends a POST request to Brevo's API
        with the right api-key header and JSON payload."""
        mock_urlopen.return_value.__enter__.return_value = MagicMock()
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertTrue(result)

        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, mailer.BREVO_API_URL)
        self.assertEqual(request.get_header("Api-key"), "xkeysib-test-123")
        self.assertEqual(
            request.get_header("User-agent"), "karabakh-atlas-mailer/1.0")
        body = json.loads(request.data)
        self.assertEqual(body["to"], [{"email": "someone@example.com"}])
        self.assertEqual(body["subject"], "Subject")
        self.assertEqual(body["textContent"], "Body")
        self.assertEqual(body["sender"], {
            "name": mailer.DEFAULT_SENDER_NAME,
            "email": "sender@example.com",
        })

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
        "BREVO_SENDER_NAME": "Custom Sender",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_sender_name_overrides_default_name(self, mock_urlopen):
        """BREVO_SENDER_NAME, when set, replaces the default sender name."""
        mock_urlopen.return_value.__enter__.return_value = MagicMock()
        mailer.send_email("someone@example.com", "Subject", "Body")
        body = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(body["sender"], {
            "name": "Custom Sender",
            "email": "sender@example.com",
        })

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "Display Name <sender@example.com>",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_formatted_sender_email_is_parsed(self, mock_urlopen):
        """'Name <email>' in BREVO_SENDER_EMAIL is split cleanly into
        Brevo's sender.name and sender.email fields."""
        mock_urlopen.return_value.__enter__.return_value = MagicMock()
        mailer.send_email("someone@example.com", "Subject", "Body")
        body = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(body["sender"], {
            "name": "Display Name",
            "email": "sender@example.com",
        })

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_network_error_is_caught_and_returns_false(self, mock_urlopen):
        """A connection-level failure is caught, logged, and reported
        back as a plain False — never raised."""
        mock_urlopen.side_effect = OSError("Network is unreachable")
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_http_error_is_caught_and_returns_false(self, mock_urlopen):
        """An HTTP-level failure (bad API key, validation error, ...) is
        caught the same way — HTTPError is a URLError subclass."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            mailer.BREVO_API_URL, 401, "Unauthorized", {}, None)
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    @patch("api.v1.mailer.logger")
    def test_http_error_body_is_logged(self, mock_logger, mock_urlopen):
        """The response body (Brevo's actual rejection reason) is read
        and logged, not just the bare status line."""
        body = b'{"code": "invalid_parameter", "message": "Sender not valid"}'
        mock_urlopen.side_effect = urllib.error.HTTPError(
            mailer.BREVO_API_URL, 400, "Bad Request", {}, io.BytesIO(body))
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)
        logged_message = mock_logger.error.call_args[0][0]
        logged_args = mock_logger.error.call_args[0][1:]
        rendered = logged_message % logged_args
        self.assertIn("400", rendered)
        self.assertIn("Sender not valid", rendered)

    @patch.dict("os.environ", {"KBA_ENV": "prod"}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    @patch("api.v1.mailer.logger")
    def test_production_unconfigured_does_not_log_otp_body(
            self, mock_logger, mock_urlopen):
        """CWE-532: If Brevo is unconfigured in production, never print
        plaintext password-reset OTPs into production server logs."""
        secret_body = "Your password reset code is: 948271"
        result = mailer.send_email(
            "someone@example.com", "Reset", secret_body)
        self.assertFalse(result)
        mock_urlopen.assert_not_called()
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_called_once()
        warn_args = mock_logger.warning.call_args[0]
        rendered = warn_args[0] % warn_args[1:]
        self.assertNotIn("948271", rendered)

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "bad\r\nInjected-Header: pwned",
        "BREVO_SENDER_EMAIL": "sender@example.com",
        "KBA_ENV": "prod",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_crlf_in_api_key_is_rejected_without_raising(self, mock_urlopen):
        """CWE-113: Control/newline characters in BREVO_API_KEY are
        rejected safely without raising ValueError."""
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)
        mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "Alice <alice@example.com> <evil@attacker.org>",
        "KBA_ENV": "prod",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_multi_bracket_sender_injection_is_rejected(self, mock_urlopen):
        """CVE-2023-27043: Multiple angle-bracket addresses in
        BREVO_SENDER_EMAIL are rejected."""
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)
        mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_invalid_recipient_or_crlf_subject_rejected(self, mock_urlopen):
        """Header/recipient injection in to_addr or subject is rejected
        before any outbound request is constructed."""
        self.assertFalse(mailer.send_email(
            "victim@example.com\r\nBcc: spy@evil.com", "Subject", "Body"))
        self.assertFalse(mailer.send_email(
            "someone@example.com", "Subj\r\nect", "Body"))
        mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {
        "BREVO_API_KEY": "xkeysib-test-123",
        "BREVO_SENDER_EMAIL": "sender@example.com",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_html_body_included_when_provided(self, mock_urlopen):
        """When html_body is passed, Brevo receives both textContent and
        htmlContent."""
        mock_urlopen.return_value.__enter__.return_value = MagicMock()
        result = mailer.send_email(
            "someone@example.com", "Subject", "Plain body",
            html_body="<p>HTML body</p>",
        )
        self.assertTrue(result)
        body = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(body["textContent"], "Plain body")
        self.assertEqual(body["htmlContent"], "<p>HTML body</p>")

    def test_sanitize_email_name_strips_control_and_bidi_chars(self):
        """Control characters and Unicode BiDi overrides are stripped from
        display names before email interpolation."""
        raw = "Alice\r\n\u202e<script>alert(1)</script>"
        cleaned = mailer.sanitize_email_name(raw)
        self.assertNotIn("\r", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertNotIn("\u202e", cleaned)
        self.assertEqual(mailer.sanitize_email_name(""), "Member")
        self.assertEqual(mailer.sanitize_email_name(None), "Member")

    def test_build_password_reset_email_supports_all_languages(self):
        """Password-reset email templates render in en, az, tr, and ru
        and escape HTML characters in the recipient name."""
        for lang, expected_word in (
            ("en", "Verification Code"),
            ("az", "Təsdiq Kodu"),
            ("tr", "Doğrulama Kodu"),
            ("ru", "Код подтверждения"),
        ):
            subj, text_body, html_body = mailer.build_password_reset_email(
                "Aysel <script>", "123456", lang=lang)
            self.assertTrue(subj)
            self.assertIn("123456", text_body)
            self.assertIn("123456", html_body)
            self.assertIn(expected_word, html_body)
            self.assertIn("Aysel &lt;script&gt;", html_body)
            self.assertNotIn("<script>", html_body)

    def test_build_welcome_email_supports_all_languages(self):
        """Welcome email templates render in en, az, tr, and ru."""
        for lang, expected_phrase in (
            ("en", "Welcome to the Community"),
            ("az", "İcmamıza Xoş Gəlmisiniz"),
            ("tr", "Topluluğumuza Hoş Geldiniz"),
            ("ru", "Добро пожаловать в сообщество"),
        ):
            subj, text_body, html_body = mailer.build_welcome_email(
                "Rəşad", lang=lang)
            self.assertTrue(subj)
            self.assertIn("Rəşad", text_body)
            self.assertIn(expected_phrase, html_body)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestCsvImportParser(unittest.TestCase):
    """frontend/csv.js: delimiters, quoting, BOM, aliases, categories."""

    def test_csv_parser_and_mapper(self):
        result = subprocess.run(
            ["node", str(SCRIPT)], capture_output=True, text=True,
            timeout=60)
        self.assertEqual(
            result.returncode, 0,
            "csv_test.js failed:\n{}{}".format(result.stdout, result.stderr))
        self.assertIn("all passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
