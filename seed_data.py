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
        {
            "name": "Aghdam",
            "latitude": 39.9908,
            "longitude": 46.9264,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, largely "
                "destroyed during the First Karabakh War and left "
                "uninhabited for nearly three decades. Its most "
                "recognizable landmark, the Aghdam Mosque, survived the "
                "destruction and has been preserved as a memorial. "
                "Since 2020 the city has been the focus of large-scale "
                "reconstruction under Azerbaijan's 'Great Return' "
                "program. (Source: azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Ağdam",
                "tr": "Ağdam",
                "ru": "Агдам",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən şəhər, "
                    "Birinci Qarabağ müharibəsi zamanı böyük dağıntıya "
                    "məruz qalmış və təxminən otuz il ərzində əhalisiz "
                    "qalmışdır. Ən tanınmış abidəsi olan Ağdam məscidi "
                    "dağıntıdan sağ çıxmış və xatirə abidəsi kimi "
                    "qorunub saxlanılır. 2020-ci ildən bəri şəhər "
                    "Azərbaycanın 'Böyük Qayıdış' proqramı çərçivəsində "
                    "genişmiqyaslı bərpa işlərinin mərkəzindədir. "
                    "(Mənbə: azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan bir "
                    "şehirdir; Birinci Karabağ Savaşı sırasında büyük "
                    "ölçüde tahrip edilmiş ve yaklaşık otuz yıl boyunca "
                    "ıssız kalmıştır. En tanınmış yapısı olan Ağdam "
                    "Camii yıkımdan kurtulmuş ve bir anıt olarak "
                    "korunmaktadır. 2020'den bu yana şehir, Azerbaycan'ın "
                    "'Büyük Dönüş' programı kapsamında geniş çaplı "
                    "yeniden yapılanmanın merkezindedir. (Kaynak: "
                    "azerbaijan.travel, president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "значительно разрушенный во время Первой карабахской "
                    "войны и остававшийся безлюдным около тридцати лет. "
                    "Его самая узнаваемая достопримечательность, "
                    "Агдамская мечеть, уцелела и сохраняется как "
                    "памятник. С 2020 года город находится в центре "
                    "масштабных восстановительных работ в рамках "
                    "программы Азербайджана «Великое возвращение». "
                    "(Источник: azerbaijan.travel, president.az)"
                ),
            },
        },
        {
            "name": "Fuzuli",
            "latitude": 39.6062,
            "longitude": 47.1467,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, "
                "historically an agricultural center at the edge of the "
                "Karabakh lowlands. Fuzuli International Airport, opened "
                "nearby in 2021, has become a key transport link for the "
                "region's reconstruction. Named after the 16th-century "
                "poet Muhammad Fuzuli. (Source: azerbaijan.travel, "
                "president.az)"
            ),
            "name_i18n": {
                "az": "Füzuli",
                "tr": "Füzuli",
                "ru": "Физули",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən şəhər, "
                    "tarixən Qarabağ düzənliyinin kənarında əkinçilik "
                    "mərkəzi olmuşdur. 2021-ci ildə yaxınlıqda açılan "
                    "Füzuli Beynəlxalq Hava Limanı bölgənin bərpası üçün "
                    "mühüm nəqliyyat əlaqəsinə çevrilmişdir. Şəhər adını "
                    "16-cı əsr şairi Məhəmməd Füzulinin şərəfinə "
                    "daşıyır. (Mənbə: azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan bir "
                    "şehirdir, tarihsel olarak Karabağ ovasının kenarında "
                    "bir tarım merkeziydi. 2021'de yakınında açılan "
                    "Füzuli Uluslararası Havalimanı, bölgenin yeniden "
                    "yapılanması için önemli bir ulaşım bağlantısı haline "
                    "gelmiştir. Şehir, adını 16. yüzyıl şairi Muhammed "
                    "Fuzuli'den almaktadır. (Kaynak: azerbaijan.travel, "
                    "president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "исторически являвшийся сельскохозяйственным центром "
                    "на краю Карабахской равнины. Международный аэропорт "
                    "Физули, открытый неподалёку в 2021 году, стал "
                    "важным транспортным звеном для восстановления "
                    "региона. Город назван в честь поэта XVI века "
                    "Мухаммеда Физули. (Источник: azerbaijan.travel, "
                    "president.az)"
                ),
            },
        },
        {
            "name": "Lachin",
            "latitude": 39.6412,
            "longitude": 46.5464,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, "
                "historically known for its mountain scenery and as a "
                "waypoint between Karabakh and Armenia. A new "
                "Lachin–Khankendi road, along with wider "
                "reconstruction efforts, has been developed since 2022 "
                "to reconnect the city to the region. (Source: "
                "azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Laçın",
                "tr": "Laçin",
                "ru": "Лачин",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən şəhər, "
                    "tarixən dağ mənzərələri və Qarabağ ilə Ermənistan "
                    "arasında keçid nöqtəsi kimi tanınır. 2022-ci ildən "
                    "bəri yeni Laçın–Xankəndi yolu və digər bərpa "
                    "işləri şəhərin bölgə ilə yenidən əlaqələndirilməsi "
                    "üçün həyata keçirilib. (Mənbə: azerbaijan.travel, "
                    "president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan bir "
                    "şehirdir, tarihsel olarak dağ manzaraları ve "
                    "Karabağ ile Ermenistan arasında bir geçiş noktası "
                    "olarak bilinir. 2022'den bu yana yeni "
                    "Laçin–Hankendi yolu ve diğer yeniden yapılanma "
                    "çalışmaları şehri bölgeyle yeniden bağlamak için "
                    "gerçekleştirilmiştir. (Kaynak: azerbaijan.travel, "
                    "president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "исторически известный горными пейзажами и как "
                    "пункт перехода между Карабахом и Арменией. С 2022 "
                    "года были реализованы новая дорога "
                    "Лачин–Ханкенди и другие восстановительные "
                    "работы для воссоединения города с регионом. "
                    "(Источник: azerbaijan.travel, president.az)"
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
