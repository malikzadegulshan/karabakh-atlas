// News tab: posts written by admins (see api/v1/views/news.py), each
// with an optional picture, and a comment thread underneath. Comments
// are ordinary forum posts targeting the news item (target_news_id), so
// they go through the same admin moderation queue and rate limit as
// every other forum post — this file just renders and submits them via
// forum.js's renderForumList()/buildForumComposer(). Shares globals
// (t, escapeHtml, isSafeUrl, compressedImageUrl, currentLang,
// apiRequest, currentUser, updateSearchResultsVisibility) with
// app.js/auth.js/admin.js/forum.js, all loaded earlier on the page.
//
// Security note: titles, bodies, and comment bodies are all rendered
// with textContent (never innerHTML), and URLs only after isSafeUrl().

const newsListEl = document.getElementById("news-list");

let newsItems = [];
// Until the first fetch lands there's nothing to render — without this,
// a re-render triggered by a login/language change would flash "No news
// yet" for a list that simply hasn't loaded.
let newsLoaded = false;
// The news article whose dedicated page is currently open in the sidebar,
// or null when showing the news card feed. Kept across re-renders (login,
// logout, language change) so the reader stays on the open article.
let newsCurrentItemId = null;

function isNewsArticleOpen() {
  return newsCurrentItemId !== null &&
    newsItems.some((item) => item.id === newsCurrentItemId);
}

