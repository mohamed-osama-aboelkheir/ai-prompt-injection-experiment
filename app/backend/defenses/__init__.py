"""
Defense registry + pipeline.

Each defense is a named profile combining:
  - pre-filters: detectors run BEFORE the victim agent; any hit blocks processing.
  - mcp_variant: "baseline" (vulnerable) or "scoped" (access-controlled tools).
  - spotlight:   whether to harden the victim's prompt + wrap the transcript as data.

Adding your own mitigation (see README "add your own defense"): implement a pre-filter
module exposing `available()` and `async scan(transcript) -> FilterResult`, register it
in PREFILTERS, and add a PROFILES entry.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents import task_agent  # noqa: E402
from agents import guardrail_agent  # noqa: E402
from defenses import jev_filter, llm_guard_filter, lakera_filter  # noqa: E402

# defense name -> {prefilters: [...], mcp: "baseline"|"scoped", spotlight: bool, description}
PROFILES: dict[str, dict] = {
    "none": {
        "prefilters": [], "mcp": "baseline", "spotlight": False,
        "description": "Baseline vulnerable app — no mitigation.",
    },
    "spotlight": {
        "prefilters": [], "mcp": "baseline", "spotlight": True,
        "description": "Prompt hardening: transcript wrapped as untrusted data + instruction/data separation.",
    },
    "guardrail": {
        "prefilters": ["guardrail"], "mcp": "baseline", "spotlight": False,
        "description": "LLM-as-judge inspects the transcript and blocks detected injections.",
    },
    "llm_guard": {
        "prefilters": ["llm_guard"], "mcp": "baseline", "spotlight": False,
        "description": "LLM Guard local PromptInjection scanner as a pre-filter.",
    },
    "lakera": {
        "prefilters": ["lakera"], "mcp": "baseline", "spotlight": False,
        "description": "Lakera Guard hosted classifier as a pre-filter (needs LAKERA_API_KEY).",
    },
    "jev": {
        "prefilters": ["jev"], "mcp": "baseline", "spotlight": False,
        "description": "Jev (TypeSafe) zero-shot classifier asked true/false injection questions "
                       "(needs TYPESAFE_API_KEY).",
    },
    "scoped_mcp": {
        "prefilters": [], "mcp": "scoped", "spotlight": False,
        "description": "Root-cause fix: MCP tools enforce the caller's team_id (access control).",
    },
    "defense_in_depth": {
        "prefilters": ["guardrail"], "mcp": "scoped", "spotlight": True,
        "description": "Scoped MCP + spotlighting + guardrail together.",
    },
}

DEFENSES = list(PROFILES)


def _prefilter_available(name: str) -> tuple[bool, str]:
    if name == "guardrail":
        return True, ""  # always available (uses the configured guardrail model)
    if name == "llm_guard":
        return llm_guard_filter.available()
    if name == "lakera":
        return lakera_filter.available()
    if name == "jev":
        return jev_filter.available()
    return False, f"unknown prefilter {name!r}"


def _add_cost(costs: dict, provider: str, usd: float | None) -> None:
    if usd is not None and provider:
        costs[provider] = round(costs.get(provider, 0.0) + usd, 6)


async def _run_prefilter(name: str, transcript: str, *, guardrail_model: str | None, costs: dict):
    """Return (flagged: bool, detail: dict, error: str|None). Adds model spend to `costs`."""
    if name == "guardrail":
        v = await guardrail_agent.check_transcript(transcript, model=guardrail_model)
        _add_cost(costs, v.provider, v.cost_usd)
        return v.has_injection, {"reasoning": v.reasoning, "model": v.model}, v.error
    if name == "llm_guard":
        r = await llm_guard_filter.scan(transcript)
        return r.flagged, r.detail, r.error
    if name == "lakera":
        r = await lakera_filter.scan(transcript)
        return r.flagged, r.detail, r.error
    if name == "jev":
        r = await jev_filter.scan(transcript)
        return r.flagged, r.detail, r.error
    return False, {}, f"unknown prefilter {name!r}"


def describe() -> list[dict]:
    """Machine-readable catalog for the API / UI, including availability."""
    out = []
    for name, p in PROFILES.items():
        avail, reason = True, ""
        for pf in p["prefilters"]:
            ok, why = _prefilter_available(pf)
            if not ok:
                avail, reason = False, why
                break
        out.append({"name": name, "description": p["description"],
                    "available": avail, "unavailable_reason": reason or None})
    return out


async def run_pipeline(
    defense: str,
    transcript: str,
    caller: dict,
    *,
    app_model: str | None = None,
    guardrail_model: str | None = None,
) -> dict:
    """Run a transcript through the named defense and return a unified result dict."""
    if defense not in PROFILES:
        raise ValueError(f"Unknown defense {defense!r}; known: {DEFENSES}")
    profile = PROFILES[defense]

    base = {
        "defense": defense,
        "app_model": app_model,
        "guardrail_model": guardrail_model,
        "blocked_by": None,
        "detector_detail": None,
        "unavailable_reason": None,
        "tasks": [],
        "raw_output": "",
        "tool_calls": [],
        "refused": False,
        "error": None,
        "cost_usd": None,
        "costs": {},  # provider -> USD for this request (victim + guardrail), for budget tracking
    }
    costs = base["costs"]

    # 1. Pre-filters (fail-open on unavailability with a clear reason).
    for pf in profile["prefilters"]:
        ok, why = _prefilter_available(pf)
        if not ok:
            return {**base, "status": "unavailable", "unavailable_reason": f"{pf}: {why}"}
        flagged, detail, error = await _run_prefilter(pf, transcript, guardrail_model=guardrail_model,
                                                      costs=costs)
        if flagged:
            return {**base, "status": "blocked", "blocked_by": pf, "detector_detail": detail,
                    "cost_usd": _total(costs)}
        base["detector_detail"] = {"prefilter": pf, "flagged": False, **({"detail": detail} if detail else {})}
        if error:
            base["detector_detail"]["error"] = error

    # 2. Victim agent with the profile's knobs.
    system_prompt = task_agent.SPOTLIGHT_SYSTEM_PROMPT if profile["spotlight"] else None
    result = await task_agent.process_transcript(
        transcript,
        caller=caller,
        model=app_model,
        mcp_variant=profile["mcp"],
        system_prompt=system_prompt,
        wrap_transcript=profile["spotlight"],
    )
    _add_cost(costs, result.provider, result.total_cost_usd)
    return {
        **base,
        "status": "processed",
        "app_model": result.model or app_model,
        "tasks": result.tasks,
        "raw_output": result.raw_output,
        "tool_calls": result.tool_calls,
        "refused": result.refused,
        "error": result.error,
        "stop_reason": result.stop_reason,
        "usage": result.usage,
        "cost_usd": _total(costs),
    }


def _total(costs: dict) -> float | None:
    return round(sum(costs.values()), 6) if costs else None
