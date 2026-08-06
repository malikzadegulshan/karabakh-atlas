// Admin panel: create/edit/delete Regions and Cities against the API.
// Shares globals (API_BASE, escapeHtml, t, loadCities, ...) with app.js,
// which is loaded first on the page.

const ADMIN_API_KEY_STORAGE = "kba_admin_api_key";

// Keep in sync with CITY_CATEGORIES in api/v1/views/cities.py.
const CITY_CATEGORIES = [
  { value: "city", label: "City" },
  { value: "cafe", label: "Cafe" },
  { value: "restaurant", label: "Restaurant" },
  { value: "hotel", label: "Hotel" },
  { value: "landmark", label: "Landmark" },
  { value: "museum", label: "Museum" },
  { value: "shop", label: "Shop" },
  { value: "other", label: "Other" },
];

function buildCategorySelect(selectedValue) {
  const select = document.createElement("select");
  CITY_CATEGORIES.forEach(({ value, label }) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (value === (selectedValue || "city")) {
      option.selected = true;
    }
    select.appendChild(option);
  });
  return select;
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

  const categorySelect = buildCategorySelect("city");

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Add city";

  form.appendChild(nameInput);
  form.appendChild(latInput);
  form.appendChild(lngInput);
  form.appendChild(categorySelect);
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
        { name, latitude, longitude, category: categorySelect.value });
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

  const categorySelect = buildCategorySelect(city.category);

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
  form.appendChild(categorySelect);
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
        category: categorySelect.value,
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
