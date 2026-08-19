#!/usr/bin/python3
"""Tests for api.v1.mailer.send_email (the Resend-backed mailer)."""
import json
import unittest
import urllib.error
from unittest.mock import patch, MagicMock
from api.v1 import mailer


class TestMailer(unittest.TestCase):
    """Unit tests against send_email() directly, not through a view."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_without_api_key_prints_instead_of_sending(self, mock_urlopen):
        """No RESEND_API_KEY -> logged, not sent, and still returns True
        (a missing config shouldn't fail the caller's request)."""
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertTrue(result)
        mock_urlopen.assert_not_called()

    @patch.dict("os.environ", {"RESEND_API_KEY": "test-key-123"}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_with_api_key_posts_to_resend(self, mock_urlopen):
        """A configured key sends a real request to Resend's API with the
        right auth header and payload."""
        mock_urlopen.return_value.__enter__.return_value = MagicMock()
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertTrue(result)

        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, mailer.RESEND_API_URL)
        self.assertEqual(
            request.get_header("Authorization"), "Bearer test-key-123")
        body = json.loads(request.data)
        self.assertEqual(body["to"], ["someone@example.com"])
        self.assertEqual(body["subject"], "Subject")
        self.assertEqual(body["text"], "Body")
        self.assertEqual(body["from"], mailer.DEFAULT_FROM)

    @patch.dict("os.environ", {
        "RESEND_API_KEY": "test-key-123",
        "RESEND_FROM": "Custom <custom@example.com>",
    }, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_resend_from_overrides_default_sender(self, mock_urlopen):
        """RESEND_FROM, when set, replaces the default sender address."""
        mock_urlopen.return_value.__enter__.return_value = MagicMock()
        mailer.send_email("someone@example.com", "Subject", "Body")
        body = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertEqual(body["from"], "Custom <custom@example.com>")

    @patch.dict("os.environ", {"RESEND_API_KEY": "test-key-123"}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_network_error_is_caught_and_returns_false(self, mock_urlopen):
        """A connection-level failure (e.g. the network-unreachable error
        that motivated this mailer in the first place) is caught, logged,
        and reported back as a plain False — never raised."""
        mock_urlopen.side_effect = OSError("Network is unreachable")
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)

    @patch.dict("os.environ", {"RESEND_API_KEY": "test-key-123"}, clear=True)
    @patch("api.v1.mailer.urllib.request.urlopen")
    def test_http_error_is_caught_and_returns_false(self, mock_urlopen):
        """An HTTP-level failure (bad API key, validation error, ...) is
        caught the same way — HTTPError is a URLError subclass."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            mailer.RESEND_API_URL, 401, "Unauthorized", {}, None)
        result = mailer.send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
