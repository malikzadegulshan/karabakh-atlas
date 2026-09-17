# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/malikzadegulshan/karabakh-atlas/security/advisories/new)
rather than opening a public issue. This lets a fix land before the
details are public.

Include what you can:

- What the issue is and where it lives (endpoint, file, feature)
- Steps to reproduce, or a proof of concept
- What an attacker could actually do with it (impact)

This is a small, independently maintained project — there's no bug
bounty and no guaranteed response time, but reports are read and
taken seriously. A fix will be prioritized based on real-world impact.

## Scope

This covers the Karabakh Atlas application itself (the Flask API in
`api/`, models in `models/`, and the frontend in `frontend/`). Issues
with third-party services it depends on (Render, Resend, Esri/CARTO
tile providers, etc.) should go to those providers directly.

## `security.txt`

Machine-readable contact info following
[RFC 9116](https://www.rfc-editor.org/rfc/rfc9116) is published at
[`/.well-known/security.txt`](https://karabakh-atlas-frontend.onrender.com/.well-known/security.txt).
