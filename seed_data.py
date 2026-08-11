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
        {
            "name": "Jabrayil",
            "latitude": 39.2144,
            "longitude": 47.0072,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, "
                "historically an agricultural center on the Aras river "
                "plain. It was one of the first areas retaken during "
                "the 2020 Second Karabakh War and has since become a "
                "focus of the 'Great Return' reconstruction program, "
                "including new housing and infrastructure. (Source: "
                "azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Cəbrayıl",
                "tr": "Cebrayil",
                "ru": "Джабраил",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən şəhər, "
                    "tarixən Araz çayı düzənliyində əkinçilik mərkəzi "
                    "olmuşdur. 2020-ci il İkinci Qarabağ müharibəsi "
                    "zamanı geri qaytarılan ilk ərazilərdən biri olmuş "
                    "və o vaxtdan bəri Azərbaycanın 'Böyük Qayıdış' "
                    "proqramı çərçivəsində yeni yaşayış və infrastruktur "
                    "layihələrinin mərkəzinə çevrilmişdir. (Mənbə: "
                    "azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan bir "
                    "şehirdir, tarihsel olarak Aras Nehri ovasında bir "
                    "tarım merkeziydi. 2020 İkinci Karabağ Savaşı "
                    "sırasında geri alınan ilk bölgelerden biri olmuş ve "
                    "o zamandan beri Azerbaycan'ın 'Büyük Dönüş' "
                    "programı kapsamında yeni konut ve altyapı "
                    "projelerinin merkezi haline gelmiştir. (Kaynak: "
                    "azerbaijan.travel, president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "исторически являвшийся сельскохозяйственным центром "
                    "на равнине реки Аракс. Стал одной из первых "
                    "территорий, возвращённых во время Второй "
                    "карабахской войны 2020 года, и с тех пор находится "
                    "в центре программы «Великое возвращение» с новым "
                    "жильём и инфраструктурой. (Источник: "
                    "azerbaijan.travel, president.az)"
                ),
            },
        },
        {
            "name": "Gubadli",
            "latitude": 39.3389,
            "longitude": 46.5872,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, located "
                "near the Bazarchay river close to the border with "
                "Armenia. Largely depopulated for nearly three decades, "
                "it has been undergoing reconstruction since 2021 as "
                "part of Azerbaijan's redevelopment program for the "
                "region. (Source: azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Qubadlı",
                "tr": "Gubadlı",
                "ru": "Губадлы",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində, Ermənistan "
                    "sərhədinə yaxın Bazarçay çayı yaxınlığında yerləşən "
                    "şəhər. Təxminən otuz il ərzində əhalisi əsasən "
                    "boşalmış, 2021-ci ildən bəri isə Azərbaycanın "
                    "bölgə üçün bərpa proqramı çərçivəsində "
                    "yenidənqurma işləri aparılır. (Mənbə: "
                    "azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde, Ermenistan "
                    "sınırına yakın Bazarçay Nehri yakınında bulunan bir "
                    "şehirdir. Yaklaşık otuz yıl boyunca büyük ölçüde "
                    "ıssız kalmış, 2021'den bu yana Azerbaycan'ın bölge "
                    "için yeniden yapılanma programı kapsamında inşa "
                    "çalışmaları sürdürülmektedir. (Kaynak: "
                    "azerbaijan.travel, president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "расположенный у реки Базарчай, недалеко от границы "
                    "с Арменией. Оставался в основном безлюдным около "
                    "тридцати лет; с 2021 года ведутся восстановительные "
                    "работы в рамках программы Азербайджана по "
                    "возрождению региона. (Источник: azerbaijan.travel, "
                    "president.az)"
                ),
            },
        },
        {
            "name": "Zangilan",
            "latitude": 39.0886,
            "longitude": 46.6497,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, near the "
                "border with Armenia and Iran. It is home to the Aghali "
                "smart village project, one of the first pilot "
                "resettlement communities built as part of Azerbaijan's "
                "'Great Return' program, combining solar power and "
                "modern infrastructure. (Source: azerbaijan.travel, "
                "president.az)"
            ),
            "name_i18n": {
                "az": "Zəngilan",
                "tr": "Zengilan",
                "ru": "Зангилан",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində, Ermənistan və İran "
                    "sərhədləri yaxınlığında yerləşən şəhər. "
                    "Azərbaycanın 'Böyük Qayıdış' proqramı çərçivəsində "
                    "qurulan ilk pilot məskunlaşma qəsəbələrindən biri "
                    "olan Ağalı 'ağıllı kənd' layihəsinin ev sahibidir; "
                    "günəş enerjisi və müasir infrastrukturu birləşdirir. "
                    "(Mənbə: azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde, Ermenistan ve "
                    "İran sınırlarına yakın bir şehirdir. Azerbaycan'ın "
                    "'Büyük Dönüş' programı kapsamında inşa edilen ilk "
                    "pilot yeniden yerleşim topluluklarından biri olan "
                    "Ağalı 'akıllı köy' projesine ev sahipliği "
                    "yapmaktadır; güneş enerjisi ve modern altyapıyı bir "
                    "araya getirir. (Kaynak: azerbaijan.travel, "
                    "president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, недалеко "
                    "от границ с Арменией и Ираном. Здесь расположен "
                    "«умный посёлок» Агалы — один из первых пилотных "
                    "проектов расселения в рамках программы «Великое "
                    "возвращение», сочетающий солнечную энергетику и "
                    "современную инфраструктуру. (Источник: "
                    "azerbaijan.travel, president.az)"
                ),
            },
        },
        {
            "name": "Kalbajar",
            "latitude": 40.1067,
            "longitude": 46.0439,
            "category": "city",
            "description": (
                "A mountainous city in the Karabakh region of "
                "Azerbaijan, known for its alpine scenery, mineral "
                "springs, and Lake Istisu. Reconnected to the rest of "
                "Azerbaijan by a new road across the Murovdag mountains, "
                "it has been the focus of reconstruction efforts since "
                "2020. (Source: azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Kəlbəcər",
                "tr": "Kelbecer",
                "ru": "Кельбаджар",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən dağlıq "
                    "şəhər, alp mənzərələri, mineral bulaqları və İstisu "
                    "gölü ilə tanınır. Murovdağ silsiləsindən keçən yeni "
                    "yolla Azərbaycanın qalan hissəsi ilə yenidən "
                    "birləşdirilmiş və 2020-ci ildən bəri bərpa "
                    "işlərinin mərkəzindədir. (Mənbə: azerbaijan.travel, "
                    "president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan dağlık bir "
                    "şehirdir; alp manzaraları, maden suları ve İstisu "
                    "Gölü ile tanınır. Murovdağ sıradağlarından geçen "
                    "yeni bir yolla Azerbaycan'ın geri kalanına yeniden "
                    "bağlanmış ve 2020'den bu yana yeniden yapılanma "
                    "çalışmalarının merkezindedir. (Kaynak: "
                    "azerbaijan.travel, president.az)"
                ),
                "ru": (
                    "Горный город в Карабахском регионе Азербайджана, "
                    "известный альпийскими пейзажами, минеральными "
                    "источниками и озером Истису. Вновь соединён с "
                    "остальной территорией Азербайджана новой дорогой "
                    "через Муровдагский хребет и с 2020 года находится "
                    "в центре восстановительных работ. (Источник: "
                    "azerbaijan.travel, president.az)"
                ),
            },
        },
        {
            "name": "Khojaly",
            "latitude": 39.9092,
            "longitude": 46.7897,
            "category": "city",
            "description": (
                "A town in the Karabakh region of Azerbaijan, near "
                "Khankendi. In February 1992, during the First Karabakh "
                "War, hundreds of Azerbaijani civilians fleeing the town "
                "were killed in what is widely documented as one of the "
                "deadliest events of the conflict, known as the Khojaly "
                "Massacre. The town is home to Karabakh's main airport, "
                "reopened in 2021. (Source: azerbaijan.travel, "
                "president.az)"
            ),
            "name_i18n": {
                "az": "Xocalı",
                "tr": "Hocalı",
                "ru": "Ходжалы",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində, Xankəndiyə yaxın "
                    "yerləşən qəsəbə. 1992-ci il fevralında, Birinci "
                    "Qarabağ müharibəsi zamanı, qəsəbəni tərk edən "
                    "yüzlərlə azərbaycanlı mülki şəxs həlak olmuşdur — "
                    "bu hadisə münaqişənin ən faciəli epizodlarından "
                    "biri kimi geniş şəkildə sənədləşdirilib və Xocalı "
                    "soyqırımı adlanır. Qəsəbədə Qarabağın əsas hava "
                    "limanı yerləşir, 2021-ci ildə yenidən açılıb. "
                    "(Mənbə: azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde, Hankendi'ye yakın "
                    "bir kasabadır. Şubat 1992'de, Birinci Karabağ "
                    "Savaşı sırasında, kasabayı terk eden yüzlerce "
                    "Azerbaycanlı sivil öldürülmüştür — bu olay "
                    "çatışmanın en trajik anlarından biri olarak geniş "
                    "çapta belgelenmiş olup Hocalı Katliamı olarak "
                    "anılmaktadır. Kasabada, 2021'de yeniden açılan "
                    "Karabağ'ın ana havalimanı bulunmaktadır. (Kaynak: "
                    "azerbaijan.travel, president.az)"
                ),
                "ru": (
                    "Посёлок в Карабахском регионе Азербайджана, "
                    "недалеко от Ханкенди. В феврале 1992 года, во время "
                    "Первой карабахской войны, сотни азербайджанских "
                    "мирных жителей, покидавших посёлок, были убиты — "
                    "событие широко документировано как одна из самых "
                    "трагических страниц конфликта и известно как "
                    "Ходжалинская резня. В посёлке находится главный "
                    "аэропорт Карабаха, вновь открытый в 2021 году. "
                    "(Источник: azerbaijan.travel, president.az)"
                ),
            },
        },
        {
            "name": "Khojavend",
            "latitude": 39.7539,
            "longitude": 47.0522,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, serving "
                "as the administrative center of Khojavend district. "
                "Since coming back under Azerbaijani administration in "
                "2020, it has been included in the government's "
                "regional reconstruction and resettlement plans. "
                "(Source: azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Xocavənd",
                "tr": "Hocavend",
                "ru": "Ходжавенд",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində yerləşən şəhər, "
                    "Xocavənd rayonunun inzibati mərkəzidir. 2020-ci "
                    "ildən Azərbaycan idarəçiliyinə qayıtdıqdan sonra "
                    "hökumətin regional bərpa və məskunlaşma planlarına "
                    "daxil edilmişdir. (Mənbə: azerbaijan.travel, "
                    "president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde bulunan bir "
                    "şehirdir, Hocavend ilçesinin idari merkezidir. "
                    "2020'de Azerbaycan yönetimine geri döndükten sonra "
                    "hükümetin bölgesel yeniden yapılanma ve yeniden "
                    "yerleşim planlarına dahil edilmiştir. (Kaynak: "
                    "azerbaijan.travel, president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "административный центр Ходжавендского района. "
                    "После возвращения под управление Азербайджана в "
                    "2020 году включён в государственные планы "
                    "восстановления и расселения региона. (Источник: "
                    "azerbaijan.travel, president.az)"
                ),
            },
        },
        {
            "name": "Aghdara",
            "latitude": 40.0056,
            "longitude": 46.8967,
            "category": "city",
            "description": (
                "A city in the Karabakh region of Azerbaijan, situated "
                "in a forested, mountainous area north of Aghdam. It "
                "has been included in Azerbaijan's post-2020 "
                "reconstruction program, with new roads and housing "
                "developed to support resettlement. (Source: "
                "azerbaijan.travel, president.az)"
            ),
            "name_i18n": {
                "az": "Ağdərə",
                "tr": "Ağdere",
                "ru": "Агдере",
            },
            "description_i18n": {
                "az": (
                    "Azərbaycanın Qarabağ bölgəsində, Ağdamın şimalında "
                    "meşəli, dağlıq ərazidə yerləşən şəhər. 2020-ci "
                    "ildən sonrakı bərpa proqramına daxil edilmiş, "
                    "məskunlaşmanı dəstəkləmək üçün yeni yollar və "
                    "yaşayış obyektləri inşa edilmişdir. (Mənbə: "
                    "azerbaijan.travel, president.az)"
                ),
                "tr": (
                    "Azerbaycan'ın Karabağ bölgesinde, Ağdam'ın "
                    "kuzeyinde ormanlık, dağlık bir alanda bulunan "
                    "şehirdir. Azerbaycan'ın 2020 sonrası yeniden "
                    "yapılanma programına dahil edilmiş, yeniden "
                    "yerleşimi desteklemek için yeni yollar ve konutlar "
                    "inşa edilmiştir. (Kaynak: azerbaijan.travel, "
                    "president.az)"
                ),
                "ru": (
                    "Город в Карабахском регионе Азербайджана, "
                    "расположенный в лесистой горной местности к северу "
                    "от Агдама. Включён в программу восстановления "
                    "Азербайджана после 2020 года; для поддержки "
                    "расселения построены новые дороги и жильё. "
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
