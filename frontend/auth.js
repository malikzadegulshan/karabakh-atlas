// Account widget: sign in / register / log out, and gating the "Manage"
// button to admins only. Shares globals (API_BASE, t, escapeHtml, ...)
// with app.js, which is loaded first on the page.

let currentUser = null;

const accountWidgetEl = document.getElementById("account-widget");
const accountSigninToggleEl = document.getElementById("account-signin-toggle");
const accountAvatarToggleEl = document.getElementById("account-avatar-toggle");
const accountStatusEl = document.getElementById("account-status");
const accountNameEl = document.getElementById("account-name");
const accountResendEl = document.getElementById("account-resend-verification");
const accountLogoutEl = document.getElementById("account-logout");
const accountOverlayEl = document.getElementById("account-overlay");
const accountTitleEl = document.getElementById("account-title");
const accountCloseEl = document.getElementById("account-close");
const accountMessageEl = document.getElementById("account-message");
const accountTabLoginEl = document.getElementById("account-tab-login");
const accountTabRegisterEl = document.getElementById("account-tab-register");
const loginFormEl = document.getElementById("login-form");
const loginEmailInputEl = document.getElementById("login-email-input");
const loginPasswordInputEl = document.getElementById("login-password-input");
const loginFormSubmitEl = document.getElementById("login-form-submit");
const registerFormEl = document.getElementById("register-form");
const registerNameInputEl = document.getElementById("register-name-input");
const registerEmailInputEl = document.getElementById("register-email-input");
const registerPasswordInputEl = document.getElementById("register-password-input");
const registerFormSubmitEl = document.getElementById("register-form-submit");
const accountLegalNoteEl = document.getElementById("account-legal-note");
const adminToggleEl = document.getElementById("admin-toggle");

function applyAccountStaticTranslations() {
  accountSigninToggleEl.setAttribute("aria-label", t("accountSignIn"));
  accountSigninToggleEl.title = t("accountSignIn");
  accountLogoutEl.textContent = t("accountSignOut");
  accountTabLoginEl.textContent = t("accountSignIn");
  accountTabRegisterEl.textContent = t("accountCreateAccount");
  loginEmailInputEl.placeholder = t("accountEmail");
  loginPasswordInputEl.placeholder = t("accountPassword");
  loginFormSubmitEl.textContent = t("accountSignIn");
  registerNameInputEl.placeholder = t("fieldName");
  registerEmailInputEl.placeholder = t("accountEmail");
  registerPasswordInputEl.placeholder = t("accountPassword");
  registerFormSubmitEl.textContent = t("accountCreateAccount");
  accountTitleEl.textContent = accountTabLoginEl.classList.contains("active")
    ? t("accountSignIn")
    : t("accountCreateAccount");
  accountResendEl.textContent = t("accountResendVerification");
  // The link hrefs are static, app-controlled markup (not user input),
  // built here rather than as plain translated strings so each
  // language can phrase the sentence naturally around them.
  const termsLink = `<a href="terms.html" target="_blank" rel="noopener">${t("accountTermsLink")}</a>`;
  const privacyLink = `<a href="privacy.html" target="_blank" rel="noopener">${t("accountPrivacyLink")}</a>`;
  accountLegalNoteEl.innerHTML = t("accountLegalNote")(termsLink, privacyLink);
  if (currentUser) {
    accountNameEl.textContent = currentUser.name;
  }
}

function closeAccountStatusPopover() {
  accountStatusEl.hidden = true;
  accountAvatarToggleEl.setAttribute("aria-expanded", "false");
}

function renderAccountWidget() {
  const loggedIn = Boolean(currentUser);
  accountSigninToggleEl.hidden = loggedIn;
  accountAvatarToggleEl.hidden = !loggedIn;
  adminToggleEl.hidden = !loggedIn || currentUser.role !== "admin";
  accountResendEl.hidden = !loggedIn || currentUser.email_verified;
  if (loggedIn) {
    accountAvatarToggleEl.textContent = currentUser.name.charAt(0).toUpperCase();
    accountNameEl.textContent = currentUser.name;
  } else {
    closeAccountStatusPopover();
  }
}

accountAvatarToggleEl.addEventListener("click", (event) => {
  event.stopPropagation();
  const willOpen = accountStatusEl.hidden;
  if (willOpen) {
    positionPopover(accountAvatarToggleEl, accountStatusEl);
  }
  accountStatusEl.hidden = !willOpen;
  accountAvatarToggleEl.setAttribute("aria-expanded", String(willOpen));
});

