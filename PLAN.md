# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

review-search-and-metrics-dashboard

## Roadmap

### static-analysis-and-review-crud — Deterministic multi-language static analysis and review persistence

Status: done

Acceptance:
- Analyze Python AST and multi-language regex rules offline without requiring an LLM key
- Persist reviews, line-level CWE findings, and audit trail in SQLite with paginated retrieval

Implementation: `backend/app/main.py`, `backend/app/api/reviews.py`, `backend/app/services/analyzer.py`, `backend/app/core/database.py`, `frontend/src/pages/SubmitReviewPage.tsx`, `frontend/src/pages/ReviewDetailPage.tsx`

Tests: `backend/tests/test_main.py`

### oidc-pkce-and-rbac — Keycloak OIDC PKCE authentication and role-based access control

Status: done

Acceptance:
- Validate RS256 bearer token signature, issuer, audience, subject, and expiration on protected endpoints
- Enforce viewer, operator, and admin role hierarchy and refuse demo mode in production

Implementation: `backend/app/core/auth.py`, `backend/app/core/config.py`, `frontend/src/auth/oidc.ts`, `keycloak/realm-export.json`

Tests: `backend/tests/test_main.py`, `frontend/src/test/client.test.ts`

### offline-benchmark-evaluation — Reproducible CWE defect benchmark evaluation suite

Status: done

Acceptance:
- Evaluate the deterministic rule engine against 25 labeled synthetic samples and compute precision, recall, F1, and mean latency
- Persist and display benchmark evidence, per-sample matches, and limitations in the evaluation view

Implementation: `backend/app/services/evaluator.py`, `backend/app/services/data/evaluation.json`, `backend/app/api/evals.py`, `frontend/src/pages/EvaluationPage.tsx`

Tests: `backend/tests/test_main.py`

### llm-advisory-enrichment — Opt-in multi-provider LLM advisory enrichment with error redaction

Status: done

Acceptance:
- Support OpenAI-compatible, Anthropic, Gemini, and Ollama adapters for optional finding explanations
- Preserve deterministic findings on provider errors and redact token-shaped strings from error output

Implementation: `backend/app/services/llm_advisor.py`, `backend/app/api/reviews.py`, `frontend/src/components/FindingList.tsx`

Tests: `backend/tests/test_main.py`

### review-search-and-metrics-dashboard — Review search, severity filtering, file import, and live summary metrics

Status: done

Acceptance:
- Filter review history by search query, severity level, and language with accurate pagination counts
- Scope security_scan submissions to security rules when focus_areas is default all
- Display live /api/stats summary metrics on the review dashboard and support importing local source/diff files

Implementation: `backend/app/main.py`, `backend/app/api/reviews.py`, `backend/app/api/evals.py`, `backend/app/core/database.py`, `frontend/src/api/client.ts`, `frontend/src/pages/ReviewListPage.tsx`, `frontend/src/pages/SubmitReviewPage.tsx`

Tests: `backend/tests/test_main.py`, `frontend/src/test/client.test.ts`

### sarif-report-export — SARIF 2.1.0 report export for static analysis findings

Status: planned

Acceptance:
- Export stored review findings as SARIF 2.1.0 JSON for external code-scanning integrations

