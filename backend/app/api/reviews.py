"""Reviews API — submit code for analysis and retrieve past reviews."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.auth import Principal, require_operator, require_viewer
from app.core.database import get_db
from app.models.schemas import (
    ReviewListOut,
    ReviewOut,
    ReviewRequest,
    FindingOut,
)
from app.services.analyzer import analyze_code, analyze_diff
from app.services.llm_advisor import enrich_with_advisory
from datetime import datetime, timezone

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _findings_to_dicts(findings, review_id: str, now: str) -> list:
    return [
        {
            "id": str(uuid.uuid4()),
            "review_id": review_id,
            "line_number": f.line_number,
            "severity": f.severity,
            "category": f.category,
            "cwe": f.cwe,
            "message": f.message,
            "suggestion": f.suggestion or "",
            "rule_id": f.rule_id or "",
            "advisory_note": getattr(f, "advisory_note", "") or "",
            "created_at": now,
        }
        for f in findings
    ]


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def submit_review(
    body: ReviewRequest,
    request: Request,
    principal: Principal = Depends(require_operator),
) -> ReviewOut:
    """Submit code or diff for static analysis. LLM advisory is opt-in."""
    db = request.app.state.db
    now = _utc_now()
    review_id = str(uuid.uuid4())

    # Run deterministic analysis
    if body.review_type == "diff" and body.diff_text:
        findings, latency_ms = analyze_diff(body.diff_text, body.language.value, body.focus_areas)
        code_for_review = body.diff_text
    else:
        findings, latency_ms = analyze_code(body.code_snippet, body.language.value, body.focus_areas)
        code_for_review = body.code_snippet

    provider = "offline-engine"
    llm_used = False
    llm_error: Optional[str] = None

    if body.use_llm_advisory and findings:
        try:
            findings, provider = enrich_with_advisory(findings, code_for_review, body.language.value, request.app.state.settings)
            llm_used = provider != "offline-engine"
        except ValueError as exc:
            llm_error = str(exc)
            provider = "offline-engine"

    findings_dicts = _findings_to_dicts(findings, review_id, now)

    review_data = {
        "id": review_id,
        "title": body.title,
        "language": body.language.value,
        "review_type": body.review_type.value,
        "focus_areas": body.focus_areas,
        "code_snippet": body.code_snippet[:50_000],
        "diff_text": body.diff_text,
        "advisory_llm_used": llm_used,
        "provider": provider,
        "created_at": now,
        "created_by": principal.user_id,
    }

    db.insert_review(review_data, findings_dicts)
    db.insert_audit_log(
        user_id=principal.user_id,
        user_role=principal.role.value,
        action="submit_review",
        resource_type="review",
        resource_id=review_id,
        details=f"language={body.language.value} findings={len(findings)} llm={llm_used}",
        ip_address=request.client.host if request.client else None,
    )

    full = db.get_review(review_id)
    if not full:
        raise HTTPException(status_code=500, detail="Review storage failed.")

    if llm_error:
        # Return result but surface the advisory failure via a custom header
        # (don't fail the whole request — deterministic results are complete)
        full["_llm_error"] = llm_error

    findings_out = [FindingOut(**f) for f in full.pop("findings", [])]
    full.pop("_llm_error", None)
    return ReviewOut(**full, findings=findings_out)


@router.get("", response_model=ReviewListOut)
async def list_reviews(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    language: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_viewer),
) -> ReviewListOut:
    db = request.app.state.db
    items = db.list_reviews(limit=limit, offset=offset, language=language)
    total = db.count_reviews(language=language)
    return ReviewListOut(
        items=[ReviewOut(**r) for r in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(
    request: Request,
    review_id: str,
    principal: Principal = Depends(require_viewer),
) -> ReviewOut:
    db = request.app.state.db
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    findings = [FindingOut(**f) for f in review.pop("findings", [])]
    return ReviewOut(**review, findings=findings)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_review(
    review_id: str,
    request: Request,
    principal: Principal = Depends(require_operator),
):
    db = request.app.state.db
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    db.delete_review(review_id)
    db.insert_audit_log(
        user_id=principal.user_id,
        user_role=principal.role.value,
        action="delete_review",
        resource_type="review",
        resource_id=review_id,
        ip_address=request.client.host if request.client else None,
    )
