# Karabakh Atlas — Agent & Project Guidelines

This file sets project-level rules and automatically routes tasks to installed plugins and skills whenever working in this repository. All instructions below are **mandatory**.

---

## 1. Automatic Plugin & Skill Activation

- **Frontend & Modern Web Standards (`modern-web-guidance`):**
  - **MANDATORY**: Whenever editing or inspecting files under `frontend/` (HTML, CSS, JavaScript, Service Worker), automatically activate and apply the `modern-web-guidance` skill first.
  - Follow modern vanilla JS, CSS custom properties, responsive design, and progressive enhancement principles.
  - Increment the service worker cache version (`CACHE_NAME` in `frontend/sw.js`) whenever modifying core frontend assets.

- **Browser UI & Rendering Verification (`chrome-devtools`):**
  - Whenever debugging layout issues, styling defects, or verifying visual workflows, use Chrome DevTools or headless Chrome automation to test and capture screenshots.

- **Accessibility Compliance (`a11y-debugging`):**
  - Use `a11y-debugging` guidelines when adding new modal dialogs, buttons, forms, or keyboard navigation handlers.
  - Ensure all interactive elements have visible labels or `aria-label` attributes with full multilingual support via `frontend/i18n.js`.

---

## 2. Security Guardrails (AI-Era Vulnerability Prevention)

AI-generated code frequently introduces subtle vulnerabilities such as mass assignment, broken object-level authorization (IDOR), unvalidated redirects/URLs, timing leaks, and unsafe DOM sinks. Every change MUST enforce the following invariants:

### 2.1 Strict Input Validation & Mass-Assignment Defense
- **Explicit Field Whitelisting (`only_allowed_fields`):**
  - Every `POST`, `PUT`, or `PATCH` JSON endpoint MUST call `only_allowed_fields(data, ALLOWED_SET)` in `api/v1/validation.py` before reading request fields.
  - **NEVER** pass raw `request.get_json()` dictionaries directly into model constructors (`Model(**data)`) or `setattr` loops—this allows attackers to inject privileged attributes like `role="admin"`, `approved=True`, `status="approved"`, `author_id`, or `session_epoch`.
- **Safe Text & Name Validation (`require_safe_text`, `require_safe_name`):**
  - All user-submitted text fields (`join_reason`, forum posts, comments, descriptions) MUST be validated with `require_safe_text`, and person/display names with `require_safe_name`.
  - Reject HTML/script tags (`<script>`, `<iframe>`, `<svg>`, `<object>`), inline event handlers (`onload=`, `onerror=`), `javascript:`/`vbscript:`/`data:text/html` URIs, markdown images (`![alt](url)`), executable payloads/links (`.exe`, `.sh`, `.bat`, `.cmd`, `.ps1`, `.msi`, `.apk`, `.scr`, `.jar`, `.vbs`), ASCII control characters, null bytes, and Unicode bidirectional override characters (`\u202a`–`\u202e`, `\u2066`–`\u2069`).
- **Safe URL Validation (`optional_url`):**
  - Any URL field (`website`, `image_url`, `source_url`) MUST be validated with `optional_url` so only `http://` and `https://` schemes with valid hostnames are accepted (blocking `javascript:`, `data:`, `file:`, and `blob:` schemes).

### 2.2 XSS, DOM Injection & Content Security Policy (CSP)
- **Zero Unsafe DOM Sinks:**
  - **NEVER** render user-supplied or API-returned strings (`name`, `email`, `join_reason`, forum posts, place titles/descriptions, error messages) using `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write()`, `eval()`, `new Function()`, or string-interpolated HTML templates.
  - Always construct DOM nodes with `document.createElement()` and assign text via `element.textContent` or `input.value`.
  - When setting `href` or `src` attributes dynamically in `frontend/`, explicitly verify the URL starts with `https://`, `http://`, or a safe relative path (`/api/v1/...`).
- **Response Security Headers:**
  - Preserve the strict `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy` headers configured in `api/v1/app.py`. Never add `'unsafe-eval'` to `script-src`.

### 2.3 Authentication, Session & Cryptographic Hygiene
- **Never Leak Sensitive Model Fields (`public_dict` vs `to_dict`):**
  - `User.to_dict()` includes internal persistence fields (`password_hash`, `password_reset_otp`, `password_reset_expires_at`, `session_epoch`) required by `FileStorage`.
  - **NEVER** return `user.to_dict()` from an API route. Always use `user.public_dict()` or an explicit safe dictionary projection.
- **Constant-Time Secret Comparisons:**
  - Always use `secrets.compare_digest(a, b)` when comparing OTPs, tokens, or hashes (`User.verify_reset_otp`, `User.check_password`). Never use `==` on secret strings.
- **Cryptographic Randomness:**
  - Always use Python's `secrets` module (`secrets.token_hex`, `secrets.randbelow`) for generating OTPs, tokens, salts, or secret keys. Never use the non-cryptographic `random` module.
- **Approval & Session Epoch Enforcement:**
  - `get_current_user()` in `api/v1/auth_utils.py` MUST verify both `user.is_approved` and `session.get("epoch") == (user.session_epoch or 0)` so unapproved accounts and sessions predating a password reset are immediately rejected.
- **Account Enumeration Prevention:**
  - On `/auth/login`, check `user.is_approved` only **after** `user.check_password()` succeeds so attackers cannot probe whether an unapproved email exists without knowing its password.
  - On `/auth/forgot-password`, always return a generic `200 OK` message regardless of whether the email exists or is approved, while suppressing OTP generation and email dispatch for unapproved/nonexistent accounts.

