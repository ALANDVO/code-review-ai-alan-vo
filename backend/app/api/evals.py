"""Evaluation API — run and retrieve benchmark evaluation results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.auth import Principal, require_admin, require_viewer
from app.core.database import get_db
from app.models.schemas import EvalRunListOut, EvalRunOut, EvalRunRequest
from app.services.evaluator import run_evaluation

router = APIRouter(prefix="/api/evals", tags=["evaluation"])


@router.post("", response_model=EvalRunOut, status_code=status.HTTP_201_CREATED)
async def trigger_evaluation(
    body: EvalRunRequest,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> EvalRunOut:
    """Run the benchmark evaluation suite. Requires admin role."""
    db = request.app.state.db
    result = run_evaluation(trigger=body.trigger, created_by=principal.user_id)
    db.insert_eval_run(result)
    db.insert_audit_log(
        user_id=principal.user_id,
        user_role=principal.role.value,
        action="trigger_eval",
        resource_type="eval_run",
        resource_id=result["id"],
        details=f"f1={result['f1_score']} precision={result['precision']} recall={result['recall']}",
        ip_address=request.client.host if request.client else None,
    )
    stored = db.get_eval_run(result["id"])
    return EvalRunOut(**stored)


@router.get("", response_model=EvalRunListOut)
async def list_eval_runs(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_viewer),
) -> EvalRunListOut:
    db = request.app.state.db
    items = db.list_eval_runs(limit=limit, offset=offset)
    return EvalRunListOut(items=[EvalRunOut(**r) for r in items], total=len(items))


@router.get("/{run_id}", response_model=EvalRunOut)
async def get_eval_run(
    request: Request,
    run_id: str,
    principal: Principal = Depends(require_viewer),
) -> EvalRunOut:
    db = request.app.state.db
    run = db.get_eval_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found.")
    return EvalRunOut(**run)
