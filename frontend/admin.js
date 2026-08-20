// Admin panel: create/edit/delete Regions and Cities against the API.
// Shares globals (API_BASE, escapeHtml, t, loadCities, ...) with app.js,
// and (currentUser, adminToggleEl, ...) with auth.js, both loaded
// earlier on the page. Write requests ride on the session cookie set by
// auth.js's login — the server is the real enforcement point; the
// admin-toggle button is just hidden client-side for non-admins as UX.

// Keep in sync with CITY_CATEGORIES in api/v1/views/cities.py. Display
// labels come from TRANSLATIONS[currentLang].categories so they follow
// the language switcher; only the values are shared with the backend.
const CITY_CATEGORY_VALUES = [
  "city", "road", "cafe", "restaurant", "hotel", "landmark", "museum",
  "park", "university", "school", "hospital", "pharmacy", "bank",
  "government", "police", "fire_station", "mosque", "church",
  "fuel_station", "parking", "shop", "other",
];

function categoryLabel(value) {
  return (t("categories") && t("categories")[value]) || value;
}

// A searchable combobox for picking a category — plain <select> gets
// unwieldy once there are 20+ categories, so this filters as you type.
// `onChange`, if given, fires with the new value whenever a selection is
// made (not on every keystroke) — used to show/hide the phone/website
// fields, which only apply to points of interest, not plain cities.
function buildCategoryPicker(selectedValue, onChange) {
  const initialValue = CITY_CATEGORY_VALUES.includes(selectedValue)
    ? selectedValue
    : CITY_CATEGORY_VALUES[0];

  const wrapper = document.createElement("div");
  wrapper.className = "category-picker";
  wrapper.dataset.value = initialValue;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "category-picker-input";
  input.autocomplete = "off";
  input.value = categoryLabel(initialValue);

  const menu = document.createElement("div");
  menu.className = "category-picker-menu";
  menu.hidden = true;

  function selectedLabel() {
    return categoryLabel(wrapper.dataset.value);
  }

  function renderOptions(query) {
    menu.innerHTML = "";
    const q = query.trim().toLowerCase();
    const matches = CITY_CATEGORY_VALUES.filter((value) =>
      categoryLabel(value).toLowerCase().includes(q));
    if (matches.length === 0) {
      const empty = document.createElement("div");
      empty.className = "category-picker-empty";
      empty.textContent = t("categoryNoMatch");
      menu.appendChild(empty);
      return;
    }
    matches.forEach((value) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "category-picker-option";
      if (value === wrapper.dataset.value) {
        option.classList.add("active");
      }
      option.textContent = categoryLabel(value);
      option.addEventListener("mousedown", (event) => {
        // mousedown (not click) fires before the input's blur handler,
        // so the selection lands before blur snaps the text back.
        event.preventDefault();
        wrapper.dataset.value = value;
        input.value = categoryLabel(value);
        menu.hidden = true;
        if (onChange) {
          onChange(value);
        }
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
const adminPanelEl = document.getElementById("admin-panel");
const adminTitleEl = document.getElementById("admin-title");
const adminCloseEl = document.getElementById("admin-close");
const adminMessageEl = document.getElementById("admin-message");
const adminAddRegionTitleEl = document.getElementById("admin-add-region-title");
const adminRegionsTitleEl = document.getElementById("admin-regions-title");
const regionFormEl = document.getElementById("region-form");
const regionNameInputEl = document.getElementById("region-name-input");
const regionDescriptionInputEl = document.getElementById("region-description-input");
const regionFormSubmitEl = document.getElementById("region-form-submit");
const adminRegionsListEl = document.getElementById("admin-regions-list");
const adminForumTitleEl = document.getElementById("admin-forum-title");
const adminForumListEl = document.getElementById("admin-forum-list");
const adminTabDataEl = document.getElementById("admin-tab-data");
const adminTabEventsEl = document.getElementById("admin-tab-events");
const adminTabForumEl = document.getElementById("admin-tab-forum");
const adminViewDataEl = document.getElementById("admin-view-data");
const adminViewEventsEl = document.getElementById("admin-view-events");
const adminViewForumEl = document.getElementById("admin-view-forum");
const adminAddEventTitleEl = document.getElementById("admin-add-event-title");
const adminEventsTitleEl = document.getElementById("admin-events-title");
const eventFormEl = document.getElementById("event-form");
const eventTitleInputEl = document.getElementById("event-title-input");
const eventYearInputEl = document.getElementById("event-year-input");
const eventLatInputEl = document.getElementById("event-lat-input");
const eventLngInputEl = document.getElementById("event-lng-input");
const eventPickOnMapEl = document.getElementById("event-pick-on-map");
const eventDescriptionInputEl = document.getElementById("event-description-input");
const eventSourceInputEl = document.getElementById("event-source-input");
const eventFormSubmitEl = document.getElementById("event-form-submit");
const adminEventsListEl = document.getElementById("admin-events-list");

// The historical-imagery timeline only reaches back to ~2014 (see
// WAYBACK_FALLBACK_MIN_YEAR in app.js) — kept in sync with
// EVENT_YEAR_MIN in api/v1/views/historical_events.py, which is the
// real enforcement point; this just gives the form's number input
// sensible min/max instead of letting someone submit an out-of-range
// year only to have the server reject it.
const EVENT_YEAR_MIN = 2014;
const eventYearMax = new Date().getFullYear();
eventYearInputEl.min = EVENT_YEAR_MIN;
eventYearInputEl.max = eventYearMax;

function applyAdminStaticTranslations() {
  adminToggleEl.setAttribute("aria-label", t("adminToggle"));
  adminToggleEl.title = t("adminToggle");
  adminTitleEl.textContent = t("adminTitle");
  adminCloseEl.setAttribute("aria-label", t("adminClose"));
  adminAddRegionTitleEl.textContent = t("adminAddRegionTitle");
  regionFormSubmitEl.textContent = t("adminAddRegionSubmit");
  adminRegionsTitleEl.textContent = t("adminRegionsTitle");
  mapPickInstructionEl.textContent = t("mapPickInstruction");
  mapPickCancelEl.textContent = t("mapPickCancel");
  adminForumTitleEl.textContent = t("adminForumTitle");
  adminTabDataEl.textContent = t("adminRegionsTitle");
  adminTabEventsEl.textContent = t("adminEventsTitle");
  adminTabForumEl.textContent = t("adminForumTitle");
  adminAddEventTitleEl.textContent = t("adminAddEventTitle");
  adminEventsTitleEl.textContent = t("adminEventsTitle");
  setPlaceholderLabel(eventTitleInputEl, t("fieldTitle"));
  setPlaceholderLabel(eventYearInputEl, t("fieldYear"));
  setPlaceholderLabel(eventLatInputEl, t("fieldLatitude"));
  setPlaceholderLabel(eventLngInputEl, t("fieldLongitude"));
  eventPickOnMapEl.textContent = t("adminPickOnMap");
  setPlaceholderLabel(eventDescriptionInputEl, t("fieldDescription"));
  setPlaceholderLabel(eventSourceInputEl, t("fieldSourceUrl"));
  eventFormSubmitEl.textContent = t("adminAddEventSubmit");
}

// Three tabs sharing the same modal, same pattern as the sign-in/register
// tabs in auth.js (.active class + hidden toggling).
function selectAdminTab(tab) {
  adminTabDataEl.classList.toggle("active", tab === "data");
  adminTabEventsEl.classList.toggle("active", tab === "events");
  adminTabForumEl.classList.toggle("active", tab === "forum");
  adminViewDataEl.hidden = tab !== "data";
  adminViewEventsEl.hidden = tab !== "events";
  adminViewForumEl.hidden = tab !== "forum";
}

adminTabDataEl.addEventListener("click", () => selectAdminTab("data"));
adminTabEventsEl.addEventListener("click", () => selectAdminTab("events"));
adminTabForumEl.addEventListener("click", () => selectAdminTab("forum"));

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
  applyAdminStaticTranslations();
  selectAdminTab("data");
  refreshAdminData();
  openModalFocus(adminPanelEl);
}

function closeAdminPanel() {
  adminOverlayEl.hidden = true;
  closeModalFocus();
}

adminToggleEl.addEventListener("click", openAdminPanel);
adminCloseEl.addEventListener("click", closeAdminPanel);
adminOverlayEl.addEventListener("click", (event) => {
  if (event.target === adminOverlayEl) {
    closeAdminPanel();
  }
});
document.addEventListener("keydown", (event) => {
  if (adminOverlayEl.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closeAdminPanel();
  } else {
    trapTabKey(event, adminPanelEl);
  }
});

const mapPickBannerEl = document.getElementById("map-pick-banner");
const mapPickInstructionEl = mapPickBannerEl.querySelector("span");
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
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  };
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
    showAdminMessage(t("regionNameEmpty"), true);
    return;
  }
  regionFormSubmitEl.disabled = true;
  try {
    await apiRequest("POST", "/regions", {
      name,
      description: regionDescriptionInputEl.value.trim() || null,
    });
    showAdminMessage(t("regionCreated")(name), false);
    regionFormEl.reset();
    await refreshAdminData();
  } catch (err) {
    showAdminMessage(err.message, true);
  } finally {
    regionFormSubmitEl.disabled = false;
  }
});

