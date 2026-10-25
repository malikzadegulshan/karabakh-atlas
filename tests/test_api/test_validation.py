#!/usr/bin/python3
"""Tests for input validation and security filters in api.v1.validation."""
import unittest
from api.v1.validation import (
    ValidationError,
    require_safe_name,
    require_safe_text,
)


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


if __name__ == "__main__":
    unittest.main()
