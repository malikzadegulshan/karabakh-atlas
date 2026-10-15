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

// Keep in sync with REPORT_REASONS in models/post_report.py.
const REPORT_REASONS = [
  { value: "spam", labelKey: "reportReasonSpam" },
  { value: "abusive", labelKey: "reportReasonAbusive" },
  { value: "misleading", labelKey: "reportReasonMisleading" },
  { value: "other", labelKey: "reportReasonOther" },
];

function reportReasonLabel(value) {
  const reason = REPORT_REASONS.find((entry) => entry.value === value);
  return reason ? t(reason.labelKey) : value;
}

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
  applyReportStaticTranslations();
}

// created_at is a naive UTC timestamp (no "Z"), which new Date() would
// read as local time.
function forumDate(isoString) {
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(isoString) ? isoString : `${isoString}Z`;
  return new Date(iso);
}

// Compact on purpose ("Oct 9", or "Oct 9, 2025" once it's not this year)
// so a post's author, badge, date and Delete fit on one line in the
// narrow panel; the full date and time are in the hover title (see
// buildForumPostElement). An absolute date rather than "3 hours ago" —
// a relative formatter would need translated unit strings in 4 languages
// for little benefit on a forum this size.
function forumDateLabel(isoString) {
  const date = forumDate(isoString);
  const options = { day: "numeric", month: "short" };
  if (date.getFullYear() !== new Date().getFullYear()) {
    options.year = "numeric";
  }
  return date.toLocaleDateString(currentLang, options);
}


// Builds one post's meta line (author, tier badge, date, Delete), body,
// and Reply button. onChanged is called (and should re-fetch/re-render
// the list) after a successful delete or reply — every call site already
// has a natural "reload this list" function to pass in. rootId is the
// top-level post a reply to this one attaches to (threads are one level
// deep, see the API's create_forum_post); isReply prefills "@Name " so
// answering a reply still says who it's aimed at.
function buildForumPostElement(post, rootId, isReply, replyCount, onChanged) {
  const li = document.createElement("li");
  li.className = isReply ? "forum-post forum-reply" : "forum-post";

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

  const when = document.createElement("time");
  when.className = "forum-post-date";
  when.dateTime = forumDate(post.created_at).toISOString();
  when.title = forumDate(post.created_at).toLocaleString(currentLang);
  when.textContent = forumDateLabel(post.created_at);
  meta.appendChild(document.createTextNode(" · "));
  meta.appendChild(when);

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
      const message = replyCount > 0
        ? t("confirmDeleteForumThread")(replyCount)
        : t("confirmDeleteForumPost");
      if (!window.confirm(message)) {
        return;
      }
      try {
        await apiRequest("DELETE", `/forum/posts/${post.id}`);
        await onChanged();
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

  const actions = document.createElement("div");
  actions.className = "forum-post-actions";

  // One slot for whichever inline form (reply or report) is open; opening
  // one closes the other.
  const replySlot = document.createElement("div");
  replySlot.className = "forum-reply-slot";

  const replyBtn = document.createElement("button");
  replyBtn.type = "button";
  replyBtn.className = "forum-reply-btn";
  replyBtn.textContent = t("forumReply");
  replyBtn.addEventListener("click", () => {
    if (!currentUser) {
      if (typeof openAccountPanel === "function") {
        openAccountPanel();
      }
      return;
    }
    const wasReply = replySlot.firstChild &&
      replySlot.firstChild.classList.contains("forum-reply-form");
    replySlot.innerHTML = "";
    if (wasReply) {
      return;
    }
    replySlot.appendChild(buildReplyForm(
      rootId, isReply ? `@${post.author_name || "?"} ` : "", replySlot,
      onChanged));
  });
  actions.appendChild(replyBtn);

  // Your own posts can't be reported (the API refuses too).
  if (!currentUser || currentUser.id !== post.author_id) {
    const reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.className = "forum-reply-btn forum-report-btn";
    reportBtn.textContent = t("forumReport");
    reportBtn.addEventListener("click", () => {
      if (!currentUser) {
        if (typeof openAccountPanel === "function") {
          openAccountPanel();
        }
        return;
      }
      openReportDialog(post);
    });
    actions.appendChild(reportBtn);
  }

  li.appendChild(actions);
  li.appendChild(replySlot);
  return li;
}

const reportOverlayEl = document.getElementById("report-overlay");
const reportPanelEl = document.getElementById("report-panel");
const reportTitleEl = document.getElementById("report-title");
const reportCloseEl = document.getElementById("report-close");
const reportFormEl = document.getElementById("report-form");
const reportPreviewEl = document.getElementById("report-post-preview");
const reportReasonsEl = document.getElementById("report-reasons");
const reportLegendEl = document.getElementById("report-reasons-legend");
const reportErrorEl = document.getElementById("report-error");
const reportSubmitEl = document.getElementById("report-submit");
const reportCancelEl = document.getElementById("report-cancel");
const reportThanksEl = document.getElementById("report-thanks");
const reportThanksTextEl = document.getElementById("report-thanks-text");
const reportDoneEl = document.getElementById("report-done");

// The post currently being reported (null while the dialog is closed).
let reportingPost = null;

function applyReportStaticTranslations() {
  reportTitleEl.textContent = t("reportTitle");
  reportCloseEl.setAttribute("aria-label", t("adminClose"));
  reportLegendEl.textContent = t("reportReasonLabel");
  reportSubmitEl.textContent = t("reportSend");
  reportCancelEl.textContent = t("adminCancel");
  reportThanksTextEl.textContent = t("reportThanks");
  reportDoneEl.textContent = t("adminClose");
}

// A pop-up dialog (same overlay/focus handling as the sign-in dialog)
// rather than a form wedged into the post list: shows what is being
// reported, a short list of reasons, and only enables Send once one is
// chosen, so a stray click can't file a report by accident.
function openReportDialog(post) {
  reportingPost = post;
  applyReportStaticTranslations();

  reportPreviewEl.innerHTML = "";
  const author = document.createElement("strong");
  author.textContent = post.author_name || "?";
  const excerpt = document.createElement("p");
  excerpt.textContent = post.body.length > 200
    ? `${post.body.slice(0, 200)}…` : post.body;
  reportPreviewEl.appendChild(author);
  reportPreviewEl.appendChild(excerpt);

  reportReasonsEl.querySelectorAll("label").forEach((el) => el.remove());
  REPORT_REASONS.forEach((reason) => {
    const label = document.createElement("label");
    label.className = "report-reason";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "report-reason";
    radio.value = reason.value;
    radio.addEventListener("change", () => { reportSubmitEl.disabled = false; });
    const text = document.createElement("span");
    text.textContent = t(reason.labelKey);
    label.appendChild(radio);
    label.appendChild(text);
    reportReasonsEl.appendChild(label);
  });

  reportErrorEl.hidden = true;
  reportErrorEl.textContent = "";
  reportSubmitEl.disabled = true;
  reportFormEl.hidden = false;
  reportThanksEl.hidden = true;
  reportOverlayEl.hidden = false;
  openModalFocus(reportPanelEl);
}

function closeReportDialog() {
  reportOverlayEl.hidden = true;
  reportingPost = null;
  closeModalFocus();
}

reportCloseEl.addEventListener("click", closeReportDialog);
reportCancelEl.addEventListener("click", closeReportDialog);
reportDoneEl.addEventListener("click", closeReportDialog);
reportOverlayEl.addEventListener("click", (event) => {
  if (event.target === reportOverlayEl) {
    closeReportDialog();
  }
});
document.addEventListener("keydown", (event) => {
  if (reportOverlayEl.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closeReportDialog();
  } else {
    trapTabKey(event, reportPanelEl);
  }
});

reportFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const chosen = reportFormEl.querySelector('input[name="report-reason"]:checked');
  if (!chosen || !reportingPost) {
    return;
  }
  reportSubmitEl.disabled = true;
  reportErrorEl.hidden = true;
  try {
    await apiRequest(
      "POST", `/forum/posts/${reportingPost.id}/report`,
      { reason: chosen.value });
  } catch (err) {
    reportErrorEl.textContent = err.message;
    reportErrorEl.hidden = false;
    reportSubmitEl.disabled = false;
    return;
  }
  reportFormEl.hidden = true;
  reportThanksEl.hidden = false;
  reportDoneEl.focus();
});

