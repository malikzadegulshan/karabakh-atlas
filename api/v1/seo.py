#!/usr/bin/python3
"""Crawler-facing pages: a share page per place (Open Graph / Twitter
preview tags), plus sitemap.xml and robots.txt.

Why this lives in the API instead of the frontend: the frontend is a
static single-page app, and link-preview bots (WhatsApp, Telegram,
Facebook, Slack, X) and most search crawlers read the raw HTML at a URL
without running JavaScript — so the ``?place=<id>`` links the app puts in
the address bar can only ever preview as the generic site card. These
routes return real per-place HTML instead; the share page hands people
straight on to the app with a meta refresh.
"""
import os
import re
from urllib.parse import quote, urlencode, urlsplit
from flask import Blueprint, Response, abort, render_template_string, request
from models import storage
from models.city import City

seo = Blueprint("seo", __name__)

SUPPORTED_LANGS = ("en", "az", "tr", "ru")
DESCRIPTION_MAX_CHARS = 200
IMAGE_PROXY_URL = "https://images.weserv.nl/"
# 1.91:1 is the aspect ratio every major preview card crops to.
OG_IMAGE_WIDTH = 1200
OG_IMAGE_HEIGHT = 630
SITE_NAME = "Dirchalish — Atlas of Karabakh"

# Server-side copy for the share page only — the app's own strings live in
# frontend/i18n.js. {name} is the place's (localized) name.
TEXT = {
    "en": {
        "fallback": "Explore {name} on the Dirchalish atlas of Karabakh: "
                    "places, photos and history on an interactive map.",
        "open": "Open {name} on the map",
        "home_desc": "An interactive atlas of Karabakh: cities, places, "
                     "photos and history on one map.",
    },
    "az": {
        "fallback": "{name} haqqında Dirçəliş Qarabağ atlasında məlumat "
                    "əldə edin: interaktiv xəritədə məkanlar, şəkillər və "
                    "tarix.",
        "open": "{name} məkanını xəritədə aç",
        "home_desc": "Qarabağın interaktiv atlası: şəhərlər, məkanlar, "
                     "şəkillər və tarix bir xəritədə.",
    },
    "tr": {
        "fallback": "{name} hakkında Dirçeliş Karabağ atlasında bilgi "
                    "edinin: etkileşimli haritada yerler, fotoğraflar ve "
                    "tarih.",
        "open": "{name} yerini haritada aç",
        "home_desc": "Karabağ'ın etkileşimli atlası: şehirler, yerler, "
                     "fotoğraflar ve tarih tek haritada.",
    },
    "ru": {
        "fallback": "{name} — узнайте больше в атласе Карабаха "
                    "«Дирчалиш»: места, фотографии и история на "
                    "интерактивной карте.",
        "open": "Открыть «{name}» на карте",
        "home_desc": "Интерактивный атлас Карабаха: города, места, "
                     "фотографии и история на одной карте.",
    },
}

PAGE_TEMPLATE = """<!doctype html>
<html lang="{{ lang }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<meta name="description" content="{{ description }}">
<link rel="canonical" href="{{ share_url }}">
<meta http-equiv="refresh" content="0; url={{ app_url }}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{{ site_name }}">
<meta property="og:title" content="{{ title }}">
<meta property="og:description" content="{{ description }}">
<meta property="og:url" content="{{ share_url }}">
<meta property="og:locale" content="{{ og_locale }}">
{% if image %}<meta property="og:image" content="{{ image }}">
<meta property="og:image:width" content="{{ image_width }}">
<meta property="og:image:height" content="{{ image_height }}">
<meta property="og:image:alt" content="{{ name }}">
{% endif %}<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{{ title }}">
<meta name="twitter:description" content="{{ description }}">
{% if image %}<meta name="twitter:image" content="{{ image }}">
{% endif %}</head>
<body>
<h1>{{ name }}</h1>
<p>{{ description }}</p>
<p><a href="{{ app_url }}">{{ open_text }}</a></p>
</body>
</html>
"""

OG_LOCALES = {"en": "en_US", "az": "az_AZ", "tr": "tr_TR", "ru": "ru_RU"}


