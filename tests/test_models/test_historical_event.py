#!/usr/bin/python3
"""Unit tests for models.historical_event.HistoricalEvent."""
import unittest
from models.base_model import BaseModel
from models.historical_event import HistoricalEvent


class TestHistoricalEvent(unittest.TestCase):
    """Test cases for the HistoricalEvent class."""

    def test_is_subclass_of_base_model(self):
        """HistoricalEvent inherits from BaseModel."""
        event = HistoricalEvent()
        self.assertIsInstance(event, BaseModel)

    def test_fields_can_be_set(self):
        """Title, year, and coordinates can be assigned and read back."""
        event = HistoricalEvent()
        event.title = "Sample Event"
        event.year = 2020
        event.latitude = 39.75
        event.longitude = 46.75
        self.assertEqual(event.title, "Sample Event")
        self.assertEqual(event.year, 2020)
        self.assertEqual(event.latitude, 39.75)
        self.assertEqual(event.longitude, 46.75)


if __name__ == "__main__":
    unittest.main()
