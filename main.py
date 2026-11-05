#!/usr/bin/env python3
# code-review-ai — AI code review assistant that analyzes diffs or files for bugs, security issues, style problems, and performance pitfalls, generating line-by-line review comments for Python, JS, Go, and Rust.
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import LLM

# Import static analyzer from backend
try:
    from backend.app.services.analyzer import analyze_code, analyze_diff, Finding
    STATIC_ANALYZER_AVAILABLE = True
except ImportError:
    STATIC_ANALYZER_AVAILABLE = False

def _detect_lang(filepath, explicit=None):
    if explicit:
        return explicit
    if not filepath:
        return "python"
    ext = os.path.splitext(filepath)[1].lower()
    return {".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "javascript", ".tsx": "typescript", ".go": "go", ".rs": "rust"}.get(ext, "python")

def _read_code(args):
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    with open(args.file) as f:
        return f.read()

def _findings_to_dicts(findings, elapsed_ms):
    """Convert analyzer Finding objects to dicts for _report."""
    return [
        {
            "line": f.line_number,
            "severity": f.severity,
            "category": f.category,
            "message": f.message,
            "suggestion": f.suggestion,
            "rule_id": f.rule_id,
            "cwe": f.cwe,
        }
        for f in findings
    ], elapsed_ms

def review(args):
    """Full-file code review with LLM analysis."""
    llm = LLM()
    code = _read_code(args)
    lang = _detect_lang(getattr(args, "file", ""), args.lang)
    focus = (args.focus or "all").split(",")
    lines = code.split("\n")
    print(f"Reviewing {len(lines)} lines ({lang}), focus: {focus}\n")

    # Chunk for very large files
    chunks, chunk_size = [], 250
    for i in range(0, len(lines), chunk_size):
        chunks.append((i + 1, "\n".join(lines[i:i + chunk_size])))

    findings = []
    for start_line, chunk in chunks:
        response = llm.generate(
            f"Language: {lang}\nFocus areas: {', '.join(focus)}\n\n"
            f"Code (starting at line {start_line}):\n```{lang}\n{chunk}\n```\n\n"
            "Review this code. For EACH issue found, output one JSON object on its own line (JSONL format) with fields:\n"
            '{"line": <line number within this chunk>, "severity": "critical|high|medium|low", "category": "bug|security|performance|style|maintainability", "message": "<specific, actionable description>", "suggestion": "<concrete fix or code snippet>"}\n'
            "Only report genuine issues. No praise, no filler. If the chunk is clean, output exactly: CLEAN",
            system="You are a staff-level engineer doing a rigorous code review. Be specific: cite the exact expression, name the vulnerability class (CWE if security), and give a fix. No generic advice like 'add error handling' without saying where."
        )
        chunk_findings = _parse_review(response, start_line)
        findings.extend(chunk_findings)
        print(f"  lines {start_line}-{start_line + len(chunk.splitlines()) - 1}: {len(chunk_findings)} finding(s)")

    _report(findings, args)
    return findings

def diff(args):
    """Review a unified diff."""
    llm = LLM()
    code = _read_code(args)
    lang = _detect_lang(getattr(args, "file", ""), args.lang)
    focus = (args.focus or "all").split(",")
    print(f"Reviewing diff ({lang}), focus: {focus}\n")

    response = llm.generate(
        f"Language: {lang}\nFocus areas: {', '.join(focus)}\n\n"
        f"Unified diff:\n```diff\n{code[:12000]}\n```\n\n"
        "Review the ADDED/CHANGED lines in this diff. For EACH issue found, output one JSON object on its own line (JSONL format) with fields:\n"
        '{"line": <line number in diff>, "severity": "critical|high|medium|low", "category": "bug|security|performance|style|maintainability", "message": "<specific, actionable description>", "suggestion": "<concrete fix or code snippet>"}\n'
        "Only report genuine issues in added/changed lines. No praise, no filler. If clean, output exactly: CLEAN",
        system="You are a staff-level engineer doing a rigorous code review of a diff. Be specific: cite the exact expression, name the vulnerability class (CWE if security), and give a fix."
    )
    findings = _parse_review(response, 0)
    _report(findings, args)
    return findings

def review_static(args):
    """Full-file code review with static analysis (no LLM required)."""
    if not STATIC_ANALYZER_AVAILABLE:
        print("Error: Static analyzer not available. Ensure backend dependencies are installed.")
        return []
    code = _read_code(args)
    lang = _detect_lang(getattr(args, "file", ""), args.lang)
    focus = args.focus or "all"
    lines = code.split("\n")
    print(f"Static analysis of {len(lines)} lines ({lang}), focus: {focus or 'all'}\n")

    findings, elapsed = analyze_code(code, lang, focus_areas=focus)
    findings_dicts, _ = _findings_to_dicts(findings, elapsed)
    print(f"  Analyzed in {elapsed:.1f}ms, {len(findings)} finding(s)")
    _report(findings_dicts, args)
    return findings_dicts

def diff_static(args):
    """Review a unified diff with static analysis (no LLM required)."""
    if not STATIC_ANALYZER_AVAILABLE:
        print("Error: Static analyzer not available. Ensure backend dependencies are installed.")
        return []
    diff_text = _read_code(args)
    lang = _detect_lang(getattr(args, "file", ""), args.lang)
    focus = args.focus or "all"
    print(f"Static analysis of diff ({lang}), focus: {focus or 'all'}\n")

    findings, elapsed = analyze_diff(diff_text, lang, focus_areas=focus)
    findings_dicts, _ = _findings_to_dicts(findings, elapsed)
    print(f"  Analyzed in {elapsed:.1f}ms, {len(findings)} finding(s)")
    _report(findings_dicts, args)
    return findings_dicts

def _parse_review(response, base_line):
    findings = []
    for line in response.split("\n"):
        line = line.strip()
        if not line or line == "CLEAN":
            continue
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
            obj["line"] = base_line + int(obj.get("line", 1))
            findings.append(obj)
        except (json.JSONDecodeError, ValueError):
            continue
    return findings

def _report(findings, args):
    from collections import Counter
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (sev_order.get(f.get("severity", "low"), 4), f.get("line", 0)))

    print(f"\n{'='*60}")
    counts = Counter(f.get("severity", "low") for f in findings)
    summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda x: sev_order.get(x[0], 4)))
    print(f"REVIEW: {len(findings)} finding(s) [{summary}]")
    print(f"{'='*60}\n")

    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
    for f in findings:
        sev = f.get("severity", "low")
        print(f"  {icons.get(sev, '⚪')} L{f.get('line', '?')} [{sev.upper()}] {f.get('category', '?')}: {f.get('message', '')}")
        if f.get("suggestion"):
            print(f"     → {f['suggestion']}")

    if not findings:
        print("  ✅ No issues found.")

    if args.output:
        with open(args.output, "w") as f:
            if args.output.endswith((".json",)):
                json.dump(findings, f, indent=2)
            else:
                f.write("# Code Review\n\n")
                for x in findings:
                    f.write(f"- **[{x.get('severity')}] L{x.get('line')}** ({x.get('category')}): {x.get('message')}\n  - Fix: {x.get('suggestion', 'n/a')}\n")
        print(f"\nSaved to {args.output}")