async function refreshAdminData() {
  adminRegionsListEl.textContent = t("adminLoading");
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
  await refreshAdminEvents();
  await refreshAdminForumQueue();
}

async function refreshAdminEvents() {
  adminEventsListEl.textContent = t("adminLoading");
  try {
    const events = await apiRequest("GET", "/historical-events");
    renderAdminEvents(events);
  } catch (err) {
    adminEventsListEl.textContent = "";
    showAdminMessage(err.message, true);
  }
}

function renderAdminEvents(events) {
  adminEventsListEl.innerHTML = "";
  if (events.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = t("adminNoEvents");
    adminEventsListEl.appendChild(empty);
    return;
  }
  events.forEach((event) => adminEventsListEl.appendChild(buildAdminEventRow(event)));
}

function buildAdminEventRow(event) {
  const li = document.createElement("div");
  li.className = "admin-region admin-event-row";
  li.dataset.eventId = event.id;

  const headerRow = document.createElement("div");
  headerRow.className = "admin-region-header";

  const label = document.createElement("strong");
  label.textContent = `${event.title} (${event.year})`;
  headerRow.appendChild(label);

  const actions = document.createElement("div");
  actions.className = "admin-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.textContent = t("adminEdit");
  editBtn.addEventListener("click", () => startEditEvent(event));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "danger";
  deleteBtn.textContent = t("adminDelete");
  deleteBtn.addEventListener("click", () => deleteEvent(event));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  headerRow.appendChild(actions);
  li.appendChild(headerRow);

  if (event.description) {
    const desc = document.createElement("p");
    desc.className = "admin-region-description";
    desc.textContent = event.description;
    li.appendChild(desc);
  }

  return li;
}

