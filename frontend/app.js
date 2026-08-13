const API_BASE = window.KBA_API_BASE || "http://localhost:5000/api/v1";
const DEFAULT_CENTER = [39.8, 46.75];
const DEFAULT_ZOOM = 9;

let currentLang = getStoredLang() || DEFAULT_LANG;
if (!TRANSLATIONS[currentLang]) {
  currentLang = DEFAULT_LANG;
}
let lastCities = [];
let layerControl = null;
let searchQuery = "";

function t(key) {
  return TRANSLATIONS[currentLang][key];
}

// Theme: follows the system by default, overridable and persisted via
// the #theme-toggle rail button (localStorage key "kba_theme"). scheme()
// is the single source of truth every color-scheme-aware render below
// calls — it checks the override first, falling back to the live media
// query. index.html also applies a stored override to
// documentElement.dataset.theme synchronously in <head>, before first
// paint, from that same key, so there's no flash of the wrong theme.
const darkModeQuery = window.matchMedia("(prefers-color-scheme: dark)");

function scheme() {
  const override = document.documentElement.dataset.theme;
  return override === "light" || override === "dark"
    ? override
    : (darkModeQuery.matches ? "dark" : "light");
}

function getStoredTheme() {
  try {
    return localStorage.getItem("kba_theme");
  } catch (err) {
    return null;
  }
}

function setStoredTheme(theme) {
  try {
    localStorage.setItem("kba_theme", theme);
  } catch (err) {
    /* localStorage unavailable (e.g. private browsing); the override
       still applies for this page load via dataset.theme, it just
       won't persist across reloads */
  }
}

