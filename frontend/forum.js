// Community forum: opinions about Karabakh in general, plus per-city and
// per-POI opinions shown alongside their detail panel. Shares globals
// (t, escapeHtml, currentLang, apiRequest, currentUser, openAccountPanel,
// ...) with app.js/auth.js/admin.js, all loaded earlier on the page.
//
// Every post starts "pending" and only ever becomes publicly visible
// once an admin approves it (see api/v1/views/forum.py) — this file
// never assumes otherwise; the general list and the per-city list both
// just render whatever the (moderation-aware) API hands back.
//
// Security note: post bodies are untrusted, unmoderated-at-render-time
// user text. Every place this file puts one on the page goes through
// escapeHtml() first — never innerHTML with a raw body.

const forumViewEl = document.getElementById("forum-view");

// Keep in sync with TOPICS in models/forum_post.py (the real source of
// truth — the API rejects anything else). Order here is display order.
const FORUM_TOPICS = [
  { value: "general", labelKey: "topicGeneral", hintKey: "topicGeneralHint" },
  { value: "global", labelKey: "topicGlobal", hintKey: "topicGlobalHint" },
  { value: "student_life", labelKey: "topicStudentLife", hintKey: "topicStudentLifeHint" },
  { value: "about_karabakh", labelKey: "topicAboutKarabakh", hintKey: "topicAboutKarabakhHint" },
  { value: "events_holidays", labelKey: "topicEventsHolidays", hintKey: "topicEventsHolidaysHint" },
  { value: "introductions", labelKey: "topicIntroductions", hintKey: "topicIntroductionsHint" },
];
const FORUM_DEFAULT_TOPIC = "general";

function forumTopicLabel(value) {
  const topic = FORUM_TOPICS.find((entry) => entry.value === value);
  return topic ? t(topic.labelKey) : null;
}

// The forum tab is a two-level drill-down, like opening a place: a list
// of topics (name, description, post count), and tapping one replaces
// the list with just that topic's page — Back button, description, its
// own posting box, and its posts. Every general post comes back from
// one request and is grouped client-side by post.topic.
let forumGeneralPosts = [];
let forumPostsLoaded = false;
// The topic whose page is showing, or null for the topic list. Kept
// across re-renders (login, language change, posting) so the reader
// stays where they were.
let forumCurrentTopic = null;

function forumTopicPosts(topicValue) {
  return forumGeneralPosts.filter((post) => post.topic === topicValue);
}

function openForumTopic(topicValue) {
  forumCurrentTopic = topicValue;
  renderForumTab();
  // The panel scrolls as one column, so a long list would otherwise
  // leave the new page opened partway down.
  document.getElementById("panel-content").scrollTop = 0;
}

function buildForumTopicList() {
  const list = document.createElement("div");
  list.className = "forum-topic-list";
  FORUM_TOPICS.forEach((topic) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "forum-topic-card";

    const text = document.createElement("span");
    text.className = "forum-topic-card-text";
    const name = document.createElement("span");
    name.className = "forum-topic-card-name";
    name.textContent = t(topic.labelKey);
    const hint = document.createElement("span");
    hint.className = "forum-topic-card-hint";
    hint.textContent = t(topic.hintKey);
    text.appendChild(name);
    text.appendChild(hint);

    const count = document.createElement("span");
    count.className = "forum-topic-card-count";
    count.textContent = String(forumTopicPosts(topic.value).length);
    const chevron = document.createElement("span");
    chevron.className = "forum-topic-card-chevron";
    chevron.setAttribute("aria-hidden", "true");

    card.appendChild(text);
    card.appendChild(count);
    card.appendChild(chevron);
    card.addEventListener("click", () => openForumTopic(topic.value));
    list.appendChild(card);
  });
  return list;
}

function buildForumTopicPage(topic) {
  const page = document.createElement("div");
  page.className = "forum-topic-page";

  const back = document.createElement("button");
  back.type = "button";
  back.className = "forum-topic-back";
  const arrow = document.createElement("span");
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "←";
  back.appendChild(arrow);
  back.appendChild(document.createTextNode(` ${t("adminBack")}`));
  back.addEventListener("click", () => openForumTopic(null));
  page.appendChild(back);

  const title = document.createElement("h3");
  title.className = "forum-topic-title";
  title.textContent = t(topic.labelKey);
  page.appendChild(title);

  const hint = document.createElement("p");
  hint.className = "forum-topic-hint";
  hint.textContent = t(topic.hintKey);
  page.appendChild(hint);

  page.appendChild(buildForumComposer(
    "target_city_id", null, loadGeneralForumPosts, "forumSignInPrompt",
    { topic: topic.value }));

  const list = document.createElement("ul");
  list.className = "forum-post-list";
  renderForumList(
    list, forumTopicPosts(topic.value), t("forumEmpty"),
    loadGeneralForumPosts);
  page.appendChild(list);
  return page;
}

function renderForumTab() {
  if (!forumPostsLoaded) {
    return;
  }
  forumViewEl.innerHTML = "";
  const topic = FORUM_TOPICS.find((entry) => entry.value === forumCurrentTopic);
  forumViewEl.appendChild(
    topic ? buildForumTopicPage(topic) : buildForumTopicList());
}

function applyForumStaticTranslations() {
  renderForumTab();
}

function forumDateLabel(isoString) {
  // An absolute, locale-formatted date/time rather than a "3 hours ago"
  // relative formatter — the latter would need its own translated unit
  // strings across 4 languages for not much benefit on a forum this size.
  return new Date(isoString).toLocaleString(currentLang);
}

