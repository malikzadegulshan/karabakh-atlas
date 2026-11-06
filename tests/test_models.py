#!/usr/bin/python3
"""Unit tests for all data models and FileStorage engine."""
import unittest
from datetime import datetime
from models import storage
from models.base_model import BaseModel
from models.city import City
from models.favorite import Favorite
from models.forum_post import ForumPost
from models.historical_event import HistoricalEvent
from models.news_item import NewsItem
from models.region import Region
from models.user import User


class TestBaseModel(unittest.TestCase):
    """Test cases for the BaseModel class."""

    def test_init_no_args_sets_defaults(self):
        """A freshly created instance gets id, created_at, updated_at."""
        obj = BaseModel()
        self.assertIsInstance(obj.id, str)
        self.assertIsInstance(obj.created_at, datetime)
        self.assertIsInstance(obj.updated_at, datetime)

    def test_two_instances_have_different_ids(self):
        """Each instance gets a unique id."""
        obj1 = BaseModel()
        obj2 = BaseModel()
        self.assertNotEqual(obj1.id, obj2.id)

    def test_str_representation(self):
        """__str__ includes the class name, id, and attribute dict."""
        obj = BaseModel()
        text = str(obj)
        self.assertIn("[BaseModel]", text)
        self.assertIn(obj.id, text)

    def test_to_dict_contains_class_key(self):
        """to_dict() adds a __class__ key with the class name."""
        obj = BaseModel()
        d = obj.to_dict()
        self.assertEqual(d["__class__"], "BaseModel")
        self.assertIsInstance(d["created_at"], str)
        self.assertIsInstance(d["updated_at"], str)

    def test_init_from_kwargs_rebuilds_instance(self):
        """Passing kwargs (as from to_dict) reconstructs an equivalent
        instance."""
        original = BaseModel()
        original.name = "test"
        d = original.to_dict()
        rebuilt = BaseModel(**d)
        self.assertEqual(original.id, rebuilt.id)
        self.assertEqual(original.created_at, rebuilt.created_at)

    def test_save_updates_updated_at(self):
        """save() refreshes updated_at to a later timestamp."""
        obj = Region(name="Save Test Region")
        old_updated_at = obj.updated_at
        obj.save()
        self.assertGreaterEqual(obj.updated_at, old_updated_at)


class TestRegion(unittest.TestCase):
    """Test cases for the Region class."""

    def test_is_subclass_of_base_model(self):
        """Region inherits from BaseModel."""
        region = Region()
        self.assertIsInstance(region, BaseModel)

    def test_default_name_is_empty_string(self):
        """A region created without a name has no name attribute set."""
        region = Region()
        self.assertFalse(hasattr(region, "name") and region.name)

    def test_name_can_be_set(self):
        """The name attribute can be assigned and read back."""
        region = Region()
        region.name = "Sample Region"
        self.assertEqual(region.name, "Sample Region")

    def test_cities_property_starts_empty(self):
        """A brand new region has no linked cities."""
        region = Region()
        region.name = "Sample Region"
        region.save()
        self.assertEqual(region.cities, [])


class TestCity(unittest.TestCase):
    """Test cases for the City class."""

    def test_is_subclass_of_base_model(self):
        """City inherits from BaseModel."""
        city = City()
        self.assertIsInstance(city, BaseModel)

    def test_coordinates_can_be_set(self):
        """Latitude and longitude can be assigned and read back."""
        city = City()
        city.name = "Sample City"
        city.latitude = 39.75
        city.longitude = 46.75
        self.assertEqual(city.latitude, 39.75)
        self.assertEqual(city.longitude, 46.75)

    def test_region_id_defaults_unset(self):
        """A city created without a region_id has none set."""
        city = City()
        self.assertFalse(hasattr(city, "region_id") and city.region_id)