// Zoom control moves to the bottom-right (Leaflet's default top-left spot
// would sit right under the floating search bar/buttons).
const map = L.map("map", { zoomControl: false }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
L.control.zoom({ position: "bottomright" }).addTo(map);

// CartoDB Positron / Dark Matter: a clean, free/keyless basemap with
// place labels but no baked-in amenity icons (cafe/restaurant/etc.), so
// our own points-of-interest markers stay legible instead of competing
// with icons we can't control. Two variants of the same basemap, picked
// to match the app's color scheme — otherwise a dark UI would sit next
// to a glaring white map. Swapped at runtime via setUrl(), see
// applyColorScheme() below.
const STREET_TILE_URLS = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

const streetLayer = L.tileLayer(
  STREET_TILE_URLS[scheme()],
  {
    maxZoom: 19,
    subdomains: "abcd",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors ' +
      '&copy; <a href="https://carto.com/attributions">CARTO</a>',
  }
);

const satelliteLayer = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {
    maxZoom: 19,
    attribution:
      "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  }
);

// Esri World Imagery Wayback: the same high-resolution basemap as the
// Satellite layer above, just at different capture dates — free,
// keyless, and genuinely zoomable (unlike coarse ~250m/pixel sources
// like NASA MODIS), at the cost of only reaching back to ~2014 instead
// of the early 2000s. Release dates/tile URLs come from Esri's own
// published config rather than being guessed at, since the exact
// per-release tile path isn't otherwise documented.
const WAYBACK_CONFIG_URL =
  "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json";
const WAYBACK_FALLBACK_MIN_YEAR = 2014;
let waybackReleases = []; // [{ date, urlTemplate }], sorted oldest to newest
let selectedYear = new Date().getFullYear();

const historicalLayer = L.tileLayer("", {
  maxZoom: 19,
  attribution:
    "Imagery: Esri World Imagery Wayback — Source: Esri, Maxar, " +
    "Earthstar Geographics, and the GIS User Community",
});

function releaseForYear(year) {
  const target = new Date(`${year}-07-15`);
  return waybackReleases.reduce((closest, release) => {
    const diff = Math.abs(release.date - target);
    return diff < Math.abs(closest.date - target) ? release : closest;
  }, waybackReleases[0]);
}

function applySelectedYear() {
  if (waybackReleases.length === 0) {
    return;
  }
  historicalLayer.setUrl(releaseForYear(selectedYear).urlTemplate);
}

async function loadWaybackReleases() {
  try {
    const res = await fetch(WAYBACK_CONFIG_URL);
    if (!res.ok) {
      throw new Error(`Wayback config returned ${res.status}`);
    }
    const config = await res.json();
    const releases = [];
    Object.values(config).forEach((entry) => {
      const dateMatch = /(\d{4}-\d{2}-\d{2})/.exec(entry.itemTitle || "");
      if (!dateMatch || !entry.itemURL) {
        return;
      }
      releases.push({
        date: new Date(dateMatch[1]),
        urlTemplate: entry.itemURL
          .replace("{level}", "{z}")
          .replace("{row}", "{y}")
          .replace("{col}", "{x}"),
      });
    });
    releases.sort((a, b) => a.date - b.date);
    if (releases.length === 0) {
      return;
    }
    waybackReleases = releases;
    yearSliderEl.min = releases[0].date.getFullYear();
    yearSliderEl.max = releases[releases.length - 1].date.getFullYear();
    yearSliderEl.value = selectedYear;
    applySelectedYear();
  } catch (err) {
    // Leave the fallback slider range in place; the layer just won't
    // have tiles until this succeeds (same degradation as any other
    // tile provider being unreachable).
  }
}

streetLayer.addTo(map);

function refreshLayerControl() {
  if (layerControl) {
    map.removeControl(layerControl);
  }
  layerControl = L.control
    .layers(
      {
        [t("layerStreets")]: streetLayer,
        [t("layerSatellite")]: satelliteLayer,
        [t("layerHistorical")]: historicalLayer,
      },
      null,
      { position: "bottomright" }
    )
    .addTo(map);
}

refreshLayerControl();

// Street tiles already render place-name labels on their own, so our
// custom city-name markers would look redundant there — only show them
// over satellite/historical imagery, which has no labels of its own.
//
// This layer stays added to the map at all times (unlike poiMarkersLayer
// below): a marker whose LayerGroup isn't on the map can't show its
// popup at all, which would silently break "jump to this city" (from
// the sidebar or search) on the default Streets view. Instead, the
// "redundant on Streets" concern is handled purely visually, by hiding
// the .city-label divIcons with CSS — that keeps every marker properly
// attached to the map (so popups always work) without cluttering the
// Streets view with duplicate labels.
const markersLayer = L.layerGroup().addTo(map);

// Points of interest (cafes, restaurants, etc.) are shown on both tile
// layers, but only once zoomed in enough — otherwise a full set of them
// would look chaotic at the region-wide view. That clutter concern goes
// away once a category filter narrows it down to just one kind of
// place, so a filter being active bypasses the zoom gate entirely.
const POI_MIN_ZOOM = 14;
const poiMarkersLayer = L.layerGroup();
let activeCategoryFilter = null;

// Which of the four grays each category's marker uses. Replaces the old
// one-hue-per-category palette: a single flat black would make 21 kinds
// of place indistinguishable on the map, so the tones are grouped by
// what a place is *for* — the darkest reads as "most urgent" instead of
// being an arbitrary color.
//
// Keep in sync with CITY_CATEGORIES in api/v1/views/cities.py. This
// object doubles as the list of POI categories (its keys are exactly
// the non-"city" ones), and each key is also its icon's name in
// KBA_ICON_PATHS — so adding a category means adding it here and in
// vendor/icons/icons.js, nowhere else.
const POI_TONES = {
  // Civic and emergency
  hospital: 0,
  police: 0,
  fire_station: 0,
  government: 0,
  // Culture and education
  museum: 1,
  landmark: 1,
  mosque: 1,
  church: 1,
  university: 1,
  school: 1,
  // Everyday services
  bank: 2,
  pharmacy: 2,
  fuel_station: 2,
  parking: 2,
  road: 2,
  // Leisure
  cafe: 3,
  restaurant: 3,
  hotel: 3,
  shop: 3,
  park: 3,
  other: 3,
};

// The ramp flips wholesale between color schemes: dark circles read on
// the light basemap, light circles on the dark one. Both directions
// keep every tone at 4.5:1 or better against its own glyph color below.
const POI_TONE_RAMP = {
  light: ["#18181b", "#3f3f46", "#52525b", "#71717a"],
  dark: ["#fafafa", "#d4d4d8", "#b4b4ba", "#96969c"],
};

// Glyph drawn inside the circle, and the ring separating it from the
// map underneath — both are the ramp's opposite end.
const POI_GLYPH = { light: "#ffffff", dark: "#18181b" };
const POI_RING = { light: "#ffffff", dark: "#2c2c2e" };

function poiToneColor(category) {
  const tier = POI_TONES[category] !== undefined
    ? POI_TONES[category]
    : POI_TONES.other;
  return POI_TONE_RAMP[scheme()][tier];
}

function updateMarkersVisibility(activeLayer) {
  const showLabels = activeLayer === satelliteLayer || activeLayer === historicalLayer;
  map.getContainer().classList.toggle("hide-city-labels", !showLabels);
}

function updatePoiVisibility() {
  const shouldShow = activeCategoryFilter !== null || map.getZoom() >= POI_MIN_ZOOM;
  if (shouldShow && !map.hasLayer(poiMarkersLayer)) {
    map.addLayer(poiMarkersLayer);
  } else if (!shouldShow && map.hasLayer(poiMarkersLayer)) {
    map.removeLayer(poiMarkersLayer);
  }
}

const timelineEl = document.getElementById("timeline");
const yearSliderEl = document.getElementById("year-slider");
const yearLabelEl = document.getElementById("year-label");

// Placeholder range until the real Wayback release list loads (or, if
// that fetch fails, what stays in effect as a fallback).
yearSliderEl.min = WAYBACK_FALLBACK_MIN_YEAR;
yearSliderEl.max = selectedYear;
yearSliderEl.value = selectedYear;
loadWaybackReleases();

function updateYearLabel() {
  yearLabelEl.textContent = t("yearLabel")(selectedYear);
}

yearSliderEl.addEventListener("input", () => {
  selectedYear = Number(yearSliderEl.value);
  updateYearLabel();
  applySelectedYear();
});

function updateTimelineVisibility(activeLayer) {
  timelineEl.hidden = activeLayer !== historicalLayer;
}

map.on("baselayerchange", (event) => {
  updateMarkersVisibility(event.layer);
  updateTimelineVisibility(event.layer);
});
map.on("zoomend", updatePoiVisibility);
updateMarkersVisibility(streetLayer);
updateTimelineVisibility(streetLayer);
updatePoiVisibility();
updateYearLabel();
const statusEl = document.getElementById("status");
const listEl = document.getElementById("city-list");
const detailEl = document.getElementById("city-detail");
const panelEl = document.getElementById("panel");
const panelToggleEl = document.getElementById("panel-toggle");
const railCitiesEl = document.getElementById("rail-cities");
const railPlacesEl = document.getElementById("rail-places");
const railForumEl = document.getElementById("rail-forum");
const panelViewCitiesEl = document.getElementById("panel-view-cities");
const panelViewPlacesEl = document.getElementById("panel-view-places");
const panelViewForumEl = document.getElementById("panel-view-forum");
const categoryGridEl = document.getElementById("category-grid");
const weatherCityEl = document.getElementById("weather-city");
const weatherIconEl = document.getElementById("weather-icon");
const weatherTempEl = document.getElementById("weather-temp");
const weatherDescEl = document.getElementById("weather-desc");
const weatherMetaEl = document.getElementById("weather-meta");
const titleEl = document.getElementById("app-title");
const searchInputEl = document.getElementById("search-input");
const langSwitcherEl = document.getElementById("lang-switcher");
const langToggleEl = document.getElementById("lang-toggle");
const langToggleLabelEl = document.getElementById("lang-toggle-label");
const langMenuEl = document.getElementById("lang-menu");
const themeToggleEl = document.getElementById("theme-toggle");

function closeLangMenu() {
  langMenuEl.hidden = true;
  langToggleEl.setAttribute("aria-expanded", "false");
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  titleEl.textContent = t("title");
  searchInputEl.placeholder = t("searchPlaceholder");
  railCitiesEl.setAttribute("aria-label", t("citiesToggle"));
  railCitiesEl.title = t("citiesToggle");
  railPlacesEl.setAttribute("aria-label", t("placesToggle"));
  railPlacesEl.title = t("placesToggle");
  railForumEl.setAttribute("aria-label", t("forumToggle"));
  railForumEl.title = t("forumToggle");
  themeToggleEl.setAttribute("aria-label", t("themeToggle"));
  themeToggleEl.title = t("themeToggle");
  updateYearLabel();
  panelToggleEl.setAttribute(
    "aria-label",
    panelEl.classList.contains("collapsed") ? t("sidebarOpen") : t("sidebarClose")
  );
  langToggleLabelEl.textContent = currentLang.toUpperCase();
  Array.from(langMenuEl.children).forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === currentLang);
  });
}

