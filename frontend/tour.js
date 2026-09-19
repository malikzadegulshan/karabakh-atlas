// Guided tour: a short, manually-triggered (or once-per-browser
// automatic) walkthrough of four real UI elements — search, category
// filter, map layers, and the stats panel — using a spotlight cut
// into a dimmed backdrop plus a tooltip card. Both are positioned on
// every step from the real target's own getBoundingClientRect(),
// never hardcoded coordinates, so it stays correct across viewport
// sizes, languages, and whichever of the desktop/mobile layout a step's
// target lives in. Shares globals (t, openModalFocus, closeModalFocus,
// trapTabKey) with app.js, loaded earlier.

const tourOverlayEl = document.getElementById("tour-overlay");
const tourSpotlightEl = document.getElementById("tour-spotlight");
const tourTooltipEl = document.getElementById("tour-tooltip");
const tourDotsEl = document.getElementById("tour-dots");
const tourStepLabelEl = document.getElementById("tour-step-label");
const tourTitleEl = document.getElementById("tour-title");
const tourBodyEl = document.getElementById("tour-body");
const tourSkipEl = document.getElementById("tour-skip");
const tourBackEl = document.getElementById("tour-back");
const tourNextEl = document.getElementById("tour-next");
const tourToggleEl = document.getElementById("tour-toggle");

// Each step names candidate selectors in preference order — the first
// one actually rendered (nonzero size) is used, so a step resolves to
// whichever of the desktop rail or the mobile sheet tabs the current
// viewport is showing for the same feature (see the responsive rules
// around #rail-places/#sheet-tab-places in style.css).
const TOUR_STEPS = [
  {
    selectors: ["#search-input"],
    titleKey: "tourSearchTitle",
    bodyKey: "tourSearchBody",
  },
  {
    selectors: ["#sheet-tab-places", "#rail-places"],
    titleKey: "tourCategoriesTitle",
    bodyKey: "tourCategoriesBody",
  },
  {
    selectors: [".leaflet-control-layers-toggle", ".leaflet-control-layers"],
    titleKey: "tourLayersTitle",
    bodyKey: "tourLayersBody",
  },
  {
    selectors: ["#stats-toggle"],
    titleKey: "tourStatsTitle",
    bodyKey: "tourStatsBody",
  },
];

const TOUR_SPOT_PADDING = 6;
const TOUR_EDGE_MARGIN = 16;
const TOUR_SEEN_KEY = "kba_tour_seen";

let tourStepIndex = 0;
let tourResizeHandler = null;

// Returns the first candidate that's actually on screen right now, or
// null if none are (e.g. a step's target is covered by another
// overlay) — renderTourStep() skips a step it can't resolve rather
// than spotlighting nothing.
function resolveTourTarget(selectors) {
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (!el) {
      continue;
    }
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      return { el, rect };
    }
  }
  return null;
}

function positionTourSpotlight(target) {
  const { el, rect } = target;
  // Matches the target's own rounding (a pill search box vs. a
  // circular rail button) instead of assuming one shape.
  const radius = parseFloat(getComputedStyle(el).borderRadius) || 8;
  tourSpotlightEl.style.top = `${rect.top - TOUR_SPOT_PADDING}px`;
  tourSpotlightEl.style.left = `${rect.left - TOUR_SPOT_PADDING}px`;
  tourSpotlightEl.style.width = `${rect.width + TOUR_SPOT_PADDING * 2}px`;
  tourSpotlightEl.style.height = `${rect.height + TOUR_SPOT_PADDING * 2}px`;
  tourSpotlightEl.style.borderRadius = `${radius + TOUR_SPOT_PADDING}px`;
}

