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
            "latitude": 39.8288,
            "longitude": 46.7661,
            "description": (
                "A city in the Karabakh region of Azerbaijan. Since 2023, "
                "the city has seen redevelopment projects including the "
                "restored Bulud Hotel and a new congress and business "
                "center. Foreign nationals have been permitted to visit "
                "since July 2025 with a permit obtained through the "
                "Yolumuz Qarabag portal. (Source: president.az, "
                "azerbaijan.az)"
            ),
        },
        {
            "name": "Shusha",
            "latitude": 39.7581,
            "longitude": 46.7469,
            "description": (
                "A historic city in the Karabakh region of Azerbaijan, "
                "founded in the 18th century as the capital of the "
                "Karabakh Khanate. Promoted by Azerbaijan as its cultural "
                "capital, known for carpet-weaving traditions and as the "
                "birthplace of composer Uzeyir Hajibeyli and poet Molla "
                "Panah Vagif. Named Cultural Capital of the Turkic World "
                "for 2023. (Source: azerbaijan.travel)"
            ),
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


CITY_FIELDS = (
    "name", "latitude", "longitude", "description", "alt_names",
    "image_url", "image_credit",
)


def get_or_create_city(region, city_data):
    """Return the City under `region` matching city_data["name"], syncing
    its fields to city_data (clearing any field missing from city_data)."""
    for city in storage.all(City).values():
        if city.region_id == region.id and city.name == city_data["name"]:
            for field in CITY_FIELDS:
                setattr(city, field, city_data.get(field))
            city.save()
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