def frontend_origin():
    """The public origin of the single-page app (first entry of
    KBA_FRONTEND_ORIGIN), without a trailing slash."""
    raw = os.environ.get("KBA_FRONTEND_ORIGIN", "http://localhost:8000")
    first = raw.split(",")[0].strip().rstrip("/")
    return first or "http://localhost:8000"


def _lang_from_request():
    lang = (request.args.get("lang") or "en").lower()
    return lang if lang in SUPPORTED_LANGS else "en"


def _localized(value, i18n, lang):
    if isinstance(i18n, dict):
        translated = i18n.get(lang)
        if isinstance(translated, str) and translated.strip():
            return translated.strip()
    return (value or "").strip()


def build_description(text, fallback):
    """Collapse whitespace and clip to DESCRIPTION_MAX_CHARS on a word
    boundary (with an ellipsis); use ``fallback`` when there's no text."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return fallback
    if len(text) <= DESCRIPTION_MAX_CHARS:
        return text
    clipped = text[:DESCRIPTION_MAX_CHARS - 1]
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(" ,.;:-—") + "…"


def preview_image_url(image_url):
    """An absolute, resized (1200x630) URL for og:image, or None unless
    ``image_url`` is a plain http(s) link. Goes through the same resizer
    the app uses for its hero photos, so a multi-megabyte upload doesn't
    make WhatsApp skip the preview."""
    if not image_url:
        return None
    parts = urlsplit(image_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return IMAGE_PROXY_URL + "?" + urlencode({
        "url": image_url,
        "w": OG_IMAGE_WIDTH,
        "h": OG_IMAGE_HEIGHT,
        "fit": "cover",
        "q": 80,
        "output": "jpg",
    })


def _share_base():
    return request.host_url.rstrip("/")


def _find_city(city_id):
    return storage.all(City).get("City.{}".format(city_id))


@seo.route("/p/<city_id>")
def share_page(city_id):
    """HTML preview card for one place, then on to the app."""
    city = _find_city(city_id)
    if city is None:
        abort(404)
    lang = _lang_from_request()
    text = TEXT[lang]
    name = _localized(city.name, city.name_i18n, lang)
    description = build_description(
        _localized(city.description, city.description_i18n, lang),
        text["fallback"].format(name=name))
    # No (usable) photo -> the site's own card, so the link still previews
    # with an image rather than as a bare text box.
    image = (preview_image_url(city.image_url)
             or "{}/og-image.png".format(frontend_origin()))
    app_url = "{}/?{}".format(
        frontend_origin(), urlencode({"place": city.id}))
    share_url = "{}/p/{}".format(_share_base(), quote(city.id, safe=""))
    if lang != "en":
        share_url += "?" + urlencode({"lang": lang})
        app_url += "&" + urlencode({"lang": lang})
    html = render_template_string(
        PAGE_TEMPLATE, lang=lang, og_locale=OG_LOCALES[lang],
        title="{} — Dirchalish".format(name), name=name,
        description=description, image=image,
        image_width=OG_IMAGE_WIDTH, image_height=OG_IMAGE_HEIGHT,
        share_url=share_url, app_url=app_url, site_name=SITE_NAME,
        open_text=text["open"].format(name=name))
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@seo.route("/sitemap.xml")
def sitemap():
    """Every place's share page, so crawlers can discover them."""
    base = _share_base()
    cities = sorted(storage.all(City).values(), key=lambda c: c.id)
    entries = []
    for city in cities:
        lastmod = city.updated_at.strftime("%Y-%m-%d") \
            if getattr(city, "updated_at", None) else None
        loc = "{}/p/{}".format(base, quote(city.id, safe=""))
        entry = "  <url><loc>{}</loc>".format(_xml_escape(loc))
        if lastmod:
            entry += "<lastmod>{}</lastmod>".format(lastmod)
        entries.append(entry + "</url>")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries) + ("\n" if entries else "")
        + "</urlset>\n")
    response = Response(body, mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@seo.route("/robots.txt")
def robots():
    """Let crawlers into the share pages, keep them out of the JSON API."""
    body = (
        "User-agent: *\n"
        "Allow: /p/\n"
        "Disallow: /api/\n"
        "\n"
        "Sitemap: {}/sitemap.xml\n".format(_share_base()))
    return Response(body, mimetype="text/plain")


def _xml_escape(value):
    return (value.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))