function startEditEvent(event) {
  const row = adminEventsListEl.querySelector(
    `.admin-event-row[data-event-id="${event.id}"]`);
  if (!row) {
    return;
  }

  const form = document.createElement("form");
  form.className = "admin-form admin-edit-form";

  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleInput.value = event.title;
  titleInput.required = true;
  titleInput.maxLength = 200;

  const yearInput = document.createElement("input");
  yearInput.type = "number";
  yearInput.step = "1";
  yearInput.min = EVENT_YEAR_MIN;
  yearInput.max = eventYearMax;
  yearInput.value = event.year;
  yearInput.required = true;

  const latInput = document.createElement("input");
  latInput.type = "number";
  latInput.step = "any";
  latInput.value = event.latitude;
  latInput.required = true;

  const lngInput = document.createElement("input");
  lngInput.type = "number";
  lngInput.step = "any";
  lngInput.value = event.longitude;
  lngInput.required = true;

  const pickOnMapBtn = document.createElement("button");
  pickOnMapBtn.type = "button";
  pickOnMapBtn.className = "pick-on-map";
  pickOnMapBtn.textContent = t("adminPickOnMap");
  pickOnMapBtn.addEventListener("click", () => startPickingLocation(latInput, lngInput));

  const descInput = document.createElement("textarea");
  descInput.rows = 2;
  setPlaceholderLabel(descInput, t("fieldDescription"));
  descInput.value = event.description || "";

  const sourceInput = document.createElement("input");
  sourceInput.type = "url";
  setPlaceholderLabel(sourceInput, t("fieldSourceUrl"));
  sourceInput.maxLength = 500;
  sourceInput.value = event.source_url || "";

  const actions = document.createElement("div");
  actions.className = "admin-form-actions";

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.textContent = t("adminSave");

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = t("adminCancel");
  cancelBtn.addEventListener("click", refreshAdminEvents);

  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(titleInput);
  form.appendChild(yearInput);
  form.appendChild(latInput);
  form.appendChild(lngInput);
  form.appendChild(pickOnMapBtn);
  form.appendChild(descInput);
  form.appendChild(sourceInput);
  form.appendChild(actions);

  form.addEventListener("submit", async (submitEvent) => {
    submitEvent.preventDefault();
    const title = titleInput.value.trim();
    const year = parseInt(yearInput.value, 10);
    const latitude = parseFloat(latInput.value);
    const longitude = parseFloat(lngInput.value);
    if (!title || Number.isNaN(year) || Number.isNaN(latitude) ||
        Number.isNaN(longitude)) {
      showAdminMessage(t("invalidEventFields"), true);
      return;
    }
    saveBtn.disabled = true;
    try {
      await apiRequest("PUT", `/historical-events/${event.id}`, {
        title, year, latitude, longitude,
        description: descInput.value.trim() || null,
        source_url: sourceInput.value.trim() || null,
      });
      showAdminMessage(t("eventUpdated")(title), false);
      await refreshAdminEvents();
      await loadHistoricalEvents();
    } catch (err) {
      showAdminMessage(err.message, true);
      saveBtn.disabled = false;
    }
  });

  row.replaceWith(form);
}

