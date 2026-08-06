// Admin panel: create/edit/delete Regions and Cities against the API.
// Shares globals (API_BASE, escapeHtml, t, loadCities, ...) with app.js,
// which is loaded first on the page.

const ADMIN_API_KEY_STORAGE = "kba_admin_api_key";

// Keep in sync with CITY_CATEGORIES in api/v1/views/cities.py.
const CITY_CATEGORIES = [
  { value: "city", label: "City" },
  { value: "road", label: "Road" },
  { value: "cafe", label: "Cafe" },
  { value: "restaurant", label: "Restaurant" },
  { value: "hotel", label: "Hotel" },
  { value: "landmark", label: "Landmark" },
  { value: "museum", label: "Museum" },
  { value: "park", label: "Park" },
  { value: "university", label: "University" },
  { value: "school", label: "School" },
  { value: "hospital", label: "Hospital" },
  { value: "pharmacy", label: "Pharmacy" },
  { value: "bank", label: "Bank" },
  { value: "government", label: "Government office" },
  { value: "police", label: "Police" },
  { value: "fire_station", label: "Fire station" },
  { value: "mosque", label: "Mosque" },
  { value: "church", label: "Church" },
  { value: "fuel_station", label: "Fuel station" },
  { value: "parking", label: "Parking" },
  { value: "shop", label: "Shop" },
  { value: "other", label: "Other" },
];

// A searchable combobox for picking a category — plain <select> gets
// unwieldy once there are 20+ categories, so this filters as you type.
function buildCategoryPicker(selectedValue) {
  const initial =
    CITY_CATEGORIES.find((c) => c.value === selectedValue) ||
    CITY_CATEGORIES[0];

  const wrapper = document.createElement("div");
  wrapper.className = "category-picker";
  wrapper.dataset.value = initial.value;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "category-picker-input";
  input.autocomplete = "off";
  input.value = initial.label;

  const menu = document.createElement("div");
  menu.className = "category-picker-menu";
  menu.hidden = true;

  function selectedLabel() {
    const current = CITY_CATEGORIES.find((c) => c.value === wrapper.dataset.value);
    return current ? current.label : "";
  }

  function renderOptions(query) {
    menu.innerHTML = "";
    const q = query.trim().toLowerCase();
    const matches = CITY_CATEGORIES.filter((c) => c.label.toLowerCase().includes(q));
    if (matches.length === 0) {
      const empty = document.createElement("div");
      empty.className = "category-picker-empty";
      empty.textContent = "No matching category";
      menu.appendChild(empty);
      return;
    }
    matches.forEach((c) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "category-picker-option";
      if (c.value === wrapper.dataset.value) {
        option.classList.add("active");
      }
      option.textContent = c.label;
      option.addEventListener("mousedown", (event) => {
        // mousedown (not click) fires before the input's blur handler,
        // so the selection lands before blur snaps the text back.
        event.preventDefault();
        wrapper.dataset.value = c.value;
        input.value = c.label;
        menu.hidden = true;
      });
      menu.appendChild(option);
    });
  }

  const MENU_MAX_HEIGHT = 180;

  function positionMenu() {
    // The admin panel body scrolls internally and clips overflow, so a
    // menu that would open below the visible area needs to flip above
    // the input instead of getting cut off.
    const inputRect = input.getBoundingClientRect();
    const panelBody = document.querySelector(".admin-panel-body");
    const bodyRect = panelBody.getBoundingClientRect();
    const spaceBelow = bodyRect.bottom - inputRect.bottom;
    const spaceAbove = inputRect.top - bodyRect.top;
    menu.classList.toggle(
      "flip-up",
      spaceBelow < MENU_MAX_HEIGHT && spaceAbove > spaceBelow
    );
  }

  input.addEventListener("focus", () => {
    input.select();
    renderOptions("");
    positionMenu();
    menu.hidden = false;
  });
  input.addEventListener("input", () => renderOptions(input.value));
  input.addEventListener("blur", () => {
    menu.hidden = true;
    input.value = selectedLabel();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      menu.hidden = true;
      input.value = selectedLabel();
      input.blur();
    }
  });

  wrapper.appendChild(input);
  wrapper.appendChild(menu);
  return wrapper;
}

function categoryPickerValue(picker) {
  return picker.dataset.value;
}

