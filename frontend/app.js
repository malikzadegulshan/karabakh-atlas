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
// custom city-name markers would be redundant there; only show them
// over satellite/historical imagery, which has no labels of its own.
const markersLayer = L.layerGroup();

// Points of interest (cafes, restaurants, etc.) are shown on both tile
// layers, but only once zoomed in enough — otherwise a full set of them
// would look chaotic at the region-wide view.
const POI_MIN_ZOOM = 14;
const poiMarkersLayer = L.layerGroup();

function updateMarkersVisibility(activeLayer) {
  if (activeLayer === satelliteLayer || activeLayer === historicalLayer) {
    if (!map.hasLayer(markersLayer)) {
      map.addLayer(markersLayer);
    }
  } else if (map.hasLayer(markersLayer)) {
    map.removeLayer(markersLayer);
  }
}

function updatePoiVisibility() {
  const shouldShow = map.getZoom() >= POI_MIN_ZOOM;
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
const titleEl = document.getElementById("app-title");
const searchInputEl = document.getElementById("search-input");
const langSwitcherEl = document.getElementById("lang-switcher");
const langToggleEl = document.getElementById("lang-toggle");
const langToggleLabelEl = document.getElementById("lang-toggle-label");
const langMenuEl = document.getElementById("lang-menu");

function closeLangMenu() {
  langMenuEl.hidden = true;
  langToggleEl.setAttribute("aria-expanded", "false");
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  titleEl.textContent = t("title");
  searchInputEl.placeholder = t("searchPlaceholder");
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
  applyFilterAndRender();
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

sidebarToggleEl.addEventListener("click", () => {
  const collapsed = sidebarEl.classList.toggle("collapsed");
  sidebarToggleEl.textContent = collapsed ? "›" : "‹";
  sidebarToggleEl.setAttribute(
    "aria-label",
    collapsed ? t("sidebarOpen") : t("sidebarClose")
  );
  setTimeout(() => map.invalidateSize(), 220);
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

function showCityDetail(city) {
  detailEl.innerHTML = cityInfoHtml(city);
  Array.from(listEl.children).forEach((li) => {
    li.classList.toggle("active", li.dataset.cityId === city.id);
  });
}

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

function isPoi(city) {
  return Boolean(city.category) && city.category !== "city";
}

function buildMarker(city) {
  if (isPoi(city)) {
    return L.circleMarker([city.latitude, city.longitude], {
      radius: 7,
      weight: 2,
      color: "#fff",
      fillColor: POI_COLORS[city.category] || POI_COLORS.other,
      fillOpacity: 0.9,
    }).addTo(poiMarkersLayer);
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

function buildListItem(city, marker) {
  const li = document.createElement("li");
  li.textContent = localizedName(city);
  li.dataset.cityId = city.id;
  li.addEventListener("click", () => {
    map.setView([city.latitude, city.longitude], 12);
    marker.openPopup();
    showCityDetail(city);
  });
  listEl.appendChild(li);
}

function renderCities(cities) {
  markersLayer.clearLayers();
  poiMarkersLayer.clearLayers();
  listEl.innerHTML = "";
  detailEl.innerHTML = "";

  if (cities.length === 0) {
    setStatus(t("noCities"), false);
    return;
  }

  setStatus(t("citiesLoaded")(cities.length), false);

  const bounds = [];
  cities.forEach((city) => {
    const marker = buildMarker(city);
    marker.bindPopup(cityInfoHtml(city));
    marker.on("click", () => showCityDetail(city));
    bounds.push([city.latitude, city.longitude]);
    // Roads and other points of interest still show up as markers on
    // the map, but only cities get a sidebar entry — the sidebar is
    // meant as a quick city index, not a listing of every added point.
    if (!isPoi(city)) {
      buildListItem(city, marker);
    }
  });

  map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
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

function applyFilterAndRender() {
  renderCities(lastCities.filter(matchesSearch));
}

searchInputEl.addEventListener("input", () => {
  searchQuery = searchInputEl.value.trim();
  applyFilterAndRender();
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
  } catch (err) {
    setStatus(t("apiError")(API_BASE, err.message), true);
  }
}

setStatus(t("loading"), false);
loadCities();
