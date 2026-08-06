const API_BASE = window.KBA_API_BASE || "http://localhost:5000/api/v1";
const DEFAULT_CENTER = [39.8, 46.75];
const DEFAULT_ZOOM = 9;

let currentLang = getStoredLang() || DEFAULT_LANG;
if (!TRANSLATIONS[currentLang]) {
  currentLang = DEFAULT_LANG;
}
let lastCities = [];
let layerControl = null;

function t(key) {
  return TRANSLATIONS[currentLang][key];
}

const map = L.map("map").setView(DEFAULT_CENTER, DEFAULT_ZOOM);

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

streetLayer.addTo(map);

function refreshLayerControl() {
  if (layerControl) {
    map.removeControl(layerControl);
  }
  layerControl = L.control
    .layers(
      { [t("layerStreets")]: streetLayer, [t("layerSatellite")]: satelliteLayer },
      null,
      { position: "topleft" }
    )
    .addTo(map);
}

refreshLayerControl();

// Street tiles already render place-name labels on their own, so our
// custom city-name markers would be redundant there; only show them
// over satellite imagery, which has no labels of its own.
const markersLayer = L.layerGroup();

// Points of interest (cafes, restaurants, etc.) are shown on both tile
// layers, but only once zoomed in enough — otherwise a full set of them
// would look chaotic at the region-wide view.
const POI_MIN_ZOOM = 14;
const poiMarkersLayer = L.layerGroup();

function updateMarkersVisibility(activeLayer) {
  if (activeLayer === satelliteLayer) {
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

map.on("baselayerchange", (event) => updateMarkersVisibility(event.layer));
map.on("zoomend", updatePoiVisibility);
updateMarkersVisibility(streetLayer);
updatePoiVisibility();
const statusEl = document.getElementById("status");
const listEl = document.getElementById("city-list");
const detailEl = document.getElementById("city-detail");
const sidebarEl = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebar-toggle");
const titleEl = document.getElementById("app-title");
const subtitleEl = document.getElementById("app-subtitle");
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
  subtitleEl.textContent = t("subtitle");
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
  renderCities(lastCities);
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
    const name = localizedName(city);
    const marker = buildMarker(city);
    marker.bindPopup(cityInfoHtml(city));
    marker.on("click", () => showCityDetail(city));
    bounds.push([city.latitude, city.longitude]);

    const li = document.createElement("li");
    li.textContent = name;
    li.dataset.cityId = city.id;
    li.addEventListener("click", () => {
      const targetZoom = isPoi(city)
        ? Math.max(map.getZoom(), POI_MIN_ZOOM)
        : 12;
      map.setView([city.latitude, city.longitude], targetZoom);
      if (isPoi(city) && !map.hasLayer(poiMarkersLayer)) {
        // Make sure the marker is actually on the map (zoomend, which
        // normally handles this, may not have fired yet) before opening
        // its popup.
        map.addLayer(poiMarkersLayer);
      }
      marker.openPopup();
      showCityDetail(city);
    });
    listEl.appendChild(li);
  });

  map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
}

async function loadCities() {
  try {
    const res = await fetch(`${API_BASE}/cities`);
    if (!res.ok) {
      throw new Error(`API returned ${res.status}`);
    }
    const cities = await res.json();
    lastCities = cities;
    renderCities(cities);
  } catch (err) {
    setStatus(t("apiError")(API_BASE, err.message), true);
  }
}

setStatus(t("loading"), false);
loadCities();
