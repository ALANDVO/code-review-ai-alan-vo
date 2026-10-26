# Changelog

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

### Added
- SARIF 2.1.0 export for static analysis findings (`GET /api/reviews/{id}/sarif` and `GET /api/reviews/sarif`) with filtering by language, search, and severity.
- SARIF export service (`backend/app/services/sarif_export.py`) with proper rule deduplication, CWE mapping, and SARIF schema validation.
- Backend tests for single-review export, multi-review export, and filtered exports.
## [1.0.0] - 2026-10-09

## Unreleased

- Add parameterized `search` and `severity` filters to `GET /api/reviews` and wire live `/api/stats` summary metrics and filter controls into the review history dashboard.
- Add local source/diff file import to the review submission form and scope `security_scan` submissions to security rules by default.
- Load product version dynamically from `VERSION` metadata in `backend/app/main.py` and return total persisted benchmark count in `GET /api/evals`.
- Add backend tests for `security_scan` scoping, search/severity filtering, LLM advisor adapters/error redaction, and admin evaluation pagination, plus frontend tests for signed OIDC PKCE callback verification and dashboard filtering.
- Add incremental roadmap tracking (`feature-plan.json`, `PLAN.md`, `STATUS.md`).
- Add a modular FastAPI backend and React dashboard for stored code reviews, deterministic security findings, and reproducible rule evaluation.
- Preserve the original command-line review interface.
- Isolate each application database and validate bearer-token claims against its configured identity provider.
- Add PKCE sign-in with signed ID-token validation, role controls, and memory-only access tokens.
- Add frontend build, authentication-boundary tests, container packaging, and public-runner CI.
- Correct the browser diff payload so findings use changed-file line numbers, and make the dashboard responsive on mobile.
- Verify real browser create/read/export workflows and a local OIDC protocol fixture through PKCE, signed tokens, authorized review creation, and administrator evaluation.