document.addEventListener("click", (event) => {
  if (!accountStatusEl.hidden && !accountWidgetEl.contains(event.target)) {
    closeAccountStatusPopover();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !accountStatusEl.hidden) {
    closeAccountStatusPopover();
  }
});

async function refreshCurrentUser() {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
    currentUser = res.ok ? await res.json() : null;
  } catch (err) {
    currentUser = null;
  }
  renderAccountWidget();
}

function showAccountMessage(message, isError) {
  accountMessageEl.textContent = message;
  accountMessageEl.hidden = false;
  accountMessageEl.classList.toggle("error", Boolean(isError));
}

function clearAccountMessage() {
  accountMessageEl.hidden = true;
  accountMessageEl.textContent = "";
}

function showLoginTab() {
  accountTabLoginEl.classList.add("active");
  accountTabRegisterEl.classList.remove("active");
  loginFormEl.hidden = false;
  registerFormEl.hidden = true;
  accountTitleEl.textContent = t("accountSignIn");
  clearAccountMessage();
}

function showRegisterTab() {
  accountTabRegisterEl.classList.add("active");
  accountTabLoginEl.classList.remove("active");
  registerFormEl.hidden = false;
  loginFormEl.hidden = true;
  accountTitleEl.textContent = t("accountCreateAccount");
  clearAccountMessage();
}

function openAccountPanel() {
  accountOverlayEl.hidden = false;
  showLoginTab();
  applyAccountStaticTranslations();
}

function closeAccountPanel() {
  accountOverlayEl.hidden = true;
  loginFormEl.reset();
  registerFormEl.reset();
}

accountSigninToggleEl.addEventListener("click", openAccountPanel);
accountCloseEl.addEventListener("click", closeAccountPanel);
accountOverlayEl.addEventListener("click", (event) => {
  if (event.target === accountOverlayEl) {
    closeAccountPanel();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !accountOverlayEl.hidden) {
    closeAccountPanel();
  }
});
accountTabLoginEl.addEventListener("click", showLoginTab);
accountTabRegisterEl.addEventListener("click", showRegisterTab);

async function authRequest(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
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

loginFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginFormSubmitEl.disabled = true;
  try {
    currentUser = await authRequest("/auth/login", {
      email: loginEmailInputEl.value.trim(),
      password: loginPasswordInputEl.value,
    });
    renderAccountWidget();
    closeAccountPanel();
  } catch (err) {
    showAccountMessage(err.message, true);
  } finally {
    loginFormSubmitEl.disabled = false;
  }
});

registerFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  registerFormSubmitEl.disabled = true;
  try {
    currentUser = await authRequest("/auth/register", {
      name: registerNameInputEl.value.trim(),
      email: registerEmailInputEl.value.trim(),
      password: registerPasswordInputEl.value,
    });
    renderAccountWidget();
    closeAccountPanel();
  } catch (err) {
    showAccountMessage(err.message, true);
  } finally {
    registerFormSubmitEl.disabled = false;
  }
});

accountLogoutEl.addEventListener("click", async () => {
  try {
    await authRequest("/auth/logout", {});
  } catch (err) {
    // Clear client-side state regardless — worst case the cookie
    // outlives the client's view of it until it naturally expires.
  }
  currentUser = null;
  renderAccountWidget();
});

accountResendEl.addEventListener("click", async () => {
  accountResendEl.disabled = true;
  try {
    await authRequest("/auth/resend-verification", {});
    accountResendEl.textContent = t("accountVerificationSent");
  } catch (err) {
    window.alert(err.message);
  } finally {
    setTimeout(() => {
      accountResendEl.disabled = false;
      accountResendEl.textContent = t("accountResendVerification");
    }, 4000);
  }
});

// The verification email links back here with ?verify=<token>. Strip it
// from the URL right away (so a refresh/bookmark/share doesn't resend
// the same request), then submit it and report the result.
async function handleEmailVerificationLink() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("verify");
  if (!token) {
    return;
  }
  const url = new URL(window.location.href);
  url.searchParams.delete("verify");
  window.history.replaceState({}, "", url);

  openAccountPanel();
  try {
    await authRequest("/auth/verify", { token });
    await refreshCurrentUser();
    showAccountMessage(t("accountVerifySuccess"), false);
  } catch (err) {
    showAccountMessage(err.message, true);
  }
}

applyAccountStaticTranslations();
refreshCurrentUser().then(handleEmailVerificationLink);
