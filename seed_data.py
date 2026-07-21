#!/usr/bin/python3
"""Seed script: populate starter region/city data via the storage layer.

Safe to re-run — it reuses existing regions/cities by name instead of
creating duplicates. Add more entries to REGIONS as the dataset grows.
"""
from models import storage
from models.region import Region
from models.city import City

REGIONS = {
    "Karabakh": [
        {
            "name": "Khankendi",
            "alt_names": "Stepanakert",
            "latitude": 39.8288,
            "longitude": 46.7661,
        },
    ],
}


def get_or_create_region(name):
    """Return the existing Region named `name`, creating it if needed."""
    for region in storage.all(Region).values():
        if region.name == name:
            return region
    region = Region(name=name)
    region.save()
    return region


def get_or_create_city(region, city_data):
    """Return the existing City under `region` matching city_data["name"]."""
    for city in storage.all(City).values():
        if city.region_id == region.id and city.name == city_data["name"]:
            return city
    city = City(region_id=region.id, **city_data)
    city.save()
    return city


def seed():
    """Create every region/city listed in REGIONS if not already present."""
    for region_name, cities in REGIONS.items():
        region = get_or_create_region(region_name)
        for city_data in cities:
            get_or_create_city(region, city_data)
        print("Region '{}': {} cit{} ready.".format(
            region_name, len(cities), "y" if len(cities) == 1 else "ies"))


if __name__ == "__main__":
    seed()
