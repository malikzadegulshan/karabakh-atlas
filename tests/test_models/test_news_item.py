#!/usr/bin/python3
"""Unit tests for models.news_item.NewsItem."""
import unittest
from models.base_model import BaseModel
from models.news_item import NewsItem


class TestNewsItem(unittest.TestCase):
    """Test cases for the NewsItem class."""

    def test_is_subclass_of_base_model(self):
        """NewsItem inherits from BaseModel."""
        self.assertIsInstance(NewsItem(), BaseModel)

    def test_fields_can_be_set(self):
        """Title, body, and image_url can be assigned and read back."""
        item = NewsItem()
        item.title = "Headline"
        item.body = "Body text"
        item.image_url = "https://example.com/a.jpg"
        self.assertEqual(item.title, "Headline")
        self.assertEqual(item.body, "Body text")
        self.assertEqual(item.image_url, "https://example.com/a.jpg")


if __name__ == "__main__":
    unittest.main()
