"""Pydantic request/response schemas for the Code Review AI API."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator
import uuid


class Language(str, Enum):
    python = "python"
    javascript = "javascript"
    typescript = "typescript"
    go = "go"
    rust = "rust"


class ReviewType(str, Enum):
    full_file = "full_file"
    diff = "diff"
    security_scan = "security_scan"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Category(str, Enum):
    bug = "bug"
    security = "security"
    performance = "performance"
    style = "style"
    maintainability = "maintainability"


# ── Requests ──────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    language: Language = Language.python
    review_type: ReviewType = ReviewType.full_file
    focus_areas: str = Field(default="all", description="Comma-separated: bug,security,performance,style,maintainability")
    code_snippet: str = Field(..., min_length=1, max_length=200_000)
    diff_text: Optional[str] = Field(default=None, max_length=200_000)
    use_llm_advisory: bool = Field(default=False)

    @field_validator("focus_areas")
    @classmethod
    def validate_focus(cls, v: str) -> str:
        valid = {"all", "bug", "security", "performance", "style", "maintainability"}
        parts = {p.strip() for p in v.split(",")}
        bad = parts - valid
        if bad:
            raise ValueError(f"Invalid focus areas: {bad}")
        return v


class EvalRunRequest(BaseModel):
    trigger: str = Field(default="manual", max_length=64)


# ── Responses ─────────────────────────────────────────────────────────────────

class FindingOut(BaseModel):
    id: str
    review_id: str
    line_number: int
    severity: str
    category: str
    cwe: Optional[str]
    message: str
    suggestion: Optional[str]
    rule_id: Optional[str]
    advisory_note: Optional[str]
    created_at: str


class ReviewOut(BaseModel):
    id: str
    title: str
    language: str
    review_type: str
    focus_areas: str
    code_snippet: str
    diff_text: Optional[str]
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: str
    created_by: str
    advisory_llm_used: int
    provider: str
    findings: Optional[List[FindingOut]] = None


class ReviewListOut(BaseModel):
    items: List[ReviewOut]
    total: int
    offset: int
    limit: int


class EvalRunOut(BaseModel):
    id: str
    trigger: str
    total_samples: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    mean_latency_ms: float
    status: str
    details: Dict[str, Any]
    created_at: str
    created_by: str


class EvalRunListOut(BaseModel):
    items: List[EvalRunOut]
    total: int


class HealthOut(BaseModel):
    status: str
    version: str
    demo_mode: bool


class StatsOut(BaseModel):
    total_reviews: int
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    languages: Dict[str, int]
    eval_runs: int


class AuditLogOut(BaseModel):
    id: str
    timestamp: str
    user_id: str
    user_role: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]


class ErrorOut(BaseModel):
    detail: str
