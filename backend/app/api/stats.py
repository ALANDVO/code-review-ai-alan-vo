"""Stats and audit log API — summary metrics and audit trail."""
from __future__ import annotations

from fastapi import Request, APIRouter, Depends, Query

from app.core.auth import Principal, require_admin, require_viewer
from app.core.database import get_db
from app.models.schemas import AuditLogOut, StatsOut

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    request: Request,
    principal: Principal = Depends(require_viewer),
) -> StatsOut:
    """Return aggregate statistics for the dashboard."""
    db = request.app.state.db
    total_reviews = db.count_reviews()
    reviews = db.list_reviews(limit=10_000)

    total_findings = sum(r["total_findings"] for r in reviews)
    critical = sum(r["critical_count"] for r in reviews)
    high = sum(r["high_count"] for r in reviews)
    medium = sum(r["medium_count"] for r in reviews)
    low = sum(r["low_count"] for r in reviews)

    lang_counts: dict = {}
    for r in reviews:
        lang = r.get("language", "unknown")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    eval_runs = db.list_eval_runs(limit=1000)

    return StatsOut(
        total_reviews=total_reviews,
        total_findings=total_findings,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        languages=lang_counts,
        eval_runs=len(eval_runs),
    )


@router.get("/audit", response_model=list[AuditLogOut])
async def list_audit_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_admin),
) -> list[AuditLogOut]:
    """Return the audit log (admin only)."""
    db = request.app.state.db
    logs = db.list_audit_logs(limit=limit, offset=offset)
    return [AuditLogOut(**log) for log in logs]
