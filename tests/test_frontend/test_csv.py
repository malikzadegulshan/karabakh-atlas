#!/usr/bin/python3
"""Runs the Node-based tests for frontend/csv.js (the admin CSV import's
parser and column mapper), so the Python suite — and CI — cover it."""
import shutil
import subprocess
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("csv_test.js")


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
