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
const statsCompositionEl = document.getElementById("stats-composition");
const statsCompositionTitleEl = document.getElementById(
  "stats-composition-title");
const statsCompositionBarEl = document.getElementById(
  "stats-composition-bar");
const statsCompositionLegendEl = document.getElementById(
  "stats-composition-legend");

// Maps each tile's DOM id to the matching key in GET /stats's response
// and the i18n key for its label.
const STAT_TILES = [
  { id: "stat-regions", key: "regions", labelKey: "statsRegions" },
  { id: "stat-cities", key: "cities", labelKey: "statsCities" },
  { id: "stat-pois", key: "points_of_interest", labelKey: "statsPois" },
  { id: "stat-events", key: "historical_events", labelKey: "statsEvents" },
  { id: "stat-posts", key: "forum_posts", labelKey: "statsPosts" },
];

// The composition bar's four series — everything in STAT_TILES except
// "regions", which is a structural/organizational count rather than
// atlas *content*, so it doesn't belong in a part-to-whole breakdown
// of what's in the atlas. Colors are --viz-series-1..4 (style.css): the
// brand teal at four lightness steps rather than a multi-hue
// categorical palette, so the bar reads as part of the app — validated
// as an ordinal ramp (monotone lightness, adjacent step >= 0.06, light
// end clears 2:1 contrast), fixed order, never reassigned per-render.
const STATS_COMPOSITION_SLOTS = [
  { key: "cities", labelKey: "statsCities", colorVar: "--viz-series-1" },
  { key: "points_of_interest", labelKey: "statsPois", colorVar: "--viz-series-2" },
  { key: "historical_events", labelKey: "statsEvents", colorVar: "--viz-series-3" },
  { key: "forum_posts", labelKey: "statsPosts", colorVar: "--viz-series-4" },
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
  statsCompositionTitleEl.textContent = t("statsComposition");
  STAT_TILES.forEach((tile) => {
    document.getElementById(`${tile.id}-label`).textContent =
      t(tile.labelKey);
  });
}

// Part-to-whole composition bar — cities/POIs/events/posts as one
// segmented bar, colored by the fixed teal-shade slots in
// STATS_COMPOSITION_SLOTS. The bar itself is aria-hidden (see
// index.html): it's a visual restatement of exactly what the legend
// list already says, so nothing is screen-reader-only or gated behind
// hover — the legend is the accessible source of truth, the bar (plus
// its title-attribute hover) is a sighted-user bonus.
function renderComposition(data) {
  statsCompositionBarEl.innerHTML = "";
  statsCompositionLegendEl.innerHTML = "";
  const slots = STATS_COMPOSITION_SLOTS.map((slot) => ({
    ...slot,
    count: data[slot.key] || 0,
  }));
  const total = slots.reduce((sum, slot) => sum + slot.count, 0);
  statsCompositionEl.hidden = total === 0;
  if (total === 0) {
    return;
  }
  slots.forEach((slot) => {
    const color = `var(${slot.colorVar})`;
    const label = t(slot.labelKey);
    const pct = Math.round((slot.count / total) * 100);

    if (slot.count > 0) {
      const segment = document.createElement("div");
      segment.className = "stats-composition-segment";
      segment.style.background = color;
      segment.style.flexGrow = String(slot.count);
      segment.title = `${label}: ${slot.count} (${pct}%)`;
      statsCompositionBarEl.appendChild(segment);
    }

    const li = document.createElement("li");
    li.className = "stats-legend-row";
    const swatch = document.createElement("span");
    swatch.className = "stats-legend-swatch";
    swatch.style.background = color;
    const text = document.createElement("span");
    text.textContent = label;
    const countEl = document.createElement("span");
    countEl.className = "stats-legend-count";
    countEl.textContent = String(slot.count);
    li.appendChild(swatch);
    li.appendChild(text);
    li.appendChild(countEl);
    statsCompositionLegendEl.appendChild(li);
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
    renderComposition(data);
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