// onDeleted is called (and should re-fetch/re-render) after a
// successful delete — both call sites below already have a natural
// "reload this list" function to pass in.
function renderForumList(container, posts, emptyMessage, onDeleted) {
  container.innerHTML = "";
  if (posts.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = emptyMessage;
    container.appendChild(empty);
    return;
  }
  posts.forEach((post) => {
    const li = document.createElement("li");
    li.className = "forum-post";

    const meta = document.createElement("div");
    meta.className = "forum-post-meta";
    const author = document.createElement("strong");
    author.textContent = post.author_name || "?";
    meta.appendChild(author);

    const tier = tierLabel(post.author_tier);
    if (tier) {
      const badge = document.createElement("span");
      badge.className = `tier-badge tier-badge-${post.author_tier}`;
      badge.textContent = tier;
      meta.appendChild(badge);
    }

    meta.appendChild(document.createTextNode(" · " + forumDateLabel(post.created_at)));

    // The API itself is the real enforcement point (author-or-admin,
    // see DELETE /forum/posts/<id>) — this button is just hidden
    // client-side for anyone it wouldn't work for.
    const canDelete = currentUser &&
      (currentUser.role === "admin" || currentUser.id === post.author_id);
    if (canDelete) {
      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "forum-post-delete";
      deleteBtn.textContent = t("adminDelete");
      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm(t("confirmDeleteForumPost"))) {
          return;
        }
        try {
          await apiRequest("DELETE", `/forum/posts/${post.id}`);
          await onDeleted();
        } catch (err) {
          window.alert(err.message);
        }
      });
      meta.appendChild(deleteBtn);
    }

    li.appendChild(meta);

    const body = document.createElement("p");
    body.className = "forum-post-body";
    body.textContent = post.body;
    li.appendChild(body);

    container.appendChild(li);
  });
}

async function loadGeneralForumPosts() {
  try {
    forumGeneralPosts = await apiRequest("GET", "/forum/posts");
  } catch (err) {
    forumGeneralPosts = [];
  }
  forumPostsLoaded = true;
  renderForumTab();
}

// Composer for a post tied to one target — a city/POI (targetField
// "target_city_id", the per-place opinions widget appended under the
// city detail panel, see showCityDetail() in app.js), a news item
// (targetField "target_news_id", its comments in news.js), or — with a
// null targetId — a general post in one forum topic (extraPayload
// carries {topic}, see buildForumSection() above). Built fresh
// every time: the detail panel's whole content gets replaced
// (detailEl.innerHTML = ...) on every city selection, and each news
// card builds its own, so there's no persistent DOM to reuse here.
function buildForumComposer(
  targetField, targetId, onApprovedPost, signInKey = "forumSignInPrompt",
  extraPayload = {}) {
  const wrapper = document.createElement("div");

  if (!currentUser) {
    const prompt = document.createElement("button");
    prompt.type = "button";
    prompt.className = "forum-signin-btn";
    prompt.textContent = t(signInKey);
    prompt.addEventListener("click", () => {
      if (typeof openAccountPanel === "function") {
        openAccountPanel();
      }
    });
    wrapper.appendChild(prompt);
    return wrapper;
  }

  const form = document.createElement("form");
  form.className = "admin-form";

  const textarea = document.createElement("textarea");
  textarea.rows = 2;
  textarea.maxLength = 2000;
  setPlaceholderLabel(textarea, t("forumComposerPlaceholder"));

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = t("forumSubmit");

  const notice = document.createElement("p");
  notice.className = "forum-pending-notice";
  notice.hidden = true;

  form.appendChild(textarea);
  form.appendChild(submit);
  wrapper.appendChild(form);
  wrapper.appendChild(notice);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = textarea.value.trim();
    if (!body) {
      return;
    }
    submit.disabled = true;
    try {
      const post = await apiRequest(
        "POST", "/forum/posts",
        { body, [targetField]: targetId, ...extraPayload });
      textarea.value = "";
      if (post.status === "approved") {
        // Admins are auto-approved — it's already live, so refresh the
        // list instead of telling them it's awaiting review.
        await onApprovedPost();
      } else {
        notice.textContent = t("forumPendingNotice");
        notice.hidden = false;
      }
    } catch (err) {
      window.alert(err.message);
    } finally {
      submit.disabled = false;
    }
  });

  return wrapper;
}

async function renderCityForumSection(container, city) {
  const section = document.createElement("div");
  section.id = "city-forum";

  const heading = document.createElement("h4");
  heading.textContent = t("forumSectionTitle");
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "forum-post-list";

  async function refreshList() {
    try {
      const posts = await apiRequest(
        "GET", `/forum/posts?city_id=${encodeURIComponent(city.id)}`);
      // The panel may have already moved on to a different city by now
      // (detailEl.innerHTML gets replaced wholesale on every selection)
      // — bail rather than render into a detached section. Same guard
      // pattern as loadWeatherFor() in app.js.
      if (!container.contains(section)) {
        return;
      }
      renderForumList(list, posts, t("forumCityEmpty"), refreshList);
    } catch (err) {
      if (container.contains(section)) {
        renderForumList(list, [], t("forumCityEmpty"), refreshList);
      }
    }
  }

  section.appendChild(
    buildForumComposer("target_city_id", city.id, refreshList));
  section.appendChild(list);
  container.appendChild(section);

  await refreshList();
}

applyForumStaticTranslations();
