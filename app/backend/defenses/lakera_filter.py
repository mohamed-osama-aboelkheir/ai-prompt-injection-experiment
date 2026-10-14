"""
Lakera Guard prompt-injection pre-filter (hosted API, free tier).

Sends the transcript to Lakera Guard's /v2/guard endpoint. Requires LAKERA_API_KEY;
if unset, the defense reports itself unavailable and the route skips it gracefully
(rather than failing the request).

Lakera's top-level `flagged` combines every detector in the project policy — including
PII (`pii/email`), which fires on every meeting transcript because they're full of email
addresses. So we request the per-detector breakdown and block only on the detectors in
LAKERA_DETECTORS (default: `prompt_attack`, Lakera's prompt-injection detector).
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import requests

LAKERA_ENDPOINT = os.getenv("LAKERA_ENDPOINT", "https://api.lakera.ai/v2/guard")
LAKERA_DETECTORS = {d.strip() for d in os.getenv("LAKERA_DETECTORS", "prompt_attack").split(",") if d.strip()}


@dataclass
class FilterResult:
    flagged: bool
    available: bool
    detail: dict
    error: str | None = None


def available() -> tuple[bool, str]:
    if not os.getenv("LAKERA_API_KEY"):
        return False, "LAKERA_API_KEY not set"
    return True, ""


def _scan_sync(transcript: str) -> FilterResult:
    api_key = os.getenv("LAKERA_API_KEY")
    if not api_key:
        return FilterResult(False, False, {}, error="LAKERA_API_KEY not set")
    try:
        resp = requests.post(
            LAKERA_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"messages": [{"role": "user", "content": transcript}], "breakdown": True},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return FilterResult(False, True, {}, error=f"{type(e).__name__}: {e}")
    breakdown = data.get("breakdown") or []
    if not breakdown:  # no per-detector results: fall back to the policy-wide verdict
        return FilterResult(bool(data.get("flagged", False)), True,
                            {"lakera_flagged": data.get("flagged"), "note": "no breakdown returned"})
    hits = [b["detector_type"] for b in breakdown
            if b.get("detected") and b.get("detector_type") in LAKERA_DETECTORS]
    return FilterResult(
        flagged=bool(hits),
        available=True,
        detail={
            "blocking_detectors": sorted(LAKERA_DETECTORS),
            "hits": hits,
            # everything Lakera detected, incl. non-blocking ones (e.g. pii/email), for the report
            "detected": [b["detector_type"] for b in breakdown if b.get("detected")],
            "results": {b["detector_type"]: b.get("result") for b in breakdown
                        if b.get("detector_type") in LAKERA_DETECTORS},
            "request_uuid": (data.get("metadata") or {}).get("request_uuid"),
        },
    )


async def scan(transcript: str) -> FilterResult:
    return await asyncio.to_thread(_scan_sync, transcript)
