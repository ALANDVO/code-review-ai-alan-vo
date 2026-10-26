"""SARIF 2.1.0 export for static analysis findings."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


# Mapping from our severity to SARIF level
SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
}

# Mapping from our category to SARIF taxonomy (CWE where applicable)
CATEGORY_TO_TAXONOMY = {
    "bug": "CWE-703",
    "security": "CWE-699",
    "performance": "CWE-1076",
    "style": "CWE-1073",
    "maintainability": "CWE-1072",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _map_severity_to_level(severity: str) -> str:
    return SEVERITY_TO_LEVEL.get(severity.lower(), "warning")


def _map_category_to_cwe(category: str) -> str:
    return CATEGORY_TO_TAXONOMY.get(category.lower(), "CWE-699")


def _build_artifact_location(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Build SARIF artifact location from finding."""
    location: Dict[str, Any] = {
        "uri": finding.get("file_path") or "unknown",
    }
    if finding.get("line_start"):
        location["startLine"] = finding["line_start"]
    if finding.get("line_end"):
        location["endLine"] = finding["line_end"]
    return location


def _build_physical_location(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Build SARIF physical location object."""
    return {
        "artifactLocation": _build_artifact_location(finding),
        "region": {
            "startLine": finding.get("line_start", 1),
            "endLine": finding.get("line_end", finding.get("line_start", 1)),
        },
    }


def _build_result(finding: Dict[str, Any], rule_index: int) -> Dict[str, Any]:
    """Build a SARIF result object from a finding."""
    severity = finding.get("severity", "medium")
    category = finding.get("category", "bug")
    rule_id = finding.get("rule_id", f"RULE-{rule_index:03d}")

    return {
        "ruleId": rule_id,
        "ruleIndex": rule_index,
        "level": _map_severity_to_level(severity),
        "message": {
            "text": finding.get("message", "No message provided"),
        },
        "locations": [_build_physical_location(finding)],
        "partialFingerprints": {
            "ruleId": rule_id,
            "filePath": finding.get("file_path", "unknown"),
            "lineStart": str(finding.get("line_start", 1)),
        },
    }


def _build_rule(finding: Dict[str, Any], rule_index: int) -> Dict[str, Any]:
    """Build a SARIF rule object from a finding."""
    rule_id = finding.get("rule_id", f"RULE-{rule_index:03d}")
    severity = finding.get("severity", "medium")
    category = finding.get("category", "bug")

    return {
        "id": rule_id,
        "name": rule_id,
        "shortDescription": {
            "text": finding.get("message", "Static analysis finding"),
        },
        "fullDescription": {
            "text": finding.get("message", "Static analysis finding"),
        },
        "defaultConfiguration": {
            "level": _map_severity_to_level(severity),
        },
        "help": {
            "text": finding.get("message", "Static analysis finding"),
            "markdown": finding.get("message", "Static analysis finding"),
        },
        "properties": {
            "category": category,
            "cwe": _map_category_to_cwe(category),
            "severity": severity,
            "tags": [category, severity],
        },
    }


def export_findings_to_sarif(
    review_id: str,
    review_title: str,
    findings: List[Dict[str, Any]],
    source_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export findings to SARIF 2.1.0 format.

    Args:
        review_id: Unique identifier for the review
        review_title: Title of the review
        findings: List of finding dictionaries from the database
        source_uri: Optional URI for the source code (e.g., git repo URL)

    Returns:
        SARIF 2.1.0 compatible JSON object
    """
    # Deduplicate rules by rule_id
    rule_map: Dict[str, Dict[str, Any]] = {}
    rule_index_map: Dict[str, int] = {}
    results = []

    for idx, finding in enumerate(findings):
        rule_id = finding.get("rule_id", f"RULE-{idx:03d}")

        if rule_id not in rule_map:
            rule_index = len(rule_map)
            rule_map[rule_id] = _build_rule(finding, rule_index)
            rule_index_map[rule_id] = rule_index
        else:
            rule_index = rule_index_map[rule_id]

        results.append(_build_result(finding, rule_index))

    rules = list(rule_map.values())

    sarif = {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Code Review AI",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/ALANDVO/code-review-ai-alan-vo",
                        "rules": rules,
                    }
                },
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "startTimeUtc": _utc_now_iso(),
                        "endTimeUtc": _utc_now_iso(),
                    }
                ],
            }
        ],
    }

    return sarif


def export_reviews_to_sarif(
    reviews: List[Dict[str, Any]],
    findings_by_review: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Export multiple reviews with their findings to a single SARIF report.

    Args:
        reviews: List of review dictionaries
        findings_by_review: Mapping from review_id to list of findings

    Returns:
        SARIF 2.1.0 compatible JSON object with multiple runs
    """
    runs = []

    for review in reviews:
        review_id = review["id"]
        findings = findings_by_review.get(review_id, [])

        # Deduplicate rules within this review
        rule_map: Dict[str, Dict[str, Any]] = {}
        rule_index_map: Dict[str, int] = {}
        results = []

        for idx, finding in enumerate(findings):
            rule_id = finding.get("rule_id", f"RULE-{idx:03d}")

            if rule_id not in rule_map:
                rule_index = len(rule_map)
                rule_map[rule_id] = _build_rule(finding, rule_index)
                rule_index_map[rule_id] = rule_index
            else:
                rule_index = rule_index_map[rule_id]

            results.append(_build_result(finding, rule_index))

        runs.append(
            {
                "tool": {
                    "driver": {
                        "name": "Code Review AI",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/ALANDVO/code-review-ai-alan-vo",
                        "rules": list(rule_map.values()),
                    }
                },
                "results": results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "startTimeUtc": _utc_now_iso(),
                        "endTimeUtc": _utc_now_iso(),
                    }
                ],
                "automationDetails": {
                    "id": review_id,
                    "description": review.get("title", "Code review"),
                },
            }
        )

    return {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA,
        "runs": runs,
    }


def export_to_sarif_file(
    sarif_data: Dict[str, Any],
    output_path: str,
) -> None:
    """Write SARIF data to a file with proper formatting."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sarif_data, f, indent=2, ensure_ascii=False)