async function deleteEvent(event) {
  const ok = window.confirm(t("confirmDeleteEvent")(event.title));
  if (!ok) {
    return;
  }
  try {
    await apiRequest("DELETE", `/historical-events/${event.id}`);
    showAdminMessage(t("eventDeleted")(event.title), false);
    await refreshAdminEvents();
    await loadHistoricalEvents();
  } catch (err) {
    showAdminMessage(err.message, true);
  }
}

eventPickOnMapEl.addEventListener("click", () =>
  startPickingLocation(eventLatInputEl, eventLngInputEl));

eventFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = eventTitleInputEl.value.trim();
  const year = parseInt(eventYearInputEl.value, 10);
  const latitude = parseFloat(eventLatInputEl.value);
  const longitude = parseFloat(eventLngInputEl.value);
  if (!title || Number.isNaN(year) || Number.isNaN(latitude) ||
      Number.isNaN(longitude)) {
    showAdminMessage(t("invalidEventFields"), true);
    return;
  }
  eventFormSubmitEl.disabled = true;
  try {
    await apiRequest("POST", "/historical-events", {
      title, year, latitude, longitude,
      description: eventDescriptionInputEl.value.trim() || null,
      source_url: eventSourceInputEl.value.trim() || null,
    });
    showAdminMessage(t("eventAdded")(title), false);
    eventFormEl.reset();
    await refreshAdminEvents();
    await loadHistoricalEvents();
  } catch (err) {
    showAdminMessage(err.message, true);
  } finally {
    eventFormSubmitEl.disabled = false;
  }
});

async function refreshAdminForumQueue() {
  adminForumListEl.textContent = t("adminLoading");
  try {
    const posts = await apiRequest("GET", "/forum/posts?status=pending");
    renderAdminForumQueue(posts);
  } catch (err) {
    adminForumListEl.textContent = "";
    showAdminMessage(err.message, true);
  }
}

function renderAdminForumQueue(posts) {
  adminForumListEl.innerHTML = "";
  if (posts.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = t("adminForumEmpty");
    adminForumListEl.appendChild(empty);
    return;
  }
  posts.forEach((post) => adminForumListEl.appendChild(buildAdminForumCard(post)));
}

function buildAdminForumCard(post) {
  const card = document.createElement("div");
  card.className = "admin-region admin-forum-card";

  const headerRow = document.createElement("div");
  headerRow.className = "admin-region-header";

  const meta = document.createElement("strong");
  const about = post.target_city_name || t("forumGeneralLabel");
  meta.textContent = `${post.author_name || "?"} — ${t("forumAbout")(about)}`;
  headerRow.appendChild(meta);

  const actions = document.createElement("div");
  actions.className = "admin-actions";

  const approveBtn = document.createElement("button");
  approveBtn.type = "button";
  approveBtn.textContent = t("adminApprove");
  approveBtn.addEventListener("click", () => moderateForumPost(post, "approved"));

  const rejectBtn = document.createElement("button");
  rejectBtn.type = "button";
  rejectBtn.className = "danger";
  rejectBtn.textContent = t("adminReject");
  rejectBtn.addEventListener("click", () => moderateForumPost(post, "rejected"));

  actions.appendChild(approveBtn);
  actions.appendChild(rejectBtn);
  headerRow.appendChild(actions);
  card.appendChild(headerRow);

  // textContent, not innerHTML — this is unmoderated user-submitted.
  // text, rendered here in the admin's own browser before it's ever
  // approved, so it must never be interpreted as HTML.
  const body = document.createElement("p");
  body.className = "admin-region-description";
  body.textContent = post.body;
  card.appendChild(body);

  return card;
}

