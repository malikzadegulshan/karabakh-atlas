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

// Zoom control moves to the bottom-right (Leaflet's default top-left spot
// would sit right under the floating search bar/buttons).
const map = L.map("map", { zoomControl: false }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
L.control.zoom({ position: "bottomright" }).addTo(map);

// CartoDB Positron: a clean, free/keyless basemap with place labels but
// no baked-in amenity icons (cafe/restaurant/etc.), so our own
// points-of-interest markers stay legible instead of competing with
// icons we can't control.
const streetLayer = L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
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

// Keep in sync with CITY_CATEGORIES in api/v1/views/cities.py.
const POI_COLORS = {
  road: "#57534e",
  cafe: "#b45309",
  restaurant: "#b91c1c",
  hotel: "#1d4ed8",
  landmark: "#7c3aed",
  museum: "#0f766e",
  park: "#15803d",
  university: "#4338ca",
  school: "#4f46e5",
  hospital: "#dc2626",
  pharmacy: "#16a34a",
  bank: "#065f46",
  government: "#374151",
  police: "#1e3a8a",
  fire_station: "#c2410c",
  mosque: "#0891b2",
  church: "#0e7490",
  fuel_station: "#78350f",
  parking: "#525252",
  shop: "#c2410c",
  other: "#334155",
};

// Keep in sync with CITY_CATEGORIES in api/v1/views/cities.py.
const POI_ICONS = {
  road: "🛣️",
  cafe: "☕",
  restaurant: "🍽️",
  hotel: "🏨",
  landmark: "🗿",
  museum: "🏛️",
  park: "🌳",
  university: "🎓",
  school: "📚",
  hospital: "🏥",
  pharmacy: "💊",
  bank: "🏦",
  government: "🏢",
  police: "👮",
  fire_station: "🚒",
  mosque: "🕌",
  church: "⛪",
  fuel_station: "⛽",
  parking: "🅿️",
  shop: "🛍️",
  other: "📍",
};

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
const sidebarEl = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebar-toggle");
const citiesToggleEl = document.getElementById("cities-toggle");
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
const placesToggleEl = document.getElementById("places-toggle");
const categoryFilterBarEl = document.getElementById("category-filter-bar");
const categoryFilterCloseEl = document.getElementById("category-filter-close");
const categoryFilterChipsEl = document.getElementById("category-filter-chips");
let placesPanelOpen = false;

function setPlacesPanelOpen(open) {
  placesPanelOpen = open;
  categoryFilterBarEl.hidden = !open;
  placesToggleEl.classList.toggle("active", open);
  placesToggleEl.setAttribute("aria-expanded", String(open));
}

placesToggleEl.addEventListener("click", () => setPlacesPanelOpen(!placesPanelOpen));
categoryFilterCloseEl.addEventListener("click", () => setPlacesPanelOpen(false));

function closeLangMenu() {
  langMenuEl.hidden = true;
  langToggleEl.setAttribute("aria-expanded", "false");
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  titleEl.textContent = t("title");
  searchInputEl.placeholder = t("searchPlaceholder");
  placesToggleEl.textContent = t("placesToggle");
  citiesToggleEl.textContent = t("citiesToggle");
  categoryFilterCloseEl.setAttribute("aria-label", t("adminClose"));
  updateYearLabel();
  sidebarToggleEl.setAttribute(
    "aria-label",
    sidebarEl.classList.contains("collapsed") ? t("sidebarOpen") : t("sidebarClose")
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
  renderCategoryFilterBar();
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

applyStaticTranslations();
renderCategoryFilterBar();

function setSidebarCollapsed(collapsed) {
  sidebarEl.classList.toggle("collapsed", collapsed);
  sidebarToggleEl.textContent = collapsed ? "›" : "‹";
  sidebarToggleEl.setAttribute(
    "aria-label",
    collapsed ? t("sidebarOpen") : t("sidebarClose")
  );
  citiesToggleEl.classList.toggle("active", !collapsed);
  citiesToggleEl.setAttribute("aria-expanded", String(!collapsed));
  // The map sits behind the sidebar's own space (it doesn't overlay it
  // on desktop — see aside's width transition in style.css), so Leaflet
  // needs to know its visible area changed once that transition ends.
  setTimeout(() => map.invalidateSize(), 220);
}

sidebarToggleEl.addEventListener("click", () => {
  setSidebarCollapsed(!sidebarEl.classList.contains("collapsed"));
});

citiesToggleEl.addEventListener("click", () => {
  setSidebarCollapsed(!sidebarEl.classList.contains("collapsed"));
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
const WEATHER_CODES = {
  0: { icon: "☀️", label: "Clear sky" },
  1: { icon: "🌤️", label: "Mainly clear" },
  2: { icon: "⛅", label: "Partly cloudy" },
  3: { icon: "☁️", label: "Overcast" },
  45: { icon: "🌫️", label: "Fog" },
  48: { icon: "🌫️", label: "Depositing rime fog" },
  51: { icon: "🌦️", label: "Light drizzle" },
  53: { icon: "🌦️", label: "Moderate drizzle" },
  55: { icon: "🌦️", label: "Dense drizzle" },
  56: { icon: "🌧️", label: "Light freezing drizzle" },
  57: { icon: "🌧️", label: "Dense freezing drizzle" },
  61: { icon: "🌧️", label: "Slight rain" },
  63: { icon: "🌧️", label: "Moderate rain" },
  65: { icon: "🌧️", label: "Heavy rain" },
  66: { icon: "🌧️", label: "Light freezing rain" },
  67: { icon: "🌧️", label: "Heavy freezing rain" },
  71: { icon: "🌨️", label: "Slight snow fall" },
  73: { icon: "🌨️", label: "Moderate snow fall" },
  75: { icon: "❄️", label: "Heavy snow fall" },
  77: { icon: "❄️", label: "Snow grains" },
  80: { icon: "🌦️", label: "Slight rain showers" },
  81: { icon: "🌦️", label: "Moderate rain showers" },
  82: { icon: "⛈️", label: "Violent rain showers" },
  85: { icon: "🌨️", label: "Slight snow showers" },
  86: { icon: "❄️", label: "Heavy snow showers" },
  95: { icon: "⛈️", label: "Thunderstorm" },
  96: { icon: "⛈️", label: "Thunderstorm, slight hail" },
  99: { icon: "⛈️", label: "Thunderstorm, heavy hail" },
};

function weatherInfo(code) {
  return WEATHER_CODES[code] || { icon: "🌡️", label: "—" };
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
    weatherIconEl.textContent = "";
    weatherTempEl.textContent = "";
    weatherDescEl.textContent = t("weatherLoading");
    weatherMetaEl.textContent = "";
    return;
  }
  const info = weatherInfo(weatherCurrent.weather_code);
  weatherIconEl.textContent = info.icon;
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
    weatherIconEl.textContent = "";
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

// Every POI category becomes a filter chip — Object.keys(POI_ICONS) is
// already exactly that list (it excludes "city", the only non-POI
// category), so there's nothing extra to keep in sync here beyond
// POI_ICONS/POI_COLORS themselves.
function renderCategoryFilterBar() {
  categoryFilterChipsEl.innerHTML = "";
  Object.keys(POI_ICONS).forEach((category) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "category-chip";
    chip.classList.toggle("active", activeCategoryFilter === category);
    chip.innerHTML =
      `<span class="category-chip-icon">${POI_ICONS[category]}</span>` +
      escapeHtml(categoryLabel(category));
    chip.addEventListener("click", () => {
      // Clicking the already-active chip clears the filter — same
      // toggle-off gesture as Google Maps' own category chips.
      activeCategoryFilter = activeCategoryFilter === category ? null : category;
      renderCategoryFilterBar();
      updatePoiVisibility();
      applyFilterAndRender({ fitBounds: false });
    });
    categoryFilterChipsEl.appendChild(chip);
  });
}

function buildMarker(city) {
  if (isPoi(city)) {
    const badgeIcon = L.divIcon({
      className: "poi-marker-wrapper",
      html:
        `<div class="poi-marker" style="background:${POI_COLORS[city.category] || POI_COLORS.other}">` +
        `${POI_ICONS[city.category] || POI_ICONS.other}</div>`,
      iconSize: [26, 26],
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
  // returns — call it directly so a POI's layer is already on the map
  // by the time openPopup() runs immediately below.
  updatePoiVisibility();
  marker.openPopup();
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
    marker.bindPopup(cityInfoHtml(city));
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
