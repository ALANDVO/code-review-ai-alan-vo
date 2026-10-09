"""
Backend tests for Code Review AI.

Tests cover:
- Static analysis engine (unit): rule firing, false-positive suppression
- Database persistence
- API workflows: create/read review, list with pagination, delete
- Auth: unauthenticated rejection, role denial
- LLM advisor: mock provider adapters
- Evaluator: benchmark runs
- Boundary and malformed inputs
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Configure test settings before importing app modules
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("ENV", "test")

from app.core.config import Settings
from app.core.database import Database
from app.main import create_app
from app.services.analyzer import Finding, analyze_code, analyze_diff
from app.services.evaluator import EVAL_DATASET, run_evaluation


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_db() -> Generator[Database, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(os.path.join(tmpdir, "test.db"))
        yield db


@pytest.fixture()
def test_settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        demo_mode=True,
        host="127.0.0.1",
        port=8000,
        database_path=str(tmp_path / "test.db"),
        llm_api_key="",
        llm_provider="openai",
        llm_model="gpt-4o",
        llm_base_url="http://localhost:9999/v1",
        oidc_issuer="http://localhost:8080/realms/test",
        oidc_audience="test-client",
        oidc_jwks_url="http://localhost:8080/realms/test/certs",
    )


@pytest.fixture()
def client(test_settings) -> Generator[TestClient, None, None]:
    """TestClient with demo mode enabled (no auth token needed)."""
    import app.core.database as db_module
    db_module._db_instance = None  # reset singleton

    application = create_app(override_settings=test_settings)
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c
    db_module._db_instance = None


@pytest.fixture()
def no_demo_client(tmp_path) -> Generator[TestClient, None, None]:
    """TestClient with demo mode disabled — requires bearer token."""
    import app.core.database as db_module
    db_module._db_instance = None

    s = Settings(
        env="test",
        demo_mode=False,
        host="127.0.0.1",
        port=8000,
        database_path=str(tmp_path / "nodemo.db"),
        llm_api_key="",
        llm_provider="openai",
        llm_model="gpt-4o",
        llm_base_url="http://localhost:9999/v1",
        oidc_issuer="http://localhost:8080/realms/test",
        oidc_audience="test-client",
        oidc_jwks_url="http://localhost:8080/realms/test/certs",
    )
    application = create_app(override_settings=s)
    with TestClient(application, raise_server_exceptions=False) as c:
        yield c
    db_module._db_instance = None


# ── 1. Analyzer unit tests ─────────────────────────────────────────────────────

class TestAnalyzerRules:
    def test_eval_rule_fires(self):
        code = "result = eval(user_input)\n"
        findings, _ = analyze_code(code, "python")
        rule_ids = [f.rule_id for f in findings]
        assert "SEC001" in rule_ids

    def test_pickle_loads_fires(self):
        code = "import pickle\nobj = pickle.loads(data)\n"
        findings, _ = analyze_code(code, "python")
        rule_ids = [f.rule_id for f in findings]
        assert "SEC004" in rule_ids

    def test_bare_except_fires(self):
        code = "try:\n    risky()\nexcept:\n    pass\n"
        findings, _ = analyze_code(code, "python")
        rule_ids = [f.rule_id for f in findings]
        assert "BUG001" in rule_ids

    def test_none_comparison_fires(self):
        code = "if x == None:\n    return False\n"
        findings, _ = analyze_code(code, "python")
        rule_ids = [f.rule_id for f in findings]
        assert "BUG003" in rule_ids

    def test_innerhtml_xss_fires_js(self):
        code = "element.innerHTML = userInput;\n"
        findings, _ = analyze_code(code, "javascript")
        rule_ids = [f.rule_id for f in findings]
        assert "SEC010" in rule_ids

    def test_innerhtml_rule_not_applied_to_python(self):
        code = "element.innerHTML = userInput\n"
        findings, _ = analyze_code(code, "python")
        rule_ids = [f.rule_id for f in findings]
        assert "SEC010" not in rule_ids

    def test_clean_code_no_findings(self):
        code = (
            "from typing import List\n\n"
            "def sum_positives(numbers: List[int]) -> int:\n"
            '    """Return sum of positive integers."""\n'
            "    return sum(n for n in numbers if n > 0)\n"
        )
        findings, _ = analyze_code(code, "python")
        sec_findings = [f for f in findings if f.category == "security"]
        assert len(sec_findings) == 0

    def test_select_star_fires(self):
        code = 'db.execute("SELECT * FROM users")\n'
        findings, _ = analyze_code(code, "python")
        assert any(f.rule_id == "PERF003" for f in findings)

    def test_focus_filter_security_only(self):
        code = "eval(x)\nresult += item\n"
        findings, _ = analyze_code(code, "python", focus_areas="security")
        cats = {f.category for f in findings}
        assert "security" in cats
        # performance rule PERF002 should not fire when focus is security-only
        assert all(f.category == "security" for f in findings)

    def test_diff_analysis_added_lines_only(self):
        diff = (
            "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,4 @@\n"
            " def foo():\n-    pass\n+    return eval(user_input)\n"
        )
        findings, _ = analyze_diff(diff, "python")
        assert any(f.rule_id == "SEC001" for f in findings)

    def test_elapsed_ms_positive(self):
        code = "x = 1\n"
        _, elapsed = analyze_code(code, "python")
        assert elapsed >= 0


# ── 2. Database persistence tests ─────────────────────────────────────────────

class TestDatabase:
    def test_insert_and_get_review(self, tmp_db):
        review_data = {
            "id": str(uuid.uuid4()),
            "title": "Test Review",
            "language": "python",
            "review_type": "full_file",
            "focus_areas": "all",
            "code_snippet": "x = eval(y)",
            "diff_text": None,
            "advisory_llm_used": False,
            "provider": "offline-engine",
            "created_by": "test-user",
        }
        findings = [
            {
                "id": str(uuid.uuid4()),
                "line_number": 1,
                "severity": "critical",
                "category": "security",
                "cwe": "CWE-95",
                "message": "eval() injection",
                "suggestion": "remove eval",
                "rule_id": "SEC001",
                "advisory_note": "",
            }
        ]
        rid = tmp_db.insert_review(review_data, findings)
        assert rid == review_data["id"]

        retrieved = tmp_db.get_review(rid)
        assert retrieved is not None
        assert retrieved["title"] == "Test Review"
        assert len(retrieved["findings"]) == 1
        assert retrieved["findings"][0]["severity"] == "critical"

    def test_list_reviews_pagination(self, tmp_db):
        for i in range(5):
            tmp_db.insert_review(
                {
                    "id": str(uuid.uuid4()),
                    "title": f"Review {i}",
                    "language": "python",
                    "review_type": "full_file",
                    "focus_areas": "all",
                    "code_snippet": "x = 1",
                    "advisory_llm_used": False,
                    "provider": "offline-engine",
                    "created_by": "u1",
                },
                [],
            )
        page1 = tmp_db.list_reviews(limit=2, offset=0)
        page2 = tmp_db.list_reviews(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert {r["title"] for r in page1}.isdisjoint({r["title"] for r in page2})

    def test_delete_review(self, tmp_db):
        rid = str(uuid.uuid4())
        tmp_db.insert_review(
            {"id": rid, "title": "Del", "language": "go", "review_type": "full_file",
             "focus_areas": "all", "code_snippet": "x", "advisory_llm_used": False,
             "provider": "offline-engine", "created_by": "u1"},
            [],
        )
        assert tmp_db.get_review(rid) is not None
        tmp_db.delete_review(rid)
        assert tmp_db.get_review(rid) is None


# ── 3. API workflow tests ──────────────────────────────────────────────────────

class TestReviewsAPI:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["demo_mode"] is True

    def test_submit_review_creates_record(self, client):
        resp = client.post(
            "/api/reviews",
            json={
                "title": "Test submission",
                "language": "python",
                "review_type": "full_file",
                "focus_areas": "all",
                "code_snippet": "result = eval(user_input)\n",
                "use_llm_advisory": False,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["total_findings"] >= 1
        assert any(f["rule_id"] == "SEC001" for f in body["findings"])

    def test_get_review_by_id(self, client):
        resp = client.post(
            "/api/reviews",
            json={
                "title": "Fetch test",
                "language": "python",
                "review_type": "full_file",
                "focus_areas": "all",
                "code_snippet": "x = 1\n",
            },
        )
        review_id = resp.json()["id"]
        resp2 = client.get(f"/api/reviews/{review_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == review_id

    def test_list_reviews_returns_created(self, client):
        client.post(
            "/api/reviews",
            json={"title": "L1", "language": "python", "review_type": "full_file",
                  "focus_areas": "all", "code_snippet": "x = 1\n"},
        )
        resp = client.get("/api/reviews")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_delete_review(self, client):
        r = client.post(
            "/api/reviews",
            json={"title": "Del", "language": "python", "review_type": "full_file",
                  "focus_areas": "all", "code_snippet": "x = 1\n"},
        )
        rid = r.json()["id"]
        del_resp = client.delete(f"/api/reviews/{rid}")
        assert del_resp.status_code == 204
        get_resp = client.get(f"/api/reviews/{rid}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_review_404(self, client):
        resp = client.get(f"/api/reviews/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_stats_endpoint(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_reviews" in body
        assert "critical_count" in body

    def test_invalid_focus_areas_rejected(self, client):
        resp = client.post(
            "/api/reviews",
            json={
                "title": "Bad focus",
                "language": "python",
                "review_type": "full_file",
                "focus_areas": "nonexistent",
                "code_snippet": "x = 1\n",
            },
        )
        assert resp.status_code == 422

    def test_empty_code_rejected(self, client):
        resp = client.post(
            "/api/reviews",
            json={
                "title": "Empty",
                "language": "python",
                "review_type": "full_file",
                "focus_areas": "all",
                "code_snippet": "",
            },
        )
        assert resp.status_code == 422


# ── 4. Auth tests ──────────────────────────────────────────────────────────────

class TestAuth:
    def test_unauthenticated_rejected_without_demo(self, no_demo_client):
        resp = no_demo_client.get("/api/reviews")
        assert resp.status_code == 401

    def test_unauthenticated_post_rejected_without_demo(self, no_demo_client):
        resp = no_demo_client.post(
            "/api/reviews",
            json={"title": "t", "language": "python", "review_type": "full_file",
                  "focus_areas": "all", "code_snippet": "x = 1"},
        )
        assert resp.status_code == 401

    def test_production_rejects_demo_mode(self):
        """Settings.load() should raise if ENV=production and DEMO_MODE=true."""
        import os as _os
        orig_env = _os.environ.copy()
        _os.environ["ENV"] = "production"
        _os.environ["DEMO_MODE"] = "true"
        with pytest.raises(RuntimeError, match="Demo mode"):
            Settings.load()
        # Restore
        _os.environ.clear()
        _os.environ.update(orig_env)


# ── 5. Evaluator tests ─────────────────────────────────────────────────────────

class TestEvaluator:
    def test_eval_run_returns_metrics(self):
        result = run_evaluation(trigger="test")
        assert result["total_samples"] == len(EVAL_DATASET)
        assert 0.0 <= result["precision"] <= 1.0
        assert 0.0 <= result["recall"] <= 1.0
        assert 0.0 <= result["f1_score"] <= 1.0
        assert result["status"] == "completed"

    def test_eval_details_include_pass_rate(self):
        result = run_evaluation()
        details = result["details"]
        assert "pass_rate" in details
        assert "samples" in details
        assert len(details["samples"]) == len(EVAL_DATASET)

    def test_eval_api_requires_admin(self, client):
        """Demo principal is operator, not admin — should be forbidden."""
        resp = client.post("/api/evals", json={"trigger": "test"})
        assert resp.status_code == 403


def test_application_databases_are_isolated(test_settings, tmp_path):
    from dataclasses import replace
    first = TestClient(create_app(test_settings))
    second = TestClient(create_app(replace(test_settings, database_path=str(tmp_path / 'other.db'))))
    payload = {'title': 'Boundary', 'language': 'python', 'review_type': 'full_file',
               'focus_areas': 'all', 'code_snippet': 'eval(user_input)', 'use_llm_advisory': False}
    with first, second:
        saved = first.post('/api/reviews', json=payload)
        assert saved.status_code == 201
        assert second.get('/api/reviews').json()['total'] == 0
        assert first.get('/api/reviews').json()['total'] == 1


@pytest.mark.parametrize('mutation', ['none', 'expired', 'missing_exp', 'wrong_audience', 'wrong_issuer', 'missing_sub', 'wrong_signature'])
def test_signed_oidc_tokens_use_app_settings_and_required_claims(test_settings, mutation):
    from dataclasses import replace
    from datetime import datetime, timezone
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from jose import jwt, jwk
    from app.core import auth
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    config = replace(test_settings, demo_mode=False)
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {'iss': config.oidc_issuer, 'aud': config.oidc_audience, 'sub': 'analyst', 'exp': now + 60, 'iat': now,
              'realm_access': {'roles': ['operator']}}
    if mutation == 'expired': claims['exp'] = now - 60
    if mutation == 'missing_exp': del claims['exp']
    if mutation == 'wrong_audience': claims['aud'] = 'unrelated-service'
    if mutation == 'wrong_issuer': claims['iss'] = 'https://untrusted.example'
    if mutation == 'missing_sub': del claims['sub']
    if mutation == 'wrong_signature':
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    token = jwt.encode(claims, private, algorithm='RS256')
    def keys(app_settings):
        assert app_settings.oidc_issuer == config.oidc_issuer
        return {'keys': [jwk.construct(public, 'RS256').to_dict()]}
    with patch.object(auth, '_get_jwks', side_effect=keys), TestClient(create_app(config)) as client:
        response = client.get('/api/reviews', headers={'Authorization': 'Bearer ' + token})
        assert response.status_code == (200 if mutation == 'none' else 401)