### 2.4 Authorization, IDOR & Privilege Boundaries
- **Defense-in-Depth Admin Gating:**
  - All administrative endpoints must enforce `@admin_required` (`api/v1/auth_utils.py`) and be covered by `ADMIN_GATED_PREFIXES` in `api/v1/app.py` where applicable.
- **Strict Ownership & State Guards (Anti-IDOR):**
  - When a user mutates or deletes a resource (e.g., forum post deletion), verify resource ownership (`post.author_id == user.id or user.role == "admin"`).
  - Administrative account approval/rejection routes (`api/v1/views/users.py`) MUST use `_pending_user_or_404` to guarantee that already-approved members and administrator accounts cannot be modified or deleted through the pending queue.

### 2.5 CSRF, CORS & Host-Header Hardening
- **Cross-Origin Write Rejection:**
  - Keep `reject_cross_origin_writes()` in `api/v1/app.py` active for all state-changing HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`). Every write request with an `Origin` header must match `_frontend_origins` (closing the `multipart/form-data` simple-request CORS gap).
  - Never configure `CORS(..., origins="*", supports_credentials=True)`.
- **Host Header & Proxy Trust:**
  - Never trust raw `Host` or `X-Forwarded-Host` headers when building security-sensitive URLs (e.g., password reset links, canonical URLs, sitemaps)—use `KBA_PUBLIC_URL` (`_public_base_url()`).
  - Keep `ProxyFix(app.wsgi_app, x_proto=1, x_host=1)` scoped to the single trusted reverse proxy hop so attackers cannot spoof `X-Forwarded-For` to bypass rate limits.

### 2.6 File Uploads, SQL/Storage & Path Traversal
- **Magic-Byte File Verification:**
  - In `api/v1/views/images.py`, never trust client-supplied `Content-Type` headers or file extensions. Always sniff raw file magic bytes (`_sniff_content_type`) and restrict uploads to safe raster formats (`image/jpeg`, `image/png`, `image/gif`, `image/webp`).
  - **NEVER** allow active image/document formats such as `.svg`, `.html`, `.xml`, or `.swf` in uploads, as they can execute embedded JavaScript.
  - Enforce strict byte-size caps (`_MAX_BYTES = 4 * 1024 * 1024` and Flask `MAX_CONTENT_LENGTH`) before reading streams into memory.
- **SQL Injection & Safe DDL:**
  - Always use parameterized SQLAlchemy ORM queries (`session.query(...).filter(...)`). Never interpolate variables into raw SQL strings with f-strings or `%`.
  - Any schema migration helper (`_sync_missing_columns` in `models/engine/db_storage.py`) must quote table and column identifiers via `engine.dialect.identifier_preparer.quote_identifier()`.
- **Path Traversal Prevention:**
  - Never pass unvalidated user input into filesystem paths (`open()`, `os.path.join()`, `send_file()`). Always use `flask.send_from_directory()` or strict regex/UUID validation on filenames.

### 2.7 Rate Limiting & DoS Resilience
- Every authentication, registration, password-reset, image-upload, report, and forum-post endpoint MUST be protected by a `RateLimiter` in `api/v1/rate_limit.py`.
- Bound all collection queries and string inputs to prevent memory exhaustion or regex catastrophic backtracking (ReDoS).

### 2.8 Secrets, Supply Chain & Repository Hygiene
- **Zero Hardcoded Secrets:**
  - Never hardcode API keys, database URLs, session secrets, or passwords in source code, tests, or frontend files. Read all secrets from environment variables.
  - Ensure `.gitignore` always blocks `.env`, `.env.*` (except `!.env.example`), `*.pem`, `*.key`, `*.crt`, `*.pfx`, `*.p12`, `file.json`, `.kba_secret_key`, `*.db`, `*.sqlite*`, `*.dump`, and `*.log`.
- **Dependency Minimalism (Anti-Slopsquatting):**
  - Do not add unvetted or hallucinated packages to `requirements.txt`. Prefer Python's standard library and existing audited dependencies (`Flask`, `SQLAlchemy`, `Werkzeug`, `PyYAML`). Pin exact versions in `requirements.txt`.

---

## 3. Python Code Standards, Testing & Pre-Completion Audit

- **Linting:**
  - All Python files must adhere to PEP 8 / `pycodestyle` (maximum line length 79 characters, no trailing whitespace, clean blank line formatting).
  - Always verify before finishing a task:
    ```bash
    python3 -m pycodestyle api/ models/ tests/ *.py
    ```

- **Database Model Evolution:**
  - Model additions must be backward-compatible with both `FileStorage` and `DBStorage` (PostgreSQL).
  - New columns added to existing tables must be `nullable=True` or supply a safe default to allow additive schema sync (`_sync_missing_columns`).

- **Test Integrity:**
  - After changing routes, schemas, validation, or models, always run the full unit test suite and add regression tests for new security rules:
    ```bash
    KBA_TYPE_STORAGE=file KBA_ENV=test python3 -m unittest discover tests
    ```

- **Mandatory Pre-Completion Security Self-Audit:**
  Before marking any code change complete, verify:
  1. Are all new/modified request fields whitelisted with `only_allowed_fields` and validated with `require_safe_text` / `require_safe_name` / `optional_url`?
  2. Are all DOM updates using `textContent` instead of `innerHTML`?
  3. Are user objects serialized exclusively via `public_dict()`?
  4. Are authorization decorators (`@admin_required`, `@login_required`), ownership checks, and rate limiters applied to any new routes?
  5. Are zero secrets, keys, or runtime data files tracked by `git status`?