function buildReplyForm(rootId, prefill, slot, onChanged) {
  const form = document.createElement("form");
  form.className = "admin-form forum-reply-form";

  const textarea = document.createElement("textarea");
  textarea.rows = 2;
  textarea.maxLength = 2000;
  setPlaceholderLabel(textarea, t("forumReplyPlaceholder"));
  textarea.value = prefill;

  const actions = document.createElement("div");
  actions.className = "admin-form-actions";
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = t("forumSubmit");
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = t("adminCancel");
  cancel.addEventListener("click", () => { slot.innerHTML = ""; });
  actions.appendChild(submit);
  actions.appendChild(cancel);

  form.appendChild(textarea);
  form.appendChild(actions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = textarea.value.trim();
    // A reply that is only the "@Name " prefill isn't a reply yet.
    if (!body || body === prefill.trim()) {
      return;
    }
    submit.disabled = true;
    try {
      const post = await apiRequest(
        "POST", "/forum/posts", { body, parent_id: rootId });
      if (post.status === "approved") {
        await onChanged();
        return;
      }
      // Pending (non-admin): the reply isn't visible yet, so replace
      // the form with the same notice posting elsewhere shows.
      const notice = document.createElement("p");
      notice.className = "forum-pending-notice";
      notice.textContent = t("forumPendingNotice");
      slot.innerHTML = "";
      slot.appendChild(notice);
    } catch (err) {
      window.alert(err.message);
      submit.disabled = false;
    }
  });

  // Focus once the form is in the document, caret after any "@Name "
  // prefill so typing continues from there.
  setTimeout(() => {
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }, 0);
  return form;
}

// Top-level posts newest first (as the API returns them), each with its
// replies underneath oldest first so a thread reads top to bottom. A
// reply whose parent isn't in the list is skipped rather than shown
// orphaned (the API already hides replies of unpublished posts; this
// just keeps the render safe against a list filtered some other way).
function renderForumList(container, posts, emptyMessage, onChanged) {
  container.innerHTML = "";
  if (posts.length === 0) {
    const empty = document.createElement("p");
    empty.className = "admin-empty";
    empty.textContent = emptyMessage;
    container.appendChild(empty);
    return;
  }
  const repliesByParent = new Map();
  posts.filter((post) => post.parent_id).forEach((reply) => {
    const thread = repliesByParent.get(reply.parent_id) || [];
    thread.push(reply);
    repliesByParent.set(reply.parent_id, thread);
  });
  posts.filter((post) => !post.parent_id).forEach((post) => {
    const replies = (repliesByParent.get(post.id) || []).slice().sort(
      (a, b) => new Date(a.created_at) - new Date(b.created_at));
    const li = buildForumPostElement(
      post, post.id, false, replies.length, onChanged);
    if (replies.length > 0) {
      const thread = document.createElement("ul");
      thread.className = "forum-replies";
      replies.forEach((reply) => {
        thread.appendChild(
          buildForumPostElement(reply, post.id, true, 0, onChanged));
      });
      li.appendChild(thread);
    }
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