langToggleEl.addEventListener("click", (event) => {
  event.stopPropagation();
  const willOpen = langMenuEl.hidden;
  langMenuEl.hidden = !willOpen;
  langToggleEl.setAttribute("aria-expanded", String(willOpen));
});

langMenuEl.addEventListener("click", (event) => {
  const lang = event.target.dataset.lang;
  closeLangMenu();
  if (!lang || lang === currentLang || !TRANSLATIONS[lang]) {
    return;
  }
  currentLang = lang;
  setStoredLang(lang);
  applyStaticTranslations();
  refreshLayerControl();
  renderCategoryGrid();
  renderWeatherPanel();
  // Only the labels change here, not the underlying data, so don't
  // re-fit the map to the markers — that was resetting the user's pan
  // and zoom on every language switch.
  applyFilterAndRender({ fitBounds: false });
  // The admin panel is a full-screen modal, so it's never open at the
  // same time as the language switcher — its dynamic content only needs
  // to be in the right language when it's (re)opened, which
  // openAdminPanel() already handles. Just keep the always-visible
  // "Manage" button in sync here.
  if (typeof applyAdminStaticTranslations === "function") {
    applyAdminStaticTranslations();
  }
  if (typeof applyForumStaticTranslations === "function") {
    applyForumStaticTranslations();
  }
});

