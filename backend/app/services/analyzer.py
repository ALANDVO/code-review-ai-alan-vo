"""
Static analysis engine for code review AI.

Deterministic rule-based analysis that works offline without any LLM key.
Covers: Python, JavaScript/TypeScript, Go, Rust with security, bug, performance,
style and maintainability rules mapped to CWE taxonomy where applicable.
"""
from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Tuple

__all__ = ["Finding", "analyze_code", "analyze_diff", "SUPPORTED_LANGUAGES"]

SUPPORTED_LANGUAGES = {"python", "javascript", "typescript", "go", "rust"}


@dataclass
class Finding:
    line_number: int
    severity: str          # critical | high | medium | low
    category: str          # bug | security | performance | style | maintainability
    message: str
    suggestion: str = ""
    rule_id: str = ""
    cwe: Optional[str] = None
    advisory_note: Optional[str] = None



# ── Rule definitions ───────────────────────────────────────────────────────────

@dataclass
class RegexRule:
    rule_id: str
    pattern: re.Pattern
    severity: str
    category: str
    message: str
    suggestion: str
    cwe: Optional[str] = None
    # Languages this rule applies to; empty = all
    languages: tuple = ()
    # Pattern that, if matched on same line, suppresses the rule
    suppress_if: Optional[re.Pattern] = None


def _r(rule_id, pat, sev, cat, msg, sug, cwe=None, langs=(), suppress=None):
    return RegexRule(
        rule_id=rule_id,
        pattern=re.compile(pat, re.IGNORECASE),
        severity=sev,
        category=cat,
        message=msg,
        suggestion=sug,
        cwe=cwe,
        languages=langs,
        suppress_if=re.compile(suppress, re.IGNORECASE) if suppress else None,
    )


from pathlib import Path
import json

REGEX_RULES = [_r(**rule) for rule in json.loads((Path(__file__).parent / 'data/rules.json').read_text())]


# ── Python AST analysis ────────────────────────────────────────────────────────

class _PythonASTVisitor(ast.NodeVisitor):
    """Deep Python analysis using AST: finds more precise issues than regex."""

    def __init__(self, source_lines: List[str]) -> None:
        self.findings: List[Finding] = []
        self._lines = source_lines
        self._func_stack: List[ast.FunctionDef] = []

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _add(self, node: ast.AST, **kw) -> None:
        self.findings.append(Finding(line_number=node.lineno, **kw))  # type: ignore[attr-defined]

    # ── Visitors ───────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._func_stack.append(node)
        # Complexity: count branches
        branches = sum(
            1 for n in ast.walk(node)
            if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Assert))
        )
        if branches > 12:
            self._add(node, severity="medium", category="maintainability",
                      rule_id="AST001",
                      message=f"Function '{node.name}' has high cyclomatic complexity ({branches} branches). "
                              "Complex functions are hard to test and reason about.",
                      suggestion="Extract sub-functions for each distinct responsibility.")

        # Missing return type annotation
        if node.returns is None and node.name not in ("__init__", "__new__"):
            self._add(node, severity="low", category="maintainability",
                      rule_id="AST002",
                      message=f"Function '{node.name}' lacks a return type annotation.",
                      suggestion="Add an explicit return type: def fn(...) -> ReturnType:")

        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            if handler.type is None:
                self._add(handler, severity="medium", category="bug",
                          rule_id="AST003",
                          message="Bare except clause catches BaseException including SystemExit.",
                          suggestion="Specify the exception type: except ValueError as e:",
                          cwe="CWE-390")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Detect mutable default argument construction
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("format", "format_map"):
            pass  # Not an issue by itself
        self.generic_visit(node)

    def visit_FunctionDef_defaults(self, node: ast.FunctionDef) -> None:
        for default in node.args.defaults + node.args.kw_defaults:
            if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add(node, severity="high", category="bug",
                          rule_id="AST004",
                          message=f"Function '{node.name}' has a mutable default argument. "
                                  "The same object is shared across all calls.",
                          suggestion="Use None as default and initialise inside the function body.",
                          cwe="CWE-686")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in ("telnetlib", "ftplib") and alias.asname is None:
                self._add(node, severity="medium", category="security",
                          rule_id="AST005",
                          message=f"Importing '{alias.name}' which uses unencrypted protocols.",
                          suggestion="Use SSH/SFTP/HTTPS equivalents.",
                          cwe="CWE-311")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Detect mutable default argument via assignment in class body
        self.generic_visit(node)

    def visit_FunctionDef_check_defaults(self, node: ast.FunctionDef) -> None:
        self.visit_FunctionDef_defaults(node)