function openNewsItem(itemId, { scrollToComments = false } = {}) {
  newsCurrentItemId = itemId;
  if (typeof updateSearchResultsVisibility === "function") {
    updateSearchResultsVisibility();
  }
  if (itemId !== null && typeof setPanelCollapsed === "function") {
    setPanelCollapsed(false);
  }
  renderNews();
  const panelContentEl = document.getElementById("panel-content");
  if (!panelContentEl) {
    return;
  }
  if (scrollToComments && itemId !== null) {
    const commentsEl = newsListEl.querySelector(".news-comments");
    if (commentsEl) {
      commentsEl.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
  }
  panelContentEl.scrollTop = 0;
}

function closeNewsArticle() {
  openNewsItem(null);
}

function localizedNewsTitle(item) {
  return (item.title_i18n && item.title_i18n[currentLang]) || item.title;
}

function localizedNewsBody(item) {
  return (item.body_i18n && item.body_i18n[currentLang]) || item.body;
}

// created_at comes back as a naive UTC timestamp (no "Z"), which
// new Date() would otherwise read as local time and can land on the
// wrong calendar day.
function newsDateLabel(isoString) {
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(isoString) ? isoString : `${isoString}Z`;
  return new Date(iso).toLocaleDateString(
    currentLang, { year: "numeric", month: "long", day: "numeric" });
}

function attachNewsImageFallback(img, originalUrl) {
  img.addEventListener("error", () => {
    if (img.dataset.fallback === "1") {
      img.hidden = true;
      return;
    }
    img.dataset.fallback = "1";
    img.src = originalUrl;
  });
}

function buildNewsComments(item) {
  const section = document.createElement("div");
  section.className = "news-comments";

  const heading = document.createElement("h4");
  heading.className = "news-comments-heading";
  heading.textContent = t("newsComments")(item.comment_count || 0);
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "forum-post-list";

  async function refreshComments() {
    try {
      const posts = await apiRequest(
        "GET", `/forum/posts?news_id=${encodeURIComponent(item.id)}`);
      item.comment_count = posts.length;
      heading.textContent = t("newsComments")(item.comment_count);
      renderForumList(list, posts, t("newsCommentsEmpty"), refreshComments);
    } catch (err) {
      renderForumList(list, [], t("newsCommentsEmpty"), refreshComments);
    }
  }

  section.appendChild(buildForumComposer(
    "target_news_id", item.id, refreshComments, "newsSignInToComment"));
  section.appendChild(list);
  refreshComments();
  return section;
}

function buildNewsArticlePage(item) {
  const page = document.createElement("li");
  page.className = "news-article-page";

  const back = document.createElement("button");
  back.type = "button";
  back.className = "forum-topic-back news-article-back";
  const arrow = document.createElement("span");
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "←";
  back.appendChild(arrow);
  back.appendChild(document.createTextNode(` ${t("adminBack")}`));
  back.addEventListener("click", () => openNewsItem(null));
  page.appendChild(back);

  if (item.image_url && isSafeUrl(item.image_url)) {
    const img = document.createElement("img");
    img.className = "news-article-image";
    img.alt = localizedNewsTitle(item);
    img.src = compressedImageUrl(item.image_url, 760, 428);
    attachNewsImageFallback(img, item.image_url);
    page.appendChild(img);
  }

  const date = document.createElement("div");
  date.className = "news-card-date";
  date.textContent = newsDateLabel(item.created_at);
  page.appendChild(date);

  const title = document.createElement("h3");
  title.className = "news-article-title";
  title.textContent = localizedNewsTitle(item);
  page.appendChild(title);

  const body = document.createElement("p");
  body.className = "news-article-body";
  body.textContent = localizedNewsBody(item);
  page.appendChild(body);

  if (item.source_url && isSafeUrl(item.source_url)) {
    const metaFooter = document.createElement("div");
    metaFooter.className = "news-article-meta";
    const source = document.createElement("a");
    source.className = "news-link-btn";
    source.href = item.source_url;
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    source.textContent = `${t("newsSource")} ↗`;
    metaFooter.appendChild(source);
    page.appendChild(metaFooter);
  }

  page.appendChild(buildNewsComments(item));
  return page;
}

function buildNewsCard(item) {
  const card = document.createElement("li");
  card.className = "news-card news-card-clickable";
  card.tabIndex = 0;

  if (item.image_url && isSafeUrl(item.image_url)) {
    const img = document.createElement("img");
    img.className = "news-card-image";
    img.loading = "lazy";
    img.alt = localizedNewsTitle(item);
    img.src = compressedImageUrl(item.image_url, 640, 360);
    attachNewsImageFallback(img, item.image_url);
    card.appendChild(img);
  }

  const date = document.createElement("div");
  date.className = "news-card-date";
  date.textContent = newsDateLabel(item.created_at);
  card.appendChild(date);

  const title = document.createElement("h3");
  title.className = "news-card-title";
  title.textContent = localizedNewsTitle(item);
  card.appendChild(title);

  const body = document.createElement("p");
  body.className = "news-card-body clamped";
  body.textContent = localizedNewsBody(item);
  card.appendChild(body);

  const footer = document.createElement("div");
  footer.className = "news-card-footer";

  const moreBtn = document.createElement("button");
  moreBtn.type = "button";
  moreBtn.className = "news-link-btn";
  moreBtn.textContent = t("newsReadMore");
  moreBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    openNewsItem(item.id);
  });
  footer.appendChild(moreBtn);

  if (item.source_url && isSafeUrl(item.source_url)) {
    const source = document.createElement("a");
    source.className = "news-link-btn";
    source.href = item.source_url;
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    source.textContent = t("newsSource");
    source.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    footer.appendChild(source);
  }

  const commentsBtn = document.createElement("button");
  commentsBtn.type = "button";
  commentsBtn.className = "news-link-btn news-comments-toggle";
  commentsBtn.textContent = t("newsComments")(item.comment_count || 0);
  commentsBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    openNewsItem(item.id, { scrollToComments: true });
  });
  footer.appendChild(commentsBtn);

  card.appendChild(footer);

  card.addEventListener("click", (event) => {
    if (event.target.closest("a, button")) {
      return;
    }
    openNewsItem(item.id);
  });

  card.addEventListener("keydown", (event) => {
    if (event.target !== card) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openNewsItem(item.id);
    }
  });

  return card;
}

function renderNews() {
  if (!newsLoaded) {
    return;
  }
  newsListEl.innerHTML = "";
  if (newsItems.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = t("newsEmpty");
    newsListEl.appendChild(empty);
    return;
  }
  const activeItem = newsItems.find((item) => item.id === newsCurrentItemId);
  if (activeItem) {
    newsListEl.appendChild(buildNewsArticlePage(activeItem));
    return;
  }
  newsCurrentItemId = null;
  newsItems.forEach((item) => newsListEl.appendChild(buildNewsCard(item)));
}

async function loadNews() {
  try {
    newsItems = await apiRequest("GET", "/news");
  } catch (err) {
    newsItems = [];
  }
  newsLoaded = true;
  if (typeof updateSearchResultsVisibility === "function") {
    updateSearchResultsVisibility();
  }
  renderNews();
}