document.addEventListener("click", (event) => {
  if (!langSwitcherEl.contains(event.target)) {
    closeLangMenu();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLangMenu();
  }
});

// Fills every [data-icon] element in the static HTML with its inline
// SVG, so index.html names an icon once and never carries path data.
// Icons inherit currentColor, which is what lets .rail-btn.active flip
// them to white through CSS alone.
function hydrateStaticIcons() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = KBA_ICON_SVG(el.dataset.icon, 19);
  });
}

// Everything that has to change when the system flips between light and
// dark: the basemap, and the marker/grid tones drawn on top of it. The
// app's own chrome needs nothing here — style.css already swaps its
// color tokens under prefers-color-scheme.
//
// Markers can't be restyled in place (their color is baked into each
// divIcon's HTML at build time), so this re-renders them — without
// re-fitting the map, which would throw away the user's current pan and
// zoom for what is only a repaint.
function applyColorScheme() {
  streetLayer.setUrl(STREET_TILE_URLS[scheme()]);
  renderCategoryGrid();
  applyFilterAndRender({ fitBounds: false });
  renderWeatherPanel();
}

darkModeQuery.addEventListener("change", applyColorScheme);

// Sun/moon reflects the *current* effective theme (like the lang-toggle
// showing the active language code, not the one you'd switch to) —
// aria-pressed carries the same state for assistive tech, since the
// icon swap alone isn't announced.
function updateThemeToggleIcon() {
  const dark = scheme() === "dark";
  themeToggleEl.dataset.icon = dark ? "theme_dark" : "theme_light";
  themeToggleEl.innerHTML = KBA_ICON_SVG(themeToggleEl.dataset.icon, 19);
  themeToggleEl.setAttribute("aria-pressed", String(dark));
}

function toggleTheme() {
  const next = scheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  setStoredTheme(next);
  updateThemeToggleIcon();
  applyColorScheme();
}

themeToggleEl.addEventListener("click", toggleTheme);

hydrateStaticIcons();
updateThemeToggleIcon();
applyStaticTranslations();
renderCategoryGrid();

let activePanelTab = "cities";

function setPanelCollapsed(collapsed) {
  panelEl.classList.toggle("collapsed", collapsed);
  panelToggleEl.textContent = collapsed ? "›" : "‹";
  panelToggleEl.setAttribute(
    "aria-label",
    collapsed ? t("sidebarOpen") : t("sidebarClose")
  );
  // The map sits beside the panel's own space (it doesn't overlay it on
  // desktop — see #panel's width transition in style.css), so Leaflet
  // needs to know its visible area changed once that transition ends.
  setTimeout(() => map.invalidateSize(), 220);
}

// Rail buttons double as tab switches (Cities/Places) and, if you click
// the already-active tab again, a close gesture — same toggle-to-close
// behavior the old Cities button had, just extended to two tabs sharing
// one panel instead of each having its own independent show/hide.
function selectPanelTab(tab) {
  if (activePanelTab === tab && !panelEl.classList.contains("collapsed")) {
    setPanelCollapsed(true);
    return;
  }
  activePanelTab = tab;
  railCitiesEl.classList.toggle("active", tab === "cities");
  railPlacesEl.classList.toggle("active", tab === "places");
  railForumEl.classList.toggle("active", tab === "forum");
  panelViewCitiesEl.hidden = tab !== "cities";
  panelViewPlacesEl.hidden = tab !== "places";
  panelViewForumEl.hidden = tab !== "forum";
  // forum.js (loaded after this file) owns the general-opinions list —
  // defensive check for the same reason applyAdminStaticTranslations()
  // gets one below: script load order guarantees it exists by the time
  // any of this actually runs (nothing calls selectPanelTab() until
  // after every <script> tag has executed), but staying defensive here
  // costs nothing and matches the existing convention.
  if (tab === "forum" && typeof loadGeneralForumPosts === "function") {
    loadGeneralForumPosts();
  }
  setPanelCollapsed(false);
}

