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

const forumGeneralSectionEl = document.getElementById("forum-general-section");
const forumComposerEl = document.getElementById("forum-composer");
const forumBodyInputEl = document.getElementById("forum-body-input");
const forumSubmitEl = document.getElementById("forum-submit");
const forumSigninPromptEl = document.getElementById("forum-signin-prompt");
const forumPendingNoticeEl = document.getElementById("forum-pending-notice");
const forumListEl = document.getElementById("forum-list");

// A selected city/POI's own "Community opinions" widget already covers
// that place, so showing the general (Karabakh-wide) composer/list at
// the same time just reads as repetitive — hide it whenever a place is
// currently selected (i.e. #city-detail, a permanent sibling of every
// panel tab, has something in it), and bring it back once nothing's
// selected. Called on every tab switch and every place selection/
// deselection, so it can't go stale.
function updateForumGeneralVisibility() {
  const placeSelected = Boolean(detailEl.firstElementChild);
  forumGeneralSectionEl.hidden = placeSelected;
}

function applyForumStaticTranslations() {
  forumBodyInputEl.placeholder = t("forumComposerPlaceholder");
  forumSubmitEl.textContent = t("forumSubmit");
  forumSigninPromptEl.textContent = t("forumSignInPrompt");
}

function updateForumComposerVisibility() {
  const loggedIn = Boolean(currentUser);
  forumComposerEl.hidden = !loggedIn;
  forumSigninPromptEl.hidden = loggedIn;
}

forumSigninPromptEl.addEventListener("click", () => {
  if (typeof openAccountPanel === "function") {
    openAccountPanel();
  }
});

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
  updateForumComposerVisibility();
  updateForumGeneralVisibility();
  try {
    const posts = await apiRequest("GET", "/forum/posts");
    renderForumList(forumListEl, posts, t("forumEmpty"), loadGeneralForumPosts);
  } catch (err) {
    renderForumList(forumListEl, [], t("forumEmpty"), loadGeneralForumPosts);
  }
}

forumComposerEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = forumBodyInputEl.value.trim();
  if (!body) {
    return;
  }
  forumSubmitEl.disabled = true;
  try {
    const post = await apiRequest("POST", "/forum/posts", { body, target_city_id: null });
    forumBodyInputEl.value = "";
    if (post.status === "approved") {
      // Admins are auto-approved (see api/v1/views/forum.py) — the post
      // is already live, so refresh the list instead of telling them
      // it's awaiting review.
      await loadGeneralForumPosts();
    } else {
      forumPendingNoticeEl.textContent = t("forumPendingNotice");
      forumPendingNoticeEl.hidden = false;
      setTimeout(() => { forumPendingNoticeEl.hidden = true; }, 6000);
    }
  } catch (err) {
    window.alert(err.message);
  } finally {
    forumSubmitEl.disabled = false;
  }
});

// Per-city/POI opinions widget, appended under the city detail panel
// (see showCityDetail() in app.js). Built fresh every time — the detail
// panel's whole content gets replaced (detailEl.innerHTML = ...) on
// every city selection, so there's no persistent DOM to reuse here.
function buildCityForumComposer(cityId, onApprovedPost) {
  const wrapper = document.createElement("div");

  if (!currentUser) {
    const prompt = document.createElement("button");
    prompt.type = "button";
    prompt.className = "forum-signin-btn";
    prompt.textContent = t("forumSignInPrompt");
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
  textarea.placeholder = t("forumComposerPlaceholder");

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
        "POST", "/forum/posts", { body, target_city_id: cityId });
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

  section.appendChild(buildCityForumComposer(city.id, refreshList));
  section.appendChild(list);
  container.appendChild(section);

  updateForumGeneralVisibility();
  await refreshList();
}

applyForumStaticTranslations();
updateForumComposerVisibility();
