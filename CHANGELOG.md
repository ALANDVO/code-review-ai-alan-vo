# Changelog

## [1.0.0] - 2026-10-09

## Unreleased

- Add a modular FastAPI backend and React dashboard for stored code reviews, deterministic security findings, and reproducible rule evaluation.
- Preserve the original command-line review interface.
- Isolate each application database and validate bearer-token claims against its configured identity provider.
- Add PKCE sign-in with signed ID-token validation, role controls, and memory-only access tokens.
- Add frontend build, authentication-boundary tests, container packaging, and public-runner CI.
- Correct the browser diff payload so findings use changed-file line numbers, and make the dashboard responsive on mobile.
- Verify real browser create/read/export workflows and a local OIDC protocol fixture through PKCE, signed tokens, authorized review creation, and administrator evaluation.