panelToggleEl.addEventListener("click", () => {
  setPanelCollapsed(!panelEl.classList.contains("collapsed"));
});

// Deselects whatever city/POI is currently shown in #city-detail (and,
// via updateForumGeneralVisibility(), brings the general forum section
// back if it was hidden for that selection).
function clearSelectedPlace() {
  detailEl.innerHTML = "";
  Array.from(listEl.children).forEach((li) => li.classList.remove("active"));
  if (typeof updateForumGeneralVisibility === "function") {
    updateForumGeneralVisibility();
  }
}

railCitiesEl.addEventListener("click", () => selectPanelTab("cities"));
railPlacesEl.addEventListener("click", () => selectPanelTab("places"));
railForumEl.addEventListener("click", () => {
  // A selected place's own forum widget hides the general one (see
  // updateForumGeneralVisibility() in forum.js) — clicking Forum again
  // while that's the case is a "go back to the general forum" gesture,
  // not the usual toggle-to-close. Toggle-to-close still applies once
  // there's nothing left to go back from (already at the general view).
  const placeSelected = Boolean(detailEl.firstElementChild);
  if (activePanelTab === "forum" && !panelEl.classList.contains("collapsed") && placeSelected) {
    clearSelectedPlace();
    if (typeof loadGeneralForumPosts === "function") {
      loadGeneralForumPosts();
    }
    return;
  }
  selectPanelTab("forum");
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function setStatus(message, isError) {
  statusEl.textContent = message;
  statusEl.hidden = !message;
  statusEl.classList.toggle("error", Boolean(isError));
}

function localizedName(city) {
  return (city.name_i18n && city.name_i18n[currentLang]) || city.name;
}

function localizedDescription(city) {
  return (
    (city.description_i18n && city.description_i18n[currentLang]) ||
    city.description
  );
}

function cityInfoHtml(city) {
  const name = localizedName(city);
  const description = localizedDescription(city);
  const parts = [`<strong>${escapeHtml(name)}</strong>`];
  if (city.alt_names) {
    parts.push(`<br><em>${escapeHtml(city.alt_names)}</em>`);
  }
  if (city.image_url) {
    parts.push(
      `<img class="popup-image" src="${escapeAttr(city.image_url)}" ` +
        `alt="${escapeAttr(name)}">`
    );
  }
  if (description) {
    parts.push(`<p>${escapeHtml(description)}</p>`);
  } else {
    parts.push(`<p class="no-info">${escapeHtml(t("noInfo"))}</p>`);
  }
  if (city.image_credit) {
    parts.push(`<p class="image-credit">${escapeHtml(city.image_credit)}</p>`);
  }
  return parts.join("");
}

// Open-Meteo's WMO weather codes -> icon/label. Kept in English only —
// Open-Meteo doesn't provide localized condition text itself, and
// translating all ~28 possible codes across 4 languages isn't worth it
// for a single line of secondary text next to a temperature and icon.
//
// `icon` names an entry in KBA_ICON_PATHS. Several codes deliberately
// share one icon — the label beside it already carries the detail (a
// separate glyph for "moderate" vs. "dense drizzle" would be a
// distinction no one could read at 20px).
const WEATHER_CODES = {
  0: { icon: "weather_clear", label: "Clear sky" },
  1: { icon: "weather_clear", label: "Mainly clear" },
  2: { icon: "weather_cloudy", label: "Partly cloudy" },
  3: { icon: "weather_cloudy", label: "Overcast" },
  45: { icon: "weather_fog", label: "Fog" },
  48: { icon: "weather_fog", label: "Depositing rime fog" },
  51: { icon: "weather_rain", label: "Light drizzle" },
  53: { icon: "weather_rain", label: "Moderate drizzle" },
  55: { icon: "weather_rain", label: "Dense drizzle" },
  56: { icon: "weather_rain", label: "Light freezing drizzle" },
  57: { icon: "weather_rain", label: "Dense freezing drizzle" },
  61: { icon: "weather_rain", label: "Slight rain" },
  63: { icon: "weather_rain", label: "Moderate rain" },
  65: { icon: "weather_rain", label: "Heavy rain" },
  66: { icon: "weather_rain", label: "Light freezing rain" },
  67: { icon: "weather_rain", label: "Heavy freezing rain" },
  71: { icon: "weather_snow", label: "Slight snow fall" },
  73: { icon: "weather_snow", label: "Moderate snow fall" },
  75: { icon: "weather_snow", label: "Heavy snow fall" },
  77: { icon: "weather_grains", label: "Snow grains" },
  80: { icon: "weather_rain", label: "Slight rain showers" },
  81: { icon: "weather_rain", label: "Moderate rain showers" },
  82: { icon: "weather_storm", label: "Violent rain showers" },
  85: { icon: "weather_snow", label: "Slight snow showers" },
  86: { icon: "weather_snow", label: "Heavy snow showers" },
  95: { icon: "weather_storm", label: "Thunderstorm" },
  96: { icon: "weather_storm", label: "Thunderstorm, slight hail" },
  99: { icon: "weather_storm", label: "Thunderstorm, heavy hail" },
};

function weatherInfo(code) {
  return WEATHER_CODES[code] || { icon: "weather_unknown", label: "—" };
}

// The city/point currently shown in the weather panel, and its last
// successfully fetched reading — kept separately from the fetch itself
// so a language switch can re-render (translated labels, localized
// city name) without re-hitting the API.
let weatherCity = null;
let weatherCurrent = null;

function renderWeatherPanel() {
  if (!weatherCity) {
    return;
  }
  weatherCityEl.textContent = localizedName(weatherCity);
  if (!weatherCurrent) {
    weatherIconEl.innerHTML = "";
    weatherTempEl.textContent = "";
    weatherDescEl.textContent = t("weatherLoading");
    weatherMetaEl.textContent = "";
    return;
  }
  const info = weatherInfo(weatherCurrent.weather_code);
  weatherIconEl.innerHTML = KBA_ICON_SVG(info.icon, 26);
  weatherTempEl.textContent = `${Math.round(weatherCurrent.temperature_2m)}°C`;
  weatherDescEl.textContent = info.label;
  weatherMetaEl.textContent =
    `${t("weatherHumidity")}: ${weatherCurrent.relative_humidity_2m}% · ` +
    `${t("weatherWind")}: ${Math.round(weatherCurrent.wind_speed_10m)} km/h`;
}

async function loadWeatherFor(city) {
  weatherCity = city;
  weatherCurrent = null;
  renderWeatherPanel();
  try {
    const url =
      `https://api.open-meteo.com/v1/forecast?latitude=${city.latitude}` +
      `&longitude=${city.longitude}&current=temperature_2m,weather_code,` +
      `wind_speed_10m,relative_humidity_2m&timezone=auto`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Weather API returned ${res.status}`);
    }
    const data = await res.json();
    // Bail if the selection moved on to a different city while this
    // request was in flight — don't clobber a newer selection.
    if (weatherCity !== city) {
      return;
    }
    weatherCurrent = data.current;
    renderWeatherPanel();
  } catch (err) {
    if (weatherCity !== city) {
      return;
    }
    weatherIconEl.innerHTML = "";
    weatherTempEl.textContent = "";
    weatherDescEl.textContent = t("weatherError");
    weatherMetaEl.textContent = "";
  }
}

function showCityDetail(city) {
  detailEl.innerHTML = cityInfoHtml(city);
  Array.from(listEl.children).forEach((li) => {
    li.classList.toggle("active", li.dataset.cityId === city.id);
  });
  loadWeatherFor(city);
  // forum.js owns the per-place opinions widget — see the comment on
  // the same pattern in selectPanelTab() above.
  if (typeof renderCityForumSection === "function") {
    renderCityForumSection(detailEl, city);
  }
}

// Not true geographic distance (no latitude-scaling correction) — just
// good enough to rank ~12 candidate cities against each other over a
// region as small as Karabakh, which is all this needs.
function squaredDistance(lat1, lng1, lat2, lng2) {
  const dLat = lat1 - lat2;
  const dLng = lng1 - lng2;
  return dLat * dLat + dLng * dLng;
}

function nearestCityTo(lat, lng) {
  const candidates = lastCities.filter((c) => !isPoi(c));
  if (candidates.length === 0) {
    return null;
  }
  return candidates.reduce((closest, city) =>
    squaredDistance(lat, lng, city.latitude, city.longitude) <
    squaredDistance(lat, lng, closest.latitude, closest.longitude)
      ? city
      : closest
  );
}

let mapMoveWeatherTimer = null;

// Weather follows the map: panning/zooming (once it settles — moveend,
// not every intermediate frame) re-centers the panel on whichever known
// city is now closest to the middle of the view. Debounced so a quick
// drag or scroll-zoom doesn't fire a burst of API calls; only actually
// refetches when the nearest city changes, so lingering in one area
// doesn't either. An explicit selection (sidebar/marker click, search)
// still wins in the moment via showCityDetail() above — this just picks
// back up from wherever the map ends up after that.
function scheduleWeatherUpdateForMapView() {
  clearTimeout(mapMoveWeatherTimer);
  mapMoveWeatherTimer = setTimeout(() => {
    if (lastCities.length === 0) {
      return;
    }
    const center = map.getCenter();
    const candidate = nearestCityTo(center.lat, center.lng);
    if (candidate && (!weatherCity || candidate.id !== weatherCity.id)) {
      loadWeatherFor(candidate);
    }
  }, 500);
}

map.on("moveend", scheduleWeatherUpdateForMapView);

function isPoi(city) {
  return Boolean(city.category) && city.category !== "city";
}

function categoryLabel(value) {
  return (t("categories") && t("categories")[value]) || value;
}

// Every POI category becomes a grid entry — Object.keys(POI_TONES) is
// already exactly that list (it excludes "city", the only non-POI
// category), so there's nothing extra to keep in sync here beyond
// POI_TONES itself. Mirrors Apple Maps' "Find Nearby" grid: a circular
// icon plus a label, two per row.
function renderCategoryGrid() {
  categoryGridEl.innerHTML = "";
  Object.keys(POI_TONES).forEach((category) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "category-grid-item";
    item.classList.toggle("active", activeCategoryFilter === category);
    item.innerHTML =
      `<span class="category-grid-icon" style="background:${poiToneColor(category)}">` +
      `${KBA_ICON_SVG(category, 14, POI_GLYPH[scheme()])}</span>` +
      `<span class="category-grid-label">${escapeHtml(categoryLabel(category))}</span>`;
    item.addEventListener("click", () => {
      // Clicking the already-active item clears the filter — same
      // toggle-off gesture as Google Maps' own category chips had.
      activeCategoryFilter = activeCategoryFilter === category ? null : category;
      renderCategoryGrid();
      updatePoiVisibility();
      applyFilterAndRender({ fitBounds: false });
    });
    categoryGridEl.appendChild(item);
  });
}

function buildMarker(city) {
  if (isPoi(city)) {
    const name = localizedName(city);
    // iconSize: null (like the city label below) lets the wrapper size
    // itself to its content instead of clipping the name — POI markers
    // already only render once zoomed in (or a category filter is
    // active; see updatePoiVisibility), the same point most other map
    // apps start showing place names.
    const badgeIcon = L.divIcon({
      className: "poi-marker-wrapper",
      html:
        `<div class="poi-marker" style="background:${poiToneColor(city.category)};` +
        `border-color:${POI_RING[scheme()]}">` +
        `${KBA_ICON_SVG(city.category, 15, POI_GLYPH[scheme()])}</div>` +
        `<span class="poi-marker-label">${escapeHtml(name)}</span>`,
      iconSize: null,
      iconAnchor: [13, 13],
    });
    return L.marker([city.latitude, city.longitude], { icon: badgeIcon })
      .addTo(poiMarkersLayer);
  }
  const name = localizedName(city);
  const labelIcon = L.divIcon({
    className: "city-label",
    html: escapeHtml(name),
    iconSize: null,
    iconAnchor: [0, 0],
  });
  return L.marker([city.latitude, city.longitude], { icon: labelIcon })
    .addTo(markersLayer);
}

