"""
LLM Guard prompt-injection pre-filter (local, model-based).

Uses llm-guard's PromptInjection input scanner (a locally-run HuggingFace classifier),
served by the `llm-guard` sidecar container (app/llm_guard_service/). It lives in its own
container because llm-guard's strict dependency pins can't co-install quickly with the
backend's Pydantic AI stack. `docker compose up` starts it with the rest of the app.

The backend reaches it at LLM_GUARD_URL (default http://llm-guard:8000). If the sidecar
isn't running, the defense reports itself unavailable instead of failing the request.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import requests

LLM_GUARD_URL = os.getenv("LLM_GUARD_URL", "http://llm-guard:8000").rstrip("/")


@dataclass
class FilterResult:
    flagged: bool
    available: bool
    detail: dict
    error: str | None = None


def available() -> tuple[bool, str]:
    try:
        r = requests.get(f"{LLM_GUARD_URL}/health", timeout=2)
        if r.status_code == 200:
            return True, ""
        return False, f"llm-guard sidecar returned HTTP {r.status_code}"
    except requests.RequestException:
        return False, (f"llm-guard sidecar not reachable at {LLM_GUARD_URL} "
                       "(is the llm-guard container running? `docker compose ps`)")


def _scan_sync(transcript: str) -> FilterResult:
    try:
        r = requests.post(f"{LLM_GUARD_URL}/scan", json={"text": transcript}, timeout=120)
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        return FilterResult(False, False, {}, error=f"{type(e).__name__}: {e}")
    if r.status_code != 200:
        return FilterResult(False, False, {}, error=body.get("error", f"HTTP {r.status_code}"))
    return FilterResult(
        flagged=not body["is_valid"],
        available=True,
        detail={k: body.get(k) for k in ("risk_score", "threshold", "match_type")},
    )


async def scan(transcript: str) -> FilterResult:
    return await asyncio.to_thread(_scan_sync, transcript)
