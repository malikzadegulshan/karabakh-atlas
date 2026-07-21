const API_BASE = window.KBA_API_BASE || "http://localhost:5000/api/v1";
const DEFAULT_CENTER = [39.8, 46.75];
const DEFAULT_ZOOM = 9;

const map = L.map("map").setView(DEFAULT_CENTER, DEFAULT_ZOOM);

const streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
});

const satelliteLayer = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {
    maxZoom: 19,
    attribution:
      "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  }
);

streetLayer.addTo(map);

L.control
  .layers({ Streets: streetLayer, Satellite: satelliteLayer })
  .addTo(map);

const markersLayer = L.layerGroup().addTo(map);
const statusEl = document.getElementById("status");
const listEl = document.getElementById("city-list");
const detailEl = document.getElementById("city-detail");
const sidebarEl = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebar-toggle");

sidebarToggleEl.addEventListener("click", () => {
  const collapsed = sidebarEl.classList.toggle("collapsed");
  sidebarToggleEl.textContent = collapsed ? "›" : "‹";
  sidebarToggleEl.setAttribute(
    "aria-label",
    collapsed ? "Open city list" : "Close city list"
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

function cityInfoHtml(city) {
  const parts = [`<strong>${escapeHtml(city.name)}</strong>`];
  if (city.alt_names) {
    parts.push(`<br><em>${escapeHtml(city.alt_names)}</em>`);
  }
  if (city.image_url) {
    parts.push(
      `<img class="popup-image" src="${escapeAttr(city.image_url)}" ` +
        `alt="${escapeAttr(city.name)}">`
    );
  }
  if (city.description) {
    parts.push(`<p>${escapeHtml(city.description)}</p>`);
  } else {
    parts.push(`<p class="no-info">No information added for this city yet.</p>`);
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

function renderCities(cities) {
  markersLayer.clearLayers();
  listEl.innerHTML = "";
  detailEl.innerHTML = "";

  if (cities.length === 0) {
    setStatus(
      "Backend is reachable, but no cities have been added yet. " +
        "Use console.py or the API to add some.",
      false
    );
    return;
  }

  setStatus(`${cities.length} cit${cities.length === 1 ? "y" : "ies"} loaded.`, false);

  const bounds = [];
  cities.forEach((city) => {
    const labelIcon = L.divIcon({
      className: "city-label",
      html: escapeHtml(city.name),
      iconSize: null,
      iconAnchor: [0, 0],
    });
    const marker = L.marker([city.latitude, city.longitude], { icon: labelIcon })
      .addTo(markersLayer);
    marker.bindPopup(cityInfoHtml(city));
    marker.on("click", () => showCityDetail(city));
    bounds.push([city.latitude, city.longitude]);

    const li = document.createElement("li");
    li.textContent = city.name;
    li.dataset.cityId = city.id;
    li.addEventListener("click", () => {
      map.setView([city.latitude, city.longitude], 12);
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
    renderCities(cities);
  } catch (err) {
    setStatus(
      `Could not reach the API at ${API_BASE}. Is the backend running? (${err.message})`,
      true
    );
  }
}

loadCities();