const adminOverlayEl = document.getElementById("admin-overlay");
const adminToggleEl = document.getElementById("admin-toggle");
const adminCloseEl = document.getElementById("admin-close");
const adminMessageEl = document.getElementById("admin-message");
const adminApiKeyEl = document.getElementById("admin-api-key");
const regionFormEl = document.getElementById("region-form");
const regionNameInputEl = document.getElementById("region-name-input");
const regionDescriptionInputEl = document.getElementById("region-description-input");
const regionFormSubmitEl = document.getElementById("region-form-submit");
const adminRegionsListEl = document.getElementById("admin-regions-list");

adminApiKeyEl.value = localStorage.getItem(ADMIN_API_KEY_STORAGE) || "";
adminApiKeyEl.addEventListener("input", () => {
  localStorage.setItem(ADMIN_API_KEY_STORAGE, adminApiKeyEl.value);
});

function adminHeaders() {
  const headers = { "Content-Type": "application/json" };
  const key = adminApiKeyEl.value.trim();
  if (key) {
    headers["X-API-Key"] = key;
  }
  return headers;
}

function showAdminMessage(message, isError) {
  adminMessageEl.textContent = message;
  adminMessageEl.hidden = false;
  adminMessageEl.classList.toggle("error", Boolean(isError));
}

function clearAdminMessage() {
  adminMessageEl.hidden = true;
  adminMessageEl.textContent = "";
}

function openAdminPanel() {
  adminOverlayEl.hidden = false;
  clearAdminMessage();
  refreshAdminData();
}

function closeAdminPanel() {
  adminOverlayEl.hidden = true;
}

adminToggleEl.addEventListener("click", openAdminPanel);
adminCloseEl.addEventListener("click", closeAdminPanel);
adminOverlayEl.addEventListener("click", (event) => {
  if (event.target === adminOverlayEl) {
    closeAdminPanel();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !adminOverlayEl.hidden) {
    closeAdminPanel();
  }
});

const mapPickBannerEl = document.getElementById("map-pick-banner");
const mapPickCancelEl = document.getElementById("map-pick-cancel");
let activePick = null;

function stopPickingLocation() {
  if (!activePick) {
    return;
  }
  map.off("click", activePick.onMapClick);
  document.removeEventListener("keydown", activePick.onKeydown);
  mapPickBannerEl.hidden = true;
  adminOverlayEl.hidden = false;
  activePick = null;
}

// Temporarily hides the admin panel so the underlying Leaflet map is
// clickable, and fills `latInput`/`lngInput` with the clicked location.
function startPickingLocation(latInput, lngInput) {
  stopPickingLocation();
  adminOverlayEl.hidden = true;
  mapPickBannerEl.hidden = false;

  const onMapClick = (event) => {
    latInput.value = event.latlng.lat.toFixed(6);
    lngInput.value = event.latlng.lng.toFixed(6);
    stopPickingLocation();
  };
  const onKeydown = (event) => {
    if (event.key === "Escape") {
      stopPickingLocation();
    }
  };

  activePick = { onMapClick, onKeydown };
  map.on("click", onMapClick);
  document.addEventListener("keydown", onKeydown);
}

mapPickCancelEl.addEventListener("click", stopPickingLocation);