// city.id -> { city, marker }, rebuilt on every render — lets search
// (and anything else) jump straight to a marker without re-deriving it
// from the DOM.
let cityMarkers = new Map();

// Points of interest only render once zoomed in past POI_MIN_ZOOM (see
// updatePoiVisibility), so jumping straight to one needs a zoom level
// past that threshold or its marker/popup won't actually be on the map
// yet. Regular cities keep the zoom level list clicks have always used.
const POI_JUMP_ZOOM = 16;
const CITY_JUMP_ZOOM = 12;

function jumpToCity(city, marker) {
  // animate: false avoids a real Leaflet bug: search filters as you
  // type (via its own animated fitBounds), so hitting Enter right after
  // typing can call setView() while that animation is still in flight —
  // Leaflet then settles on an intermediate zoom instead of the one
  // just requested here. An instant jump sidesteps the collision
  // entirely, and reads as snappier for a deliberate "go here" action.
  map.setView(
    [city.latitude, city.longitude],
    isPoi(city) ? POI_JUMP_ZOOM : CITY_JUMP_ZOOM,
    { animate: false }
  );
  // setView's zoom change normally reaches updatePoiVisibility via the
  // map's own "zoomend" listener, but that can land after this function
  // returns — call it directly so a POI's marker/label is already on
  // the map by the time showCityDetail() below scrolls it into view.
  updatePoiVisibility();
  showCityDetail(city);
}

