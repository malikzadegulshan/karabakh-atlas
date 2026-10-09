// News tab: posts written by admins (see api/v1/views/news.py), each
// with an optional picture, and a comment thread underneath. Comments
// are ordinary forum posts targeting the news item (target_news_id), so
// they go through the same admin moderation queue and rate limit as
// every other forum post — this file just renders and submits them via
// forum.js's renderForumList()/buildForumComposer(). Shares globals
// (t, escapeHtml, isSafeUrl, compressedImageUrl, currentLang,
// apiRequest, currentUser) with app.js/auth.js/admin.js/forum.js, all
// loaded earlier on the page.
//
// Security note: titles, bodies, and comment bodies are all rendered
// with textContent (never innerHTML), and URLs only after isSafeUrl().

const newsListEl = document.getElementById("news-list");

let newsItems = [];
// Until the first fetch lands there's nothing to render — without this,
// a re-render triggered by a login/language change would flash "No news
// yet" for a list that simply hasn't loaded.
let newsLoaded = false;
// Items whose comment thread is open, so a re-render (login, logout,
// language change) puts them back instead of collapsing everything.
const newsOpenComments = new Set();

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

function buildNewsComments(item, toggleBtn) {
  const section = document.createElement("div");
  section.className = "news-comments";

  const list = document.createElement("ul");
  list.className = "forum-post-list";

  function updateToggleLabel() {
    toggleBtn.textContent = t("newsComments")(item.comment_count);
  }

  async function refreshComments() {
    try {
      const posts = await apiRequest(
        "GET", `/forum/posts?news_id=${encodeURIComponent(item.id)}`);
      item.comment_count = posts.length;
      updateToggleLabel();
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

function buildNewsCard(item) {
  const card = document.createElement("li");
  card.className = "news-card";

  if (item.image_url && isSafeUrl(item.image_url)) {
    const img = document.createElement("img");
    img.className = "news-card-image";
    img.loading = "lazy";
    img.alt = localizedNewsTitle(item);
    img.src = compressedImageUrl(item.image_url, 640, 360);
    // The compression proxy can't always reach a given host (or the
    // image may already be small) — fall back to the original once,
    // and only hide the picture if that fails too.
    img.addEventListener("error", () => {
      if (img.dataset.fallback === "1") {
        img.hidden = true;
        return;
      }
      img.dataset.fallback = "1";
      img.src = item.image_url;
    });
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
  moreBtn.hidden = true;
  moreBtn.addEventListener("click", () => {
    const clamped = body.classList.toggle("clamped");
    moreBtn.textContent = clamped ? t("newsReadMore") : t("newsShowLess");
  });
  footer.appendChild(moreBtn);

  if (item.source_url && isSafeUrl(item.source_url)) {
    const source = document.createElement("a");
    source.className = "news-link-btn";
    source.href = item.source_url;
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    source.textContent = t("newsSource");
    footer.appendChild(source);
  }

  const commentsBtn = document.createElement("button");
  commentsBtn.type = "button";
  commentsBtn.className = "news-link-btn news-comments-toggle";
  commentsBtn.setAttribute("aria-expanded", "false");
  commentsBtn.textContent = t("newsComments")(item.comment_count || 0);
  let commentsSection = null;
  function setCommentsOpen(open) {
    if (open && commentsSection === null) {
      commentsSection = buildNewsComments(item, commentsBtn);
      card.appendChild(commentsSection);
    }
    if (commentsSection !== null) {
      commentsSection.hidden = !open;
    }
    commentsBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      newsOpenComments.add(item.id);
    } else {
      newsOpenComments.delete(item.id);
    }
  }
  commentsBtn.addEventListener("click", () => {
    setCommentsOpen(commentsSection === null || commentsSection.hidden);
  });
  footer.appendChild(commentsBtn);

  card.appendChild(footer);
  if (newsOpenComments.has(item.id)) {
    setCommentsOpen(true);
  }

  // "Read more" only when the text is actually cut off, which needs
  // real layout — checked once the card is in the document.
  card._checkOverflow = () => {
    moreBtn.hidden = body.scrollHeight <= body.clientHeight + 1 &&
      body.classList.contains("clamped");
  };
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
  const cards = newsItems.map(buildNewsCard);
  cards.forEach((card) => newsListEl.appendChild(card));
  cards.forEach((card) => card._checkOverflow());
}

async function loadNews() {
  try {
    newsItems = await apiRequest("GET", "/news");
  } catch (err) {
    newsItems = [];
  }
  newsLoaded = true;
  renderNews();
}