def scan(args):
    """Security scan across a directory (static by default, --llm for LLM)."""
    path = args.path
    files = []
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            files.extend(os.path.join(root, n) for n in names if n.lower().endswith((".py", ".js", ".ts", ".go", ".rs")))
    else:
        files = [path]

    if args.llm:
        # LLM-based security scan
        llm = LLM()
        print(f"LLM security scanning {len(files)} file(s)...\n")
        all_findings = []
        for filepath in files:
            try:
                with open(filepath) as f:
                    code = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            lang = _detect_lang(filepath)
            response = llm.generate(
                f"File: {filepath}\nLanguage: {lang}\n```{lang}\n{code[:12000]}\n```\n\n"
                "List ONLY security vulnerabilities in this file as JSONL: "
                '{"line": <n>, "severity": "critical|high|medium|low", "cwe": "CWE-xxx", "message": "<desc>", "suggestion": "<fix>"}\n'
                "Look for: hardcoded secrets, injection (SQL/cmd/XSS), path traversal, insecure deserialization, missing auth checks, weak crypto. Output CLEAN if none.",
                system="You are a security engineer. Be precise — name the exact vulnerability and CWE. No false positives: confirm the vulnerable expression exists in the code."
            )
            found = _parse_review(response, 0)
            found = [f for f in found if f.get("cwe") or f.get("category") in ("security", "bug")]
            if found:
                print(f"  {filepath}: {len(found)} issue(s)")
                for f in found:
                    print(f"    L{f['line']} [{f.get('severity','?')}] {f.get('cwe','')} {f.get('message','')[:100]}")
                all_findings.extend(found)
            else:
                print(f"  {filepath}: clean")

        print(f"\nTotal security findings: {len(all_findings)}")
        if args.output:
            with open(args.output, "w") as f:
                json.dump(all_findings, f, indent=2)
            print(f"Saved to {args.output}")
        return all_findings
    else:
        # Static analysis security scan
        if not STATIC_ANALYZER_AVAILABLE:
            print("Error: Static analyzer not available. Ensure backend dependencies are installed.")
            return []
        print(f"Static security scanning {len(files)} file(s)...\n")
        all_findings = []
        for filepath in files:
            try:
                with open(filepath) as f:
                    code = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            lang = _detect_lang(filepath)
            findings, elapsed = analyze_code(code, lang, focus_areas="security")
            if findings:
                print(f"  {filepath}: {len(findings)} issue(s) ({elapsed:.1f}ms)")
                for f in findings:
                    print(f"    L{f.line_number} [{f.severity.upper()}] {f.rule_id} {f.message[:100]}")
                    all_findings.append({
                        "line": f.line_number,
                        "severity": f.severity,
                        "category": f.category,
                        "message": f.message,
                        "suggestion": f.suggestion,
                        "rule_id": f.rule_id,
                        "cwe": f.cwe,
                        "file": filepath,
                    })
            else:
                print(f"  {filepath}: clean ({elapsed:.1f}ms)")

        print(f"\nTotal security findings: {len(all_findings)}")
        if args.output:
            with open(args.output, "w") as f:
                json.dump(all_findings, f, indent=2)
            print(f"Saved to {args.output}")
        return all_findings