function buildListItem(city, marker) {
  const li = document.createElement("li");
  li.textContent = localizedName(city);
  li.dataset.cityId = city.id;
  li.addEventListener("click", () => jumpToCity(city, marker));
  listEl.appendChild(li);
}

function renderCities(cities, { fitBounds = true } = {}) {
  markersLayer.clearLayers();
  poiMarkersLayer.clearLayers();
  listEl.innerHTML = "";
  detailEl.innerHTML = "";
  cityMarkers = new Map();
  // A re-render (search, filter, reload) implicitly clears whatever
  // place was selected — bring the general forum section back if it
  // was hidden for that selection. See the comment on the same pattern
  // in selectPanelTab() above.
  if (typeof updateForumGeneralVisibility === "function") {
    updateForumGeneralVisibility();
  }

  if (cities.length === 0) {
    setStatus(t("noCities"), false);
    return;
  }

  // No "N cities loaded" message once there's data — the sidebar list
  // itself already shows what's loaded.
  setStatus("", false);

  const bounds = [];
  cities.forEach((city) => {
    const marker = buildMarker(city);
    // No map popup — clicking a marker shows its info in the sidebar
    // (#city-detail) instead, via showCityDetail() below, so a second
    // "info card" floating on the map itself would just be redundant.
    marker.on("click", () => showCityDetail(city));
    cityMarkers.set(city.id, { city, marker });
    bounds.push([city.latitude, city.longitude]);
    // Roads and other points of interest still show up as markers on
    // the map, but only cities get a sidebar entry — the sidebar is
    // meant as a quick city index, not a listing of every added point.
    if (!isPoi(city)) {
      buildListItem(city, marker);
    }
  });

  if (fitBounds) {
    // animate: false — this re-fits on every search keystroke, and an
    // in-flight fitBounds animation can still be resolving when the
    // next one (or a deliberate jumpToCity()) fires right after, which
    // makes Leaflet settle on a stale intermediate zoom instead of
    // whichever view was actually requested last. Instant avoids the
    // whole class of interrupted-animation bugs.
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11, animate: false });
  }
}