def _analyze_python_ast(source: str, source_lines: List[str]) -> List[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [Finding(
            line_number=exc.lineno or 1,
            severity="critical",
            category="bug",
            message=f"Python syntax error: {exc.msg}",
            suggestion="Fix the syntax error before proceeding.",
            rule_id="SYN001",
        )]

    visitor = _PythonASTVisitor(source_lines)
    # Check mutable defaults before main visit
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor.visit_FunctionDef_check_defaults(node)

    visitor.visit(tree)
    return visitor.findings


# ── Diff analysis ──────────────────────────────────────────────────────────────

def _extract_added_lines(diff_text: str) -> List[Tuple[int, str]]:
    """Return (line_number_in_diff, text) for added lines in a unified diff."""
    added: List[Tuple[int, str]] = []
    current_line = 0
    for i, line in enumerate(diff_text.splitlines(), start=1):
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                current_line = int(m.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            added.append((current_line, line[1:]))
        elif not line.startswith("-"):
            current_line += 1
    return added


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_code(
    source: str,
    language: str,
    focus_areas: str = "all",
) -> Tuple[List[Finding], float]:
    """
    Run deterministic static analysis on source code.

    Returns (findings, elapsed_ms).
    """
    t0 = time.perf_counter()
    lang = language.lower()
    focus = {a.strip() for a in focus_areas.split(",")}
    include_all = "all" in focus

    source_lines = source.splitlines()
    findings: List[Finding] = []

    # Regex rules
    for rule in REGEX_RULES:
        if rule.languages and lang not in rule.languages:
            continue
        if not include_all and rule.category not in focus:
            continue
        for lineno, line in enumerate(source_lines, start=1):
            if rule.pattern.search(line):
                if rule.suppress_if and rule.suppress_if.search(line):
                    continue
                findings.append(Finding(
                    line_number=lineno,
                    severity=rule.severity,
                    category=rule.category,
                    message=rule.message,
                    suggestion=rule.suggestion,
                    rule_id=rule.rule_id,
                    cwe=rule.cwe,
                ))

    # Deep Python AST analysis
    if lang == "python" and (include_all or "bug" in focus or "maintainability" in focus):
        ast_findings = _analyze_python_ast(source, source_lines)
        for f in ast_findings:
            if include_all or f.category in focus:
                findings.append(f)

    # Deduplicate: same rule on same line
    seen: set = set()
    unique: List[Finding] = []
    for f in findings:
        key = (f.rule_id, f.line_number)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return unique, elapsed_ms


def analyze_diff(
    diff_text: str,
    language: str,
    focus_areas: str = "all",
) -> Tuple[List[Finding], float]:
    """
    Analyze only the added lines in a unified diff.

    Returns (findings, elapsed_ms) with line_number relative to diff hunk.
    """
    added_lines = _extract_added_lines(diff_text)
    if not added_lines:
        return [], 0.0

    # Reconstruct a "source" for analysis using only added lines
    synthetic_source = "\n".join(text for _, text in added_lines)
    raw_findings, elapsed_ms = analyze_code(synthetic_source, language, focus_areas)

    # Map findings back to diff line numbers
    mapped: List[Finding] = []
    for f in raw_findings:
        idx = f.line_number - 1
        if 0 <= idx < len(added_lines):
            original_lineno, _ = added_lines[idx]
        else:
            original_lineno = f.line_number
        mapped.append(Finding(
            line_number=original_lineno,
            severity=f.severity,
            category=f.category,
            message=f.message,
            suggestion=f.suggestion,
            rule_id=f.rule_id,
            cwe=f.cwe,
        ))

    return mapped, elapsed_ms