def main():
    import argparse
    p = argparse.ArgumentParser(prog="code-review-ai", description="AI code review assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("review", help="Review a full file using LLM")
    r.add_argument("--file", default=None); r.add_argument("--stdin", action="store_true")
    r.add_argument("--lang", default=None); r.add_argument("--focus", default="all")
    r.add_argument("--output", default=None)
    r.set_defaults(fn=review)

    d = sub.add_parser("diff", help="Review a unified diff using LLM")
    d.add_argument("--file", default=None); d.add_argument("--stdin", action="store_true")
    d.add_argument("--lang", default=None); d.add_argument("--focus", default="all")
    d.add_argument("--output", default=None)
    d.set_defaults(fn=diff)

    rs = sub.add_parser("review-static", help="Review a full file using static analysis (no LLM required)")
    rs.add_argument("--file", default=None); rs.add_argument("--stdin", action="store_true")
    rs.add_argument("--lang", default=None); rs.add_argument("--focus", default="all")
    rs.add_argument("--output", default=None)
    rs.set_defaults(fn=review_static)

    ds = sub.add_parser("diff-static", help="Review a unified diff using static analysis (no LLM required)")
    ds.add_argument("--file", default=None); ds.add_argument("--stdin", action="store_true")
    ds.add_argument("--lang", default=None); ds.add_argument("--focus", default="all")
    ds.add_argument("--output", default=None)
    ds.set_defaults(fn=diff_static)

    s = sub.add_parser("scan", help="Security scan a directory (static by default, --llm for LLM)")
    s.add_argument("path"); s.add_argument("--output", default=None)
    s.add_argument("--llm", action="store_true", help="Use LLM instead of static analysis")
    s.set_defaults(fn=scan)

    args = p.parse_args()
    if args.cmd in ("review", "diff", "review-static", "diff-static") and not args.file and not getattr(args, "stdin", False):
        p.error("provide --file or --stdin")
    args.fn(args)

if __name__ == '__main__':
    main()
