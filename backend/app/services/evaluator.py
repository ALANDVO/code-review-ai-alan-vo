"""
Evaluation service — benchmarks the static analysis engine against
a curated ground-truth defect dataset to produce precision, recall and F1.

The dataset is shipped as local JSON so evaluation runs offline without
any external dependency. Data provenance: hand-crafted synthetic snippets
representing representative defect patterns from CWE taxonomy categories.
Each sample has known-positive or known-negative labels per rule family.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.analyzer import analyze_code, Finding

__all__ = ["run_evaluation", "EVAL_DATASET"]


@dataclass
class EvalSample:
    sample_id: str
    language: str
    description: str
    code: str
    expected_rule_ids: List[str]       # rules that MUST fire
    forbidden_rule_ids: List[str] = field(default_factory=list)  # rules that MUST NOT fire


# ── Ground-truth benchmark dataset ────────────────────────────────────────────
# 25 labeled samples covering security, bugs, performance, style, maintainability.

from pathlib import Path
import json

EVAL_DATASET = [EvalSample(**sample) for sample in json.loads((Path(__file__).parent / 'data/evaluation.json').read_text())]


# ── Evaluation logic ───────────────────────────────────────────────────────────

@dataclass
class SampleResult:
    sample_id: str
    description: str
    expected: List[str]
    fired: List[str]
    tp: int
    fp: int
    fn: int
    latency_ms: float
    pass_: bool


def _evaluate_sample(sample: EvalSample) -> SampleResult:
    t0 = time.perf_counter()
    findings, _ = analyze_code(sample.code, sample.language, "all")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    fired_ids = {f.rule_id for f in findings}
    expected_ids = set(sample.expected_rule_ids)
    forbidden_ids = set(sample.forbidden_rule_ids)

    tp = len(expected_ids & fired_ids)
    fn = len(expected_ids - fired_ids)
    fp = len(fired_ids - expected_ids)  # fired but not expected

    # False positive: fired a forbidden rule
    fp_forbidden = len(forbidden_ids & fired_ids)
    fp += fp_forbidden

    pass_ = (fn == 0 and fp_forbidden == 0)

    return SampleResult(
        sample_id=sample.sample_id,
        description=sample.description,
        expected=list(expected_ids),
        fired=list(fired_ids),
        tp=tp,
        fp=fp,
        fn=fn,
        latency_ms=elapsed_ms,
        pass_=pass_,
    )


def run_evaluation(trigger: str = "manual", created_by: str = "system") -> Dict[str, Any]:
    """
    Run the full evaluation suite and return a structured result dict
    suitable for storing in the eval_runs table.
    """
    results: List[SampleResult] = []
    for sample in EVAL_DATASET:
        results.append(_evaluate_sample(sample))

    total = len(results)
    tp_total = sum(r.tp for r in results)
    fp_total = sum(r.fp for r in results)
    fn_total = sum(r.fn for r in results)
    mean_latency = sum(r.latency_ms for r in results) / total if total else 0.0

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    passed = sum(1 for r in results if r.pass_)

    details = {
        "samples": [
            {
                "sample_id": r.sample_id,
                "description": r.description,
                "expected_rules": r.expected,
                "fired_rules": r.fired,
                "tp": r.tp,
                "fp": r.fp,
                "fn": r.fn,
                "latency_ms": round(r.latency_ms, 2),
                "pass": r.pass_,
            }
            for r in results
        ],
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "data_provenance": (
            "Synthetic hand-labeled benchmark derived from CWE taxonomy categories. "
            f"{total} samples, {len([s for s in EVAL_DATASET if s.expected_rule_ids])} positive, "
            f"{len([s for s in EVAL_DATASET if not s.expected_rule_ids])} negative."
        ),
        "baseline": "Deterministic rule engine without LLM. Precision/Recall measured against labeled ground truth.",
        "limitations": (
            "Dataset is synthetic; real-world code may contain obfuscated patterns "
            "or context-dependent issues not captured by single-file static analysis. "
            "LLM advisory notes are not evaluated here."
        ),
    }

    return {
        "id": str(uuid.uuid4()),
        "trigger": trigger,
        "total_samples": total,
        "true_positives": tp_total,
        "false_positives": fp_total,
        "false_negatives": fn_total,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "mean_latency_ms": round(mean_latency, 2),
        "status": "completed",
        "details": details,
        "created_by": created_by,
    }