async function apiRequest(method, path, body) {
  const options = { method, headers: adminHeaders() };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${path}`, options);
  let data = null;
  try {
    data = await res.json();
  } catch (err) {
    data = null;
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

regionFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = regionNameInputEl.value.trim();
  if (!name) {
    showAdminMessage("Region name can't be empty.", true);
    return;
  }
  regionFormSubmitEl.disabled = true;
  try {
    await apiRequest("POST", "/regions", {
      name,
      description: regionDescriptionInputEl.value.trim() || null,
    });
    showAdminMessage(`Region "${name}" created.`, false);
    regionFormEl.reset();
    await refreshAdminData();
  } catch (err) {
    showAdminMessage(err.message, true);
  } finally {
    regionFormSubmitEl.disabled = false;
  }
});

async function refreshAdminData() {
  adminRegionsListEl.textContent = "Loading…";
  try {
    const [regions, cities] = await Promise.all([
      apiRequest("GET", "/regions"),
      apiRequest("GET", "/cities"),
    ]);
    renderAdminRegions(regions, cities);
  } catch (err) {
    adminRegionsListEl.textContent = "";
    showAdminMessage(err.message, true);
  }
}

function renderAdminRegions(regions, cities) {
  adminRegionsListEl.innerHTML = "";
  if (regions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = "No regions yet — add one above.";
    adminRegionsListEl.appendChild(empty);
    return;
  }
  regions.forEach((region) => {
    const regionCities = cities.filter((c) => c.region_id === region.id);
    adminRegionsListEl.appendChild(buildAdminRegionCard(region, regionCities));
  });
}

function buildAdminRegionCard(region, regionCities) {
  const card = document.createElement("div");
  card.className = "admin-region";
  card.dataset.regionId = region.id;

  const headerRow = document.createElement("div");
  headerRow.className = "admin-region-header";

  const title = document.createElement("strong");
  title.textContent = region.name;
  headerRow.appendChild(title);

  const actions = document.createElement("div");
  actions.className = "admin-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => startEditRegion(region));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "danger";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", () => deleteRegion(region));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  headerRow.appendChild(actions);
  card.appendChild(headerRow);

  if (region.description) {
    const desc = document.createElement("p");
    desc.className = "admin-region-description";
    desc.textContent = region.description;
    card.appendChild(desc);
  }

  const cityList = document.createElement("ul");
  cityList.className = "admin-city-list";
  if (regionCities.length === 0) {
    const li = document.createElement("li");
    li.className = "admin-empty";
    li.textContent = "No cities in this region yet.";
    cityList.appendChild(li);
  } else {
    regionCities.forEach((city) => cityList.appendChild(buildAdminCityRow(city)));
  }
  card.appendChild(cityList);
  card.appendChild(buildAddCityForm(region));

  return card;
}

function buildAdminCityRow(city) {
  const li = document.createElement("li");
  li.className = "admin-city";
  li.dataset.cityId = city.id;

  const label = document.createElement("span");
  const categoryTag = city.category && city.category !== "city" ? ` [${city.category}]` : "";
  label.textContent = `${city.name}${categoryTag} (${city.latitude}, ${city.longitude})`;
  li.appendChild(label);

  const actions = document.createElement("div");
  actions.className = "admin-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => startEditCity(city));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "danger";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", () => deleteCity(city));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  li.appendChild(actions);

  return li;
}

function buildAddCityForm(region) {
  const form = document.createElement("form");
  form.className = "admin-form admin-add-city-form";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.placeholder = "City name";
  nameInput.required = true;
  nameInput.maxLength = 128;

  const latInput = document.createElement("input");
  latInput.type = "number";
  latInput.step = "any";
  latInput.placeholder = "Latitude";
  latInput.required = true;

  const lngInput = document.createElement("input");
  lngInput.type = "number";
  lngInput.step = "any";
  lngInput.placeholder = "Longitude";
  lngInput.required = true;

  const categoryPicker = buildCategoryPicker("city");

  const pickOnMapBtn = document.createElement("button");
  pickOnMapBtn.type = "button";
  pickOnMapBtn.className = "pick-on-map";
  pickOnMapBtn.textContent = "Pick on map";
  pickOnMapBtn.addEventListener("click", () => startPickingLocation(latInput, lngInput));

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Add city";

  form.appendChild(nameInput);
  form.appendChild(latInput);
  form.appendChild(lngInput);
  form.appendChild(pickOnMapBtn);
  form.appendChild(categoryPicker);
  form.appendChild(submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = nameInput.value.trim();
    const latitude = parseFloat(latInput.value);
    const longitude = parseFloat(lngInput.value);
    if (!name || Number.isNaN(latitude) || Number.isNaN(longitude)) {
      showAdminMessage(
        "Please fill in a valid name, latitude, and longitude.", true);
      return;
    }
    submit.disabled = true;
    try {
      await apiRequest(
        "POST", `/regions/${region.id}/cities`,
        { name, latitude, longitude, category: categoryPickerValue(categoryPicker) });
      showAdminMessage(`City "${name}" added.`, false);
      await refreshAdminData();
      await loadCities();
    } catch (err) {
      showAdminMessage(err.message, true);
    } finally {
      submit.disabled = false;
    }
  });

  return form;
}

function startEditRegion(region) {
  const card = adminRegionsListEl.querySelector(
    `.admin-region[data-region-id="${region.id}"]`);
  if (!card) {
    return;
  }

  const form = document.createElement("form");
  form.className = "admin-form admin-edit-form";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = region.name;
  nameInput.required = true;
  nameInput.maxLength = 128;

  const descInput = document.createElement("textarea");
  descInput.rows = 2;
  descInput.value = region.description || "";

  const actions = document.createElement("div");
  actions.className = "admin-form-actions";

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.textContent = "Save";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", refreshAdminData);

  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(nameInput);
  form.appendChild(descInput);
  form.appendChild(actions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = nameInput.value.trim();
    if (!name) {
      showAdminMessage("Region name can't be empty.", true);
      return;
    }
    saveBtn.disabled = true;
    try {
      await apiRequest("PUT", `/regions/${region.id}`, {
        name, description: descInput.value.trim() || null,
      });
      showAdminMessage(`Region "${name}" updated.`, false);
      await refreshAdminData();
      await loadCities();
    } catch (err) {
      showAdminMessage(err.message, true);
      saveBtn.disabled = false;
    }
  });

  card.replaceWith(form);
}

function startEditCity(city) {
  const li = adminRegionsListEl.querySelector(
    `.admin-city[data-city-id="${city.id}"]`);
  if (!li) {
    return;
  }

  const form = document.createElement("form");
  form.className = "admin-form admin-edit-form admin-edit-city-form";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = city.name;
  nameInput.required = true;
  nameInput.maxLength = 128;

  const latInput = document.createElement("input");
  latInput.type = "number";
  latInput.step = "any";
  latInput.value = city.latitude;
  latInput.required = true;

  const lngInput = document.createElement("input");
  lngInput.type = "number";
  lngInput.step = "any";
  lngInput.value = city.longitude;
  lngInput.required = true;

  const descInput = document.createElement("textarea");
  descInput.rows = 2;
  descInput.placeholder = "Description";
  descInput.value = city.description || "";

  const categoryPicker = buildCategoryPicker(city.category);

  const pickOnMapBtn = document.createElement("button");
  pickOnMapBtn.type = "button";
  pickOnMapBtn.className = "pick-on-map";
  pickOnMapBtn.textContent = "Pick on map";
  pickOnMapBtn.addEventListener("click", () => startPickingLocation(latInput, lngInput));

  const actions = document.createElement("div");
  actions.className = "admin-form-actions";

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.textContent = "Save";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = "Cancel";
  cancelBtn.addEventListener("click", refreshAdminData);

  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(nameInput);
  form.appendChild(latInput);
  form.appendChild(lngInput);
  form.appendChild(pickOnMapBtn);
  form.appendChild(categoryPicker);
  form.appendChild(descInput);
  form.appendChild(actions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = nameInput.value.trim();
    const latitude = parseFloat(latInput.value);
    const longitude = parseFloat(lngInput.value);
    if (!name || Number.isNaN(latitude) || Number.isNaN(longitude)) {
      showAdminMessage(
        "Please fill in a valid name, latitude, and longitude.", true);
      return;
    }
    saveBtn.disabled = true;
    try {
      await apiRequest("PUT", `/cities/${city.id}`, {
        name, latitude, longitude,
        category: categoryPickerValue(categoryPicker),
        description: descInput.value.trim() || null,
      });
      showAdminMessage(`City "${name}" updated.`, false);
      await refreshAdminData();
      await loadCities();
    } catch (err) {
      showAdminMessage(err.message, true);
      saveBtn.disabled = false;
    }
  });

  li.replaceWith(form);
}

async function deleteRegion(region) {
  const ok = window.confirm(
    `Delete region "${region.name}" and all its cities? This can't be undone.`);
  if (!ok) {
    return;
  }
  try {
    await apiRequest("DELETE", `/regions/${region.id}`);
    showAdminMessage(`Region "${region.name}" deleted.`, false);
    await refreshAdminData();
    await loadCities();
  } catch (err) {
    showAdminMessage(err.message, true);
  }
}

async function deleteCity(city) {
  const ok = window.confirm(`Delete city "${city.name}"? This can't be undone.`);
  if (!ok) {
    return;
  }
  try {
    await apiRequest("DELETE", `/cities/${city.id}`);
    showAdminMessage(`City "${city.name}" deleted.`, false);
    await refreshAdminData();
    await loadCities();
  } catch (err) {
    showAdminMessage(err.message, true);
  }
}
