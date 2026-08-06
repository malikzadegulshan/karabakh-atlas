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
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan. Since 2023, "
                "the city has seen redevelopment projects including the "
                "restored Bulud Hotel and a new congress and business "
                "center. Foreign nationals have been permitted to visit "
                "since July 2025 with a permit obtained through the "
                "Yolumuz Qarabag portal. (Source: president.az, "
                "azerbaijan.az)"
            ),
            "image_url": (
                "https://commons.wikimedia.org/wiki/Special:FilePath/"
                "Stepanakert_Wikivoyage_banner.jpg"
            ),
            "image_credit": (
                "Photo via Wikimedia Commons — see file page for author "
                "and license"
            ),
            "name_i18n": {
                "az": "Xankəndi",
                "tr": "Hankendi",
                "ru": "Ханкенди",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən şəhərdir. "
                    "2023-cü ildən bəri şəhərdə bərpa olunmuş Bulud Hotel "
                    "və yeni konqres və biznes mərkəzi daxil olmaqla "
                    "yenidənqurma layihələri həyata keçirilib. Xarici "
                    "vətəndaşlara 2025-ci ilin iyul ayından etibarən "
                    "'Yolumuz Qarabağ' portalı vasitəsilə əldə edilən "
                    "icazə ilə səfər etməyə icazə verilir. (Mənbə: "
                    "president.az, azerbaijan.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan bir "
                    "şehirdir. 2023'ten bu yana şehirde restore edilen "
                    "Bulud Oteli ve yeni bir kongre ve iş merkezi dahil "
                    "olmak üzere yeniden yapılanma projeleri "
                    "gerçekleştirilmiştir. Yabancı vatandaşların Temmuz "
                    "2025'ten itibaren 'Yolumuz Qarabağ' portalından "
                    "alınan bir izinle şehri ziyaret etmelerine izin "
                    "verilmektedir. (Kaynak: president.az, azerbaijan.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана. С 2023 "
                    "года в городе реализуются проекты реконструкции, "
                    "включая восстановленный отель Bulud и новый "
                    "конгресс- и бизнес-центр. С июля 2025 года "
                    "иностранным гражданам разрешено посещать город по "
                    "разрешению, оформленному через портал 'Yolumuz "
                    "Qarabağ'. (Источник: president.az, azerbaijan.az)"
                ),
            },
        },
        {
            "name": "Shusha",
            "latitude": 39.7581,
            "longitude": 46.7469,
            "category": "city",
            "description": (
                "A historic city in the Karabakh region of Azerbaijan, "
                "founded in the 18th century as the capital of the "
                "Karabakh Khanate. Promoted by Azerbaijan as its cultural "
                "capital, known for carpet-weaving traditions and as the "
                "birthplace of composer Uzeyir Hajibeyli and poet Molla "
                "Panah Vagif. Named Cultural Capital of the Turkic World "
                "for 2023. (Source: azerbaijan.travel)"
            ),
            "image_url": (
                "https://commons.wikimedia.org/wiki/Special:FilePath/"
                "Shusha_general_view.jpg"
            ),
            "image_credit": (
                "Photo via Wikimedia Commons — see file page for author "
                "and license"
            ),
            "name_i18n": {
                "az": "Şuşa",
                "tr": "Şuşa",
                "ru": "Шуша",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində, 18-ci əsrdə Qarabağ "
                    "xanlığının paytaxtı kimi qurulmuş tarixi şəhərdir. "
                    "Azərbaycan tərəfindən mədəniyyət paytaxtı kimi "
                    "təşviq olunur, xalça toxuculuğu ənənələri, bəstəkar "
                    "Üzeyir Hacıbəyov və şair Molla Pənah Vaqifin "
                    "doğulduğu yer kimi tanınır. 2023-cü il üçün Türk "
                    "Dünyasının Mədəniyyət Paytaxtı elan edilib. (Mənbə: "
                    "azerbaijan.travel)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde, 18. yüzyılda "
                    "Karabağ Hanlığı'nın başkenti olarak kurulmuş tarihi "
                    "bir şehirdir. Azerbaycan tarafından kültür başkenti "
                    "olarak tanıtılmaktadır; halı dokuma gelenekleri ve "
                    "besteci Üzeyir Hacıbeyov ile şair Molla Penah "
                    "Vagif'in doğum yeri olarak bilinir. 2023 yılı için "
                    "Türk Dünyasının Kültür Başkenti ilan edilmiştir. "
                    "(Kaynak: azerbaijan.travel)"
                ),
                "ru": (
                    "Исторический город в Карабахском регионе "
                    "Азербайджана, основанный в XVIII веке как столица "
                    "Карабахского ханства. Продвигается Азербайджаном "
                    "как культурная столица страны, известен традициями "
                    "ковроткачества, а также как место рождения "
                    "композитора Узеира Гаджибекова и поэта Моллы "
                    "Панаха Вагифа. Объявлен культурной столицей "
                    "тюркского мира на 2023 год. (Источник: "
                    "azerbaijan.travel)"
                ),
            },
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
    "image_url", "image_credit", "category", "name_i18n",
    "description_i18n",
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