function matchesSearch(city) {
  if (!searchQuery) {
    return true;
  }
  const q = searchQuery.toLowerCase();
  return (
    localizedName(city).toLowerCase().includes(q) ||
    city.name.toLowerCase().includes(q)
  );
}

// Regular cities are unaffected by the category filter (it's a POI
// concept — "show me the cafes", not "hide every non-cafe city"); only
// POIs get excluded when their category doesn't match the active one.
function matchesActiveFilters(city) {
  if (!matchesSearch(city)) {
    return false;
  }
  if (activeCategoryFilter && isPoi(city) && city.category !== activeCategoryFilter) {
    return false;
  }
  return true;
}

function applyFilterAndRender(options) {
  renderCities(lastCities.filter(matchesActiveFilters), options);
}

searchInputEl.addEventListener("input", () => {
  searchQuery = searchInputEl.value.trim();
  applyFilterAndRender();
});

searchInputEl.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || !searchQuery) {
    return;
  }
  event.preventDefault();
  // Jump to the top match currently shown — same ranked order as the
  // sidebar list (and includes POIs, which the sidebar itself doesn't
  // list but the map still does).
  const [topMatch] = lastCities.filter(matchesActiveFilters);
  if (!topMatch) {
    return;
  }
  const entry = cityMarkers.get(topMatch.id);
  if (!entry) {
    return;
  }
  jumpToCity(entry.city, entry.marker);
  searchInputEl.blur();
});

async function loadCities() {
  try {
    const res = await fetch(`${API_BASE}/cities`);
    if (!res.ok) {
      throw new Error(`API returned ${res.status}`);
    }
    const cities = await res.json();
    lastCities = cities;
    applyFilterAndRender();
    if (!weatherCity && cities.length > 0) {
      // Default weather panel content before anything's been clicked —
      // Khankendi if it's there, otherwise just whatever loaded first.
      const defaultCity = cities.find((c) => c.name === "Khankendi") || cities[0];
      loadWeatherFor(defaultCity);
    }
  } catch (err) {
    setStatus(t("apiError")(API_BASE, err.message), true);
  }
}

setStatus(t("loading"), false);
loadCities();