// Prefers placing the tooltip below the target, falls back above it,
// and as a last resort (little vertical room either side, e.g. a
// short landscape viewport) pins it to whichever side has more space
// — always clamped inside the viewport with a consistent edge margin.
function positionTourTooltip(rect) {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const tipRect = tourTooltipEl.getBoundingClientRect();

  const spaceBelow = viewportHeight - (rect.bottom + TOUR_SPOT_PADDING);
  const spaceAbove = rect.top - TOUR_SPOT_PADDING;
  let top;
  if (spaceBelow >= tipRect.height + TOUR_EDGE_MARGIN) {
    top = rect.bottom + TOUR_SPOT_PADDING + 10;
  } else if (spaceAbove >= tipRect.height + TOUR_EDGE_MARGIN) {
    top = rect.top - TOUR_SPOT_PADDING - 10 - tipRect.height;
  } else {
    top = spaceBelow >= spaceAbove
      ? viewportHeight - tipRect.height - TOUR_EDGE_MARGIN
      : TOUR_EDGE_MARGIN;
  }
  top = Math.max(
    TOUR_EDGE_MARGIN,
    Math.min(top, viewportHeight - tipRect.height - TOUR_EDGE_MARGIN)
  );

  const left = Math.max(
    TOUR_EDGE_MARGIN,
    Math.min(rect.left, viewportWidth - tipRect.width - TOUR_EDGE_MARGIN)
  );

  tourTooltipEl.style.top = `${top}px`;
  tourTooltipEl.style.left = `${left}px`;
}

function renderTourStep() {
  const step = TOUR_STEPS[tourStepIndex];
  const isLast = tourStepIndex === TOUR_STEPS.length - 1;

  tourTitleEl.textContent = t(step.titleKey);
  tourBodyEl.textContent = t(step.bodyKey);
  tourStepLabelEl.textContent = `${tourStepIndex + 1} / ${TOUR_STEPS.length}`;
  tourBackEl.hidden = tourStepIndex === 0;
  tourNextEl.textContent = isLast ? t("tourDone") : t("tourNext");

  tourDotsEl.innerHTML = "";
  TOUR_STEPS.forEach((_, index) => {
    const dot = document.createElement("span");
    dot.className = index === tourStepIndex ? "active" : "";
    tourDotsEl.appendChild(dot);
  });

  const target = resolveTourTarget(step.selectors);
  if (!target) {
    if (isLast) {
      closeTour();
    } else {
      tourStepIndex += 1;
      renderTourStep();
    }
    return;
  }
  positionTourSpotlight(target);
  positionTourTooltip(target.rect);
}

function openTour() {
  tourStepIndex = 0;
  tourOverlayEl.hidden = false;
  renderTourStep();
  openModalFocus(tourTooltipEl);
  tourResizeHandler = () => renderTourStep();
  window.addEventListener("resize", tourResizeHandler);
}

function closeTour() {
  tourOverlayEl.hidden = true;
  closeModalFocus();
  if (tourResizeHandler) {
    window.removeEventListener("resize", tourResizeHandler);
    tourResizeHandler = null;
  }
  try {
    localStorage.setItem(TOUR_SEEN_KEY, "1");
  } catch (err) {
    /* localStorage unavailable (e.g. private browsing) — the tour
       just won't remember it's been seen, nothing else depends on it */
  }
}

function tourGoNext() {
  if (tourStepIndex === TOUR_STEPS.length - 1) {
    closeTour();
    return;
  }
  tourStepIndex += 1;
  renderTourStep();
}

function tourGoBack() {
  if (tourStepIndex === 0) {
    return;
  }
  tourStepIndex -= 1;
  renderTourStep();
}

tourToggleEl.addEventListener("click", openTour);
tourSkipEl.addEventListener("click", closeTour);
tourBackEl.addEventListener("click", tourGoBack);
tourNextEl.addEventListener("click", tourGoNext);

tourOverlayEl.addEventListener("click", (event) => {
  if (event.target === tourOverlayEl) {
    closeTour();
  }
});

document.addEventListener("keydown", (event) => {
  if (tourOverlayEl.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closeTour();
  } else {
    trapTabKey(event, tourTooltipEl);
  }
});

tourToggleEl.setAttribute("aria-label", t("tourToggle"));
tourToggleEl.title = t("tourToggle");

// Auto-launch once per browser (kba_tour_seen, same override
// convention as kba_theme in theme-init.js) — a light first-run nudge
// toward features that are otherwise easy to miss, not a modal
// someone has to clear before they can use the map. The delay is a
// pragmatic stand-in for "once the map's own data has loaded" (app.js
// doesn't expose that as an awaitable signal) — long enough that the
// initial city fetch has normally resolved, short enough to still
// read as part of the page loading rather than a delayed interruption.
function maybeAutoStartTour() {
  let seen;
  try {
    seen = localStorage.getItem(TOUR_SEEN_KEY);
  } catch (err) {
    return;
  }
  if (!seen && tourOverlayEl.hidden) {
    openTour();
  }
}

setTimeout(maybeAutoStartTour, 800);
