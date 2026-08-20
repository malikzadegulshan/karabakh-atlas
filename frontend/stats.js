// "About this atlas" stats dashboard: a public, unauthenticated
// snapshot of what's in the atlas (region/city/POI/event/opinion
// counts) via GET /stats — mainly useful for demos and general
// curiosity, not tied to any account state. Shares globals (t,
// categoryLabel, API_BASE) with app.js/admin.js, loaded earlier.

const statsToggleEl = document.getElementById("stats-toggle");
const statsOverlayEl = document.getElementById("stats-overlay");
const statsPanelEl = document.getElementById("stats-panel");
const statsCloseEl = document.getElementById("stats-close");
const statsTitleEl = document.getElementById("stats-title");
const statsLoadingEl = document.getElementById("stats-loading");
const statsGridEl = document.getElementById("stats-grid");
const statsCategoriesEl = document.getElementById("stats-categories");
const statsCategoriesTitleEl = document.getElementById(
  "stats-categories-title");
const statsCategoriesListEl = document.getElementById(
  "stats-categories-list");

// Maps each tile's DOM id to the matching key in GET /stats's response
// and the i18n key for its label.
const STAT_TILES = [
  { id: "stat-regions", key: "regions", labelKey: "statsRegions" },
  { id: "stat-cities", key: "cities", labelKey: "statsCities" },
  { id: "stat-pois", key: "points_of_interest", labelKey: "statsPois" },
  { id: "stat-events", key: "historical_events", labelKey: "statsEvents" },
  { id: "stat-posts", key: "forum_posts", labelKey: "statsPosts" },
];

// Fetched once per page load and reused on every reopen — these
// numbers don't need to be live-second-accurate for what's essentially
// an "about" panel, and it avoids hammering the endpoint every time
// someone reopens it out of curiosity during a demo.
let statsLoadPromise = null;

function applyStatsStaticTranslations() {
  statsTitleEl.textContent = t("statsTitle");
  statsLoadingEl.textContent = t("loading");
  statsCategoriesTitleEl.textContent = t("statsByCategory");
  STAT_TILES.forEach((tile) => {
    document.getElementById(`${tile.id}-label`).textContent =
      t(tile.labelKey);
  });
}

function renderCategoryBreakdown(categories) {
  statsCategoriesListEl.innerHTML = "";
  const entries = Object.entries(categories || {})
    .sort((a, b) => b[1] - a[1]);
  statsCategoriesEl.hidden = entries.length === 0;
  if (entries.length === 0) {
    return;
  }
  const max = Math.max(...entries.map(([, count]) => count));
  entries.forEach(([category, count]) => {
    const li = document.createElement("li");
    li.className = "stats-category-row";

    const label = document.createElement("span");
    label.className = "stats-category-label";
    label.textContent = categoryLabel(category);

    const barWrap = document.createElement("span");
    barWrap.className = "stats-category-bar-wrap";
    const bar = document.createElement("span");
    bar.className = "stats-category-bar";
    bar.style.width = `${Math.max(6, (count / max) * 100)}%`;
    barWrap.appendChild(bar);

    const countEl = document.createElement("span");
    countEl.className = "stats-category-count";
    countEl.textContent = String(count);

    li.appendChild(label);
    li.appendChild(barWrap);
    li.appendChild(countEl);
    statsCategoriesListEl.appendChild(li);
  });
}

async function loadStats() {
  if (!statsLoadPromise) {
    statsLoadPromise = fetch(`${API_BASE}/stats`).then((res) => {
      if (!res.ok) {
        throw new Error(`API returned ${res.status}`);
      }
      return res.json();
    });
  }
  try {
    const data = await statsLoadPromise;
    STAT_TILES.forEach((tile) => {
      document.getElementById(tile.id).textContent = String(
        data[tile.key] || 0);
    });
    renderCategoryBreakdown(data.categories);
    statsLoadingEl.hidden = true;
    statsGridEl.hidden = false;
  } catch (err) {
    // A failed fetch shouldn't leave a stale success from a previous
    // open cached — the next reopen should retry rather than show
    // nothing forever.
    statsLoadPromise = null;
    statsLoadingEl.textContent = t("statsError");
  }
}

function openStatsPanel() {
  applyStatsStaticTranslations();
  statsOverlayEl.hidden = false;
  openModalFocus(statsPanelEl);
  loadStats();
}

function closeStatsPanel() {
  statsOverlayEl.hidden = true;
  closeModalFocus();
}

statsToggleEl.addEventListener("click", openStatsPanel);
statsCloseEl.addEventListener("click", closeStatsPanel);
statsOverlayEl.addEventListener("click", (event) => {
  if (event.target === statsOverlayEl) {
    closeStatsPanel();
  }
});
document.addEventListener("keydown", (event) => {
  if (statsOverlayEl.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closeStatsPanel();
  } else {
    trapTabKey(event, statsPanelEl);
  }
});
