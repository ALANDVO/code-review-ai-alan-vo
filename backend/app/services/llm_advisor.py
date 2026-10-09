"""
LLM advisory service — multi-provider adapter for optional AI-generated
explanations and additional hints layered on top of deterministic findings.

Providers: OpenAI-compatible (OpenAI, LiteLLM, Ollama, OpenRouter),
           Anthropic messages API, Google Gemini generateContent API.

LLM_API_KEY is the only credential. LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL
are non-secret operator settings. All external calls have bounded timeouts.
Errors are redacted before being returned to callers.
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

import httpx

from app.core.config import settings
from app.services.analyzer import Finding

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

_ADVISORY_SYSTEM = (
    "You are a senior software engineer reviewing code findings produced by a "
    "static analysis tool. For each finding, add a concise advisory note "
    "(1-2 sentences) that explains why the issue matters and gives a concrete fix. "
    "Respond ONLY with a JSON array of objects: "
    '[{"rule_id":"...","advisory_note":"..."}]. '
    "Do not add new findings. Do not invent issues not in the input."
)


def _redact(msg: str) -> str:
    """Strip any token-shaped strings from error messages before logging/returning."""
    return re.sub(r"sk-[A-Za-z0-9]{10,}", "[REDACTED]", msg)


def _build_prompt(code_snippet: str, findings: List[Finding], language: str) -> str:
    findings_json = json.dumps(
        [{"rule_id": f.rule_id, "line": f.line_number, "message": f.message} for f in findings],
        indent=2,
    )
    return (
        f"Language: {language}\n\n"
        f"Static analysis findings:\n{findings_json}\n\n"
        f"Code excerpt (first 4000 chars):\n```{language}\n{code_snippet[:4000]}\n```\n\n"
        "Provide advisory notes for each finding."
    )


def _parse_advisory_response(raw: str, findings: List[Finding]) -> List[Finding]:
    """Merge advisory notes back into findings by rule_id."""
    import dataclasses
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return findings
        notes_list = json.loads(raw[start:end])
        note_map = {item["rule_id"]: item.get("advisory_note", "") for item in notes_list if "rule_id" in item}
    except (json.JSONDecodeError, KeyError):
        return findings

    enriched: List[Finding] = []
    for f in findings:
        note = note_map.get(f.rule_id, "")
        enriched.append(dataclasses.replace(f, advisory_note=note))
    return enriched



# ── Provider adapters ──────────────────────────────────────────────────────────

def _call_openai_compatible(prompt: str, api_key: str, base_url: str, model: str) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _ADVISORY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": _ADVISORY_SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": _ADVISORY_SYSTEM + "\n\n" + prompt}]}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.2},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# ── Public API ─────────────────────────────────────────────────────────────────

def enrich_with_advisory(
    findings: List[Finding],
    code_snippet: str,
    language: str,
    app_settings=None,
) -> tuple[List[Finding], str]:
    """
    Optionally enrich findings with LLM advisory notes.

    Returns (enriched_findings, provider_name).
    Provider is "offline-engine" when LLM is unavailable.
    Raises ValueError with a redacted message if the LLM call fails.
    """
    config = app_settings or settings
    if not config.llm_api_key and config.llm_provider != "ollama":
        return findings, "offline-engine"
    if not findings:
        return findings, "offline-engine"

    prompt = _build_prompt(code_snippet, findings, language)
    provider = config.llm_provider.lower()
    model = config.llm_model
    api_key = config.llm_api_key
    base_url = config.llm_base_url

    try:
        if provider == "anthropic":
            raw = _call_anthropic(prompt, api_key, model)
        elif provider == "gemini":
            raw = _call_gemini(prompt, api_key, model)
        else:
            # openai-compatible: openai, litellm, ollama, openrouter
            raw = _call_openai_compatible(prompt, api_key, base_url, model)

        enriched = _parse_advisory_response(raw, findings)
        return enriched, provider

    except httpx.HTTPStatusError as exc:
        raise ValueError(
            f"LLM provider '{provider}' returned HTTP {exc.response.status_code}. "
            "Check LLM_API_KEY and LLM_BASE_URL configuration."
        ) from None
    except httpx.RequestError as exc:
        raise ValueError(
            "LLM endpoint is unreachable or timed out."
        ) from None
    except Exception as exc:
        raise ValueError("LLM advisory returned an invalid response.") from None
