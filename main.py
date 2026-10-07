#!/usr/bin/env python3
# code-review-ai — AI code review assistant that analyzes diffs or files for bugs, security issues, style problems, and performance pitfalls, generating line-by-line review comments for Python, JS, Go, and Rust.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import LLM
def _detect_lang(filepath, explicit=None):
    if explicit:
        return explicit
    ext = os.path.splitext(filepath)[1].lower()
    return {".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "javascript", ".tsx": "typescript", ".go": "go", ".rs": "rust"}.get(ext, "python")

def _read_code(args):
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    with open(args.file) as f:
        return f.read()

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
    print(f"Reviewing diff ({lang}, {len(code.splitlines())} lines)\n")

    # Only review added lines context
    response = llm.generate(
        f"Language: {lang}\n\nUnified diff:\n```diff\n{code}\n```\n\n"
        "Review ONLY the changes (added/modified lines). For each issue in the CHANGED code, output one JSON object per line (JSONL) with fields:\n"
        '{"line": <line number in the diff>, "severity": "critical|high|medium|low", "category": "bug|security|performance|style|maintainability", "message": "<specific description>", "suggestion": "<concrete fix>"}\n'
        "Flag regressions, broken callers, and new vulnerabilities introduced by the change. If the diff is clean, output: CLEAN",
        system="You are reviewing a PR diff. Focus on what the change breaks or introduces: API contract violations, unhandled edge cases, security holes, performance regressions. Be surgical."
    )
    findings = _parse_review(response, 0)
    _report(findings, args)
    return findings

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
    """Quick security-only scan across a directory."""
    llm = LLM()
    path = args.path
    files = []
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            files.extend(os.path.join(root, n) for n in names if n.lower().endswith((".py", ".js", ".ts", ".go", ".rs")))
    else:
        files = [path]

    print(f"Security scanning {len(files)} file(s)...\n")
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

def main():
    import argparse
    p = argparse.ArgumentParser(prog="code-review-ai", description="AI code review assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("review", help="Review a full file")
    r.add_argument("--file", default=None); r.add_argument("--stdin", action="store_true")
    r.add_argument("--lang", default=None); r.add_argument("--focus", default="all")
    r.add_argument("--output", default=None)
    r.set_defaults(fn=review)

    d = sub.add_parser("diff", help="Review a unified diff")
    d.add_argument("--file", default=None); d.add_argument("--stdin", action="store_true")
    d.add_argument("--lang", default=None); d.add_argument("--output", default=None)
    d.set_defaults(fn=diff)

    s = sub.add_parser("scan", help="Security scan a directory")
    s.add_argument("path"); s.add_argument("--output", default=None)
    s.set_defaults(fn=scan)

    args = p.parse_args()
    if not args.file and not getattr(args, "stdin", False):
        p.error("provide --file or --stdin")
    args.fn(args)

if __name__ == '__main__':
    main()
