// Favorites: a logged-in user's saved places, plus the save/unsave
// toggle shown in a place's detail view. Shares globals (t, currentUser,
// apiRequest, localizedName, cityMarkers, jumpToCity, openAccountPanel,
// closeAccountStatusPopover, ...) with app.js/auth.js/forum.js, all
// loaded earlier on the page.

const detailFavoriteToggleEl = document.getElementById(
  "detail-favorite-toggle");
const accountFavoritesEl = document.getElementById("account-favorites");
const accountFavoritesTitleEl = document.getElementById(
  "account-favorites-title");
const accountFavoritesListEl = document.getElementById(
  "account-favorites-list");
const accountFavoritesEmptyEl = document.getElementById(
  "account-favorites-empty");

let favoriteCityIds = new Set();
// The full city objects behind favoriteCityIds — kept alongside it so
// the account dropdown list can show names without a second round trip
// (the API already returns full City objects, not just ids).
let favoritesCache = [];
// Whichever place the detail view is currently showing, so a toggle
// click (or a favorites list refresh) knows what it's acting on —
// #detail-favorite-toggle is a single persistent button, not rebuilt
// per city the way #city-detail's own innerHTML is.
let favoriteToggleCity = null;

function isFavorited(cityId) {
  return favoriteCityIds.has(cityId);
}

function updateFavoriteToggle(city) {
  favoriteToggleCity = city;
  const favorited = isFavorited(city.id);
  detailFavoriteToggleEl.classList.toggle("is-favorited", favorited);
  detailFavoriteToggleEl.setAttribute("aria-pressed", String(favorited));
  const label = t(favorited ? "favoriteRemove" : "favoriteAdd");
  detailFavoriteToggleEl.title = label;
  detailFavoriteToggleEl.setAttribute("aria-label", label);
}

function renderAccountFavoritesList() {
  accountFavoritesEl.hidden = !currentUser;
  if (!currentUser) {
    return;
  }
  accountFavoritesTitleEl.textContent = t("accountFavoritesTitle");
  const empty = favoritesCache.length === 0;
  accountFavoritesEmptyEl.hidden = !empty;
  accountFavoritesEmptyEl.textContent = t("accountFavoritesEmpty");
  accountFavoritesListEl.hidden = empty;
  accountFavoritesListEl.innerHTML = "";
  favoritesCache.forEach((city) => {
    const li = document.createElement("li");
    const row = document.createElement("button");
    row.type = "button";
    row.className = "account-favorite-row";
    row.textContent = localizedName(city);
    row.addEventListener("click", () => {
      closeAccountStatusPopover();
      const entry = cityMarkers.get(city.id);
      if (entry) {
        jumpToCity(entry.city, entry.marker);
      }
    });
    li.appendChild(row);
    accountFavoritesListEl.appendChild(li);
  });
}

// Called from renderAccountWidget() (auth.js) via the same guarded-call
// pattern app.js already uses for forum.js's renderCityForumSection —
// every place currentUser changes (login, register, reset-password,
// logout, boot) already calls that one function, so hooking there
// covers every case without touching each call site individually.
async function refreshFavorites() {
  if (!currentUser) {
    favoriteCityIds = new Set();
    favoritesCache = [];
    renderAccountFavoritesList();
    if (favoriteToggleCity) {
      updateFavoriteToggle(favoriteToggleCity);
    }
    return;
  }
  try {
    favoritesCache = await apiRequest("GET", "/favorites");
  } catch (err) {
    favoritesCache = [];
  }
  favoriteCityIds = new Set(favoritesCache.map((c) => c.id));
  renderAccountFavoritesList();
  if (favoriteToggleCity) {
    updateFavoriteToggle(favoriteToggleCity);
  }
}

detailFavoriteToggleEl.addEventListener("click", async () => {
  if (!favoriteToggleCity) {
    return;
  }
  if (!currentUser) {
    if (typeof openAccountPanel === "function") {
      openAccountPanel();
    }
    return;
  }
  const city = favoriteToggleCity;
  const wasFavorited = isFavorited(city.id);
  detailFavoriteToggleEl.disabled = true;
  try {
    if (wasFavorited) {
      await apiRequest("DELETE", `/favorites/${city.id}`);
      favoriteCityIds.delete(city.id);
      favoritesCache = favoritesCache.filter((c) => c.id !== city.id);
    } else {
      // The response is the Favorite row itself (id/user_id/city_id/
      // timestamps), not a City — favoritesCache holds City objects, so
      // it's `city` (already in hand from the caller) that goes in, not
      // the response body.
      await apiRequest("POST", "/favorites", { city_id: city.id });
      favoriteCityIds.add(city.id);
      if (!favoritesCache.some((c) => c.id === city.id)) {
        favoritesCache.unshift(city);
      }
    }
    updateFavoriteToggle(city);
    renderAccountFavoritesList();
  } catch (err) {
    window.alert(err.message);
  } finally {
    detailFavoriteToggleEl.disabled = false;
  }
});