class TestUser(unittest.TestCase):
    """Test User model."""

    def test_user_is_base_model(self):
        """User inherits from BaseModel."""
        user = User()
        self.assertIsInstance(user, BaseModel)

    def test_user_name(self):
        """User name can be assigned."""
        user = User()
        user.name = "Test User"
        self.assertEqual(user.name, "Test User")

    def test_user_email(self):
        """User email can be assigned."""
        user = User()
        user.email = "test@example.com"
        self.assertEqual(user.email, "test@example.com")

    def test_set_password_hashes_it(self):
        """set_password() never stores the raw password."""
        user = User()
        user.set_password("correcthorsebattery")
        self.assertNotEqual(user.password_hash, "correcthorsebattery")
        self.assertTrue(len(user.password_hash) > 20)

    def test_check_password_accepts_correct_password(self):
        """check_password() returns True for the password it was set to."""
        user = User()
        user.set_password("correcthorsebattery")
        self.assertTrue(user.check_password("correcthorsebattery"))

    def test_check_password_rejects_wrong_password(self):
        """check_password() returns False for any other password."""
        user = User()
        user.set_password("correcthorsebattery")
        self.assertFalse(user.check_password("wrong-password"))

    def test_public_dict_excludes_password_hash(self):
        """public_dict() never leaks internal secret or session fields."""
        user = User(name="Test User", email="test@example.com")
        user.set_password("correcthorsebattery")
        user.generate_password_reset_otp()
        user.session_epoch = 3
        public = user.public_dict()
        self.assertNotIn("password_hash", public)
        self.assertNotIn("password_reset_otp", public)
        self.assertNotIn("password_reset_otp_expires_at", public)
        self.assertNotIn("session_epoch", public)

    def test_to_dict_keeps_password_hash(self):
        """to_dict() keeps password_hash — FileStorage round-trips objects
        to disk through it, so stripping it there would lose it."""
        user = User(name="Test User", email="test@example.com")
        user.set_password("correcthorsebattery")
        self.assertIn("password_hash", user.to_dict())

    def test_is_approved_only_false_when_explicitly_unapproved(self):
        """None (legacy rows) and True are approved; only False is pending."""
        user = User()
        self.assertTrue(user.is_approved)
        user.approved = True
        self.assertTrue(user.is_approved)
        user.approved = False
        self.assertFalse(user.is_approved)


class TestFavorite(unittest.TestCase):
    """Test cases for the Favorite class."""

    def test_is_subclass_of_base_model(self):
        """Favorite inherits from BaseModel."""
        favorite = Favorite()
        self.assertIsInstance(favorite, BaseModel)

    def test_fields_can_be_set(self):
        """Core fields can be assigned and read back."""
        favorite = Favorite()
        favorite.user_id = "some-user-id"
        favorite.city_id = "some-city-id"
        self.assertEqual(favorite.user_id, "some-user-id")
        self.assertEqual(favorite.city_id, "some-city-id")


class TestForumPost(unittest.TestCase):
    """Test cases for the ForumPost class."""

    def test_is_subclass_of_base_model(self):
        """ForumPost inherits from BaseModel."""
        post = ForumPost()
        self.assertIsInstance(post, BaseModel)

    def test_fields_can_be_set(self):
        """Core fields can be assigned and read back."""
        post = ForumPost()
        post.author_id = "some-user-id"
        post.body = "Beautiful region."
        post.status = "pending"
        self.assertEqual(post.author_id, "some-user-id")
        self.assertEqual(post.body, "Beautiful region.")
        self.assertEqual(post.status, "pending")

    def test_target_city_id_defaults_unset(self):
        """A post created without a target_city_id has none set — it's a
        general opinion, not one about a specific city/POI."""
        post = ForumPost()
        self.assertFalse(
            hasattr(post, "target_city_id") and post.target_city_id)


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


class TestFileStorage(unittest.TestCase):
    """Test cases for the FileStorage engine."""

    def test_new_and_all(self):
        """new() registers an object so it is returned by all()."""
        region = Region(name="Test Region")
        region.save()
        key = "Region.{}".format(region.id)
        self.assertIn(key, storage.all())

    def test_all_filters_by_class(self):
        """all(cls) only returns objects of the requested class."""
        region = Region(name="Filter Region")
        region.save()
        city = City(name="Filter City", latitude=1.0, longitude=1.0)
        city.save()
        regions = storage.all(Region)
        self.assertTrue(all(isinstance(o, Region) for o in regions.values()))

    def test_delete_removes_object(self):
        """delete() removes the object from storage.all()."""
        region = Region(name="Delete Me")
        region.save()
        key = "Region.{}".format(region.id)
        region.delete()
        storage.save()
        self.assertNotIn(key, storage.all())


if __name__ == "__main__":
    unittest.main()