async function moderateForumPost(post, status) {
  try {
    await apiRequest("PUT", `/forum/posts/${post.id}/status`, { status });
    await refreshAdminForumQueue();
  } catch (err) {
    showAdminMessage(err.message, true);
  }
}

function renderAdminRegions(regions, cities) {
  adminRegionsListEl.innerHTML = "";
  if (regions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = t("adminNoRegions");
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
  editBtn.textContent = t("adminEdit");
  editBtn.addEventListener("click", () => startEditRegion(region));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "danger";
  deleteBtn.textContent = t("adminDelete");
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
    li.textContent = t("adminNoCities");
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
  const categoryTag = city.category && city.category !== "city"
    ? ` [${categoryLabel(city.category)}]`
    : "";
  label.textContent = `${city.name}${categoryTag} (${city.latitude}, ${city.longitude})`;
  li.appendChild(label);

  const actions = document.createElement("div");
  actions.className = "admin-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.textContent = t("adminEdit");
  editBtn.addEventListener("click", () => startEditCity(city));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "danger";
  deleteBtn.textContent = t("adminDelete");
  deleteBtn.addEventListener("click", () => deleteCity(city));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  li.appendChild(actions);

  return li;
}

// Per-language name overrides — same name_i18n field the seeded cities
// (Khankendi/Shusha) already use, just now editable from the admin
// panel for any city or point of interest. English uses the main Name
// field as its fallback, so there's no separate "EN" input here.
const NAME_I18N_LANGS = ["az", "tr", "ru"];

function buildNameI18nInputs(existingNameI18n) {
  const inputs = {};
  const elements = NAME_I18N_LANGS.map((lang) => {
    const input = document.createElement("input");
    input.type = "text";
    setPlaceholderLabel(input, `${t("fieldName")} (${lang.toUpperCase()})`);
    input.maxLength = 128;
    input.value = (existingNameI18n && existingNameI18n[lang]) || "";
    inputs[lang] = input;
    return input;
  });

  function collect() {
    const result = {};
    NAME_I18N_LANGS.forEach((lang) => {
      const value = inputs[lang].value.trim();
      if (value) {
        result[lang] = value;
      }
    });
    return Object.keys(result).length > 0 ? result : null;
  }

  return { elements, collect };
}

// Same idea as buildNameI18nInputs, but for the longer description text
// — textareas instead of single-line inputs. English still uses the
// main Description field as its fallback (see localizedDescription()
// in app.js), so there's no separate "EN" textarea here either.
function buildDescriptionI18nInputs(existingDescriptionI18n) {
  const inputs = {};
  const elements = NAME_I18N_LANGS.map((lang) => {
    const textarea = document.createElement("textarea");
    textarea.rows = 2;
    setPlaceholderLabel(textarea, `${t("fieldDescription")} (${lang.toUpperCase()})`);
    textarea.value = (existingDescriptionI18n && existingDescriptionI18n[lang]) || "";
    inputs[lang] = textarea;
    return textarea;
  });

  function collect() {
    const result = {};
    NAME_I18N_LANGS.forEach((lang) => {
      const value = inputs[lang].value.trim();
      if (value) {
        result[lang] = value;
      }
    });
    return Object.keys(result).length > 0 ? result : null;
  }

  return { elements, collect };
}

function buildAddCityForm(region) {
  const form = document.createElement("form");
  form.className = "admin-form admin-add-city-form";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  setPlaceholderLabel(nameInput, t("fieldName"));
  nameInput.required = true;
  nameInput.maxLength = 128;

  const latInput = document.createElement("input");
  latInput.type = "number";
  latInput.step = "any";
  setPlaceholderLabel(latInput, t("fieldLatitude"));
  latInput.required = true;

  const lngInput = document.createElement("input");
  lngInput.type = "number";
  lngInput.step = "any";
  setPlaceholderLabel(lngInput, t("fieldLongitude"));
  lngInput.required = true;

  const nameI18n = buildNameI18nInputs(null);

  const descInput = document.createElement("textarea");
  descInput.rows = 2;
  setPlaceholderLabel(descInput, t("fieldDescription"));

  const descriptionI18n = buildDescriptionI18nInputs(null);

  const imageUrlInput = document.createElement("input");
  imageUrlInput.type = "url";
  setPlaceholderLabel(imageUrlInput, t("fieldImageUrl"));
  imageUrlInput.maxLength = 500;

  const imageCreditInput = document.createElement("input");
  imageCreditInput.type = "text";
  setPlaceholderLabel(imageCreditInput, t("fieldImageCredit"));
  imageCreditInput.maxLength = 255;

  // Phone/website only apply to points of interest, not plain cities —
  // hidden whenever the category picker is on "city", starting here
  // since that's this form's default category.
  const phoneInput = document.createElement("input");
  phoneInput.type = "tel";
  setPlaceholderLabel(phoneInput, t("fieldPhone"));
  phoneInput.maxLength = 30;
  phoneInput.hidden = true;

  const websiteInput = document.createElement("input");
  websiteInput.type = "url";
  setPlaceholderLabel(websiteInput, t("fieldWebsite"));
  websiteInput.maxLength = 500;
  websiteInput.hidden = true;

  const categoryPicker = buildCategoryPicker("city", (value) => {
    const isCity = value === "city";
    phoneInput.hidden = isCity;
    websiteInput.hidden = isCity;
  });

  const pickOnMapBtn = document.createElement("button");
  pickOnMapBtn.type = "button";
  pickOnMapBtn.className = "pick-on-map";
  pickOnMapBtn.textContent = t("adminPickOnMap");
  pickOnMapBtn.addEventListener("click", () => startPickingLocation(latInput, lngInput));

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = t("adminAddCity");

  form.appendChild(nameInput);
  nameI18n.elements.forEach((el) => form.appendChild(el));
  form.appendChild(latInput);
  form.appendChild(lngInput);
  form.appendChild(pickOnMapBtn);
  form.appendChild(categoryPicker);
  form.appendChild(imageUrlInput);
  form.appendChild(imageCreditInput);
  form.appendChild(phoneInput);
  form.appendChild(websiteInput);
  form.appendChild(descInput);
  descriptionI18n.elements.forEach((el) => form.appendChild(el));
  form.appendChild(submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = nameInput.value.trim();
    const latitude = parseFloat(latInput.value);
    const longitude = parseFloat(lngInput.value);
    if (!name || Number.isNaN(latitude) || Number.isNaN(longitude)) {
      showAdminMessage(t("invalidCityFields"), true);
      return;
    }
    submit.disabled = true;
    const category = categoryPickerValue(categoryPicker);
    const payload = {
      name, latitude, longitude, category,
      description: descInput.value.trim() || null,
      image_url: imageUrlInput.value.trim() || null,
      image_credit: imageCreditInput.value.trim() || null,
      // Cities don't get a contact section in the detail view, so don't
      // save contact info for them either — even if the fields still
      // hold text from before the category was switched to "city".
      phone: category === "city" ? null : (phoneInput.value.trim() || null),
      website: category === "city" ? null : (websiteInput.value.trim() || null),
    };
    const nameI18nValue = nameI18n.collect();
    if (nameI18nValue) {
      payload.name_i18n = nameI18nValue;
    }
    const descriptionI18nValue = descriptionI18n.collect();
    if (descriptionI18nValue) {
      payload.description_i18n = descriptionI18nValue;
    }
    try {
      await apiRequest("POST", `/regions/${region.id}/cities`, payload);
      showAdminMessage(t("cityAdded")(name), false);
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
  saveBtn.textContent = t("adminSave");

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = t("adminCancel");
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
      showAdminMessage(t("regionNameEmpty"), true);
      return;
    }
    saveBtn.disabled = true;
    try {
      await apiRequest("PUT", `/regions/${region.id}`, {
        name, description: descInput.value.trim() || null,
      });
      showAdminMessage(t("regionUpdated")(name), false);
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
  setPlaceholderLabel(descInput, t("fieldDescription"));
  descInput.value = city.description || "";

  const nameI18n = buildNameI18nInputs(city.name_i18n);
  const descriptionI18n = buildDescriptionI18nInputs(city.description_i18n);

  const imageUrlInput = document.createElement("input");
  imageUrlInput.type = "url";
  setPlaceholderLabel(imageUrlInput, t("fieldImageUrl"));
  imageUrlInput.maxLength = 500;
  imageUrlInput.value = city.image_url || "";

  const imageCreditInput = document.createElement("input");
  imageCreditInput.type = "text";
  setPlaceholderLabel(imageCreditInput, t("fieldImageCredit"));
  imageCreditInput.maxLength = 255;
  imageCreditInput.value = city.image_credit || "";

  // Phone/website only apply to points of interest, not plain cities —
  // hidden whenever the category picker is on "city".
  const phoneInput = document.createElement("input");
  phoneInput.type = "tel";
  setPlaceholderLabel(phoneInput, t("fieldPhone"));
  phoneInput.maxLength = 30;
  phoneInput.value = city.phone || "";
  phoneInput.hidden = city.category === "city";

  const websiteInput = document.createElement("input");
  websiteInput.type = "url";
  setPlaceholderLabel(websiteInput, t("fieldWebsite"));
  websiteInput.maxLength = 500;
  websiteInput.value = city.website || "";
  websiteInput.hidden = city.category === "city";

  const categoryPicker = buildCategoryPicker(city.category, (value) => {
    const isCity = value === "city";
    phoneInput.hidden = isCity;
    websiteInput.hidden = isCity;
  });

  const pickOnMapBtn = document.createElement("button");
  pickOnMapBtn.type = "button";
  pickOnMapBtn.className = "pick-on-map";
  pickOnMapBtn.textContent = t("adminPickOnMap");
  pickOnMapBtn.addEventListener("click", () => startPickingLocation(latInput, lngInput));

  const actions = document.createElement("div");
  actions.className = "admin-form-actions";

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.textContent = t("adminSave");

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = t("adminCancel");
  cancelBtn.addEventListener("click", refreshAdminData);

  actions.appendChild(saveBtn);
  actions.appendChild(cancelBtn);
  form.appendChild(nameInput);
  nameI18n.elements.forEach((el) => form.appendChild(el));
  form.appendChild(latInput);
  form.appendChild(lngInput);
  form.appendChild(pickOnMapBtn);
  form.appendChild(categoryPicker);
  form.appendChild(imageUrlInput);
  form.appendChild(imageCreditInput);
  form.appendChild(phoneInput);
  form.appendChild(websiteInput);
  form.appendChild(descInput);
  descriptionI18n.elements.forEach((el) => form.appendChild(el));
  form.appendChild(actions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = nameInput.value.trim();
    const latitude = parseFloat(latInput.value);
    const longitude = parseFloat(lngInput.value);
    if (!name || Number.isNaN(latitude) || Number.isNaN(longitude)) {
      showAdminMessage(t("invalidCityFields"), true);
      return;
    }
    saveBtn.disabled = true;
    const category = categoryPickerValue(categoryPicker);
    try {
      await apiRequest("PUT", `/cities/${city.id}`, {
        name, latitude, longitude, category,
        description: descInput.value.trim() || null,
        image_url: imageUrlInput.value.trim() || null,
        image_credit: imageCreditInput.value.trim() || null,
        // Cities don't get a contact section in the detail view, so
        // don't save contact info for them either — even if the fields
        // still hold text from before the category was switched to
        // "city".
        phone: category === "city" ? null : (phoneInput.value.trim() || null),
        website: category === "city" ? null : (websiteInput.value.trim() || null),
        name_i18n: nameI18n.collect(),
        description_i18n: descriptionI18n.collect(),
      });
      showAdminMessage(t("cityUpdated")(name), false);
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
  const ok = window.confirm(t("confirmDeleteRegion")(region.name));
  if (!ok) {
    return;
  }
  try {
    await apiRequest("DELETE", `/regions/${region.id}`);
    showAdminMessage(t("regionDeleted")(region.name), false);
    await refreshAdminData();
    await loadCities();
  } catch (err) {
    showAdminMessage(err.message, true);
  }
}

async function deleteCity(city) {
  const ok = window.confirm(t("confirmDeleteCity")(city.name));
  if (!ok) {
    return;
  }
  try {
    await apiRequest("DELETE", `/cities/${city.id}`);
    showAdminMessage(t("cityDeleted")(city.name), false);
    await refreshAdminData();
    await loadCities();
  } catch (err) {
    showAdminMessage(err.message, true);
  }
}

applyAdminStaticTranslations();
