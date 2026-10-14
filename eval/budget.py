"""
Per-provider spend ledger + hard caps, shared by the attack agent and the eval matrix.

Every request to the app returns `result.costs` = {provider: USD} for the victim and
guardrail calls it made (priced by genai-prices inside the backend). We add those to a
JSON ledger on disk, so the cap holds across the attack phase, the adaptive phase and the
eval phase. A run stops cleanly before any provider would go over its cap.

Caps come from --budget or the BUDGET_USD env var, e.g. "anthropic=19,openai=19".
A provider without a cap is unlimited. The attack generator on the Claude Code
subscription is not billed per token, so it is not counted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = _REPO_ROOT / "eval" / "results" / "spend.json"


class BudgetExceeded(RuntimeError):
    pass


def parse_caps(spec: str | None) -> dict[str, float]:
    spec = spec if spec is not None else os.getenv("BUDGET_USD", "")
    caps: dict[str, float] = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        provider, _, usd = part.partition("=")
        caps[provider.strip()] = float(usd)
    return caps


class Budget:
    def __init__(self, caps: dict[str, float] | None = None, ledger: Path = DEFAULT_LEDGER):
        self.caps = caps or {}
        self.ledger = Path(ledger)
        self.spent: dict[str, float] = {}
        if self.ledger.is_file():
            self.spent = json.loads(self.ledger.read_text(encoding="utf-8")).get("spent", {})

    def add(self, costs: dict[str, float] | None) -> None:
        # Re-read first so concurrent processes (attack agent + eval, two evals) each add
        # their own spend instead of overwriting the ledger with a stale total.
        if self.ledger.is_file():
            try:
                self.spent = json.loads(self.ledger.read_text(encoding="utf-8")).get("spent", self.spent)
            except (json.JSONDecodeError, OSError):
                pass
        for provider, usd in (costs or {}).items():
            if usd:
                self.spent[provider] = round(self.spent.get(provider, 0.0) + float(usd), 6)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps({"spent": self.spent, "caps": self.caps}, indent=2),
                               encoding="utf-8")

    def check(self, providers: set[str], reserve: dict[str, float] | None = None) -> None:
        """Raise BudgetExceeded if the next call (costing ~`reserve`) could break a cap."""
        for p in providers:
            cap = self.caps.get(p)
            if cap is None:
                continue
            if self.spent.get(p, 0.0) + (reserve or {}).get(p, 0.0) > cap:
                raise BudgetExceeded(f"{p}: spent ${self.spent.get(p, 0.0):.2f} of ${cap:.2f} cap")

    def summary(self) -> str:
        parts = []
        for p in sorted(set(self.spent) | set(self.caps)):
            cap = self.caps.get(p)
            parts.append(f"{p} ${self.spent.get(p, 0.0):.2f}" + (f"/${cap:.2f}" if cap is not None else ""))
        return ", ".join(parts) or "no spend yet"


def provider_of(model: str | None) -> str | None:
    """Provider prefix of a model id ('openai:gpt-5-mini' -> 'openai'); bare claude-* -> anthropic."""
    if not model:
        return None
    if ":" in model:
        return model.split(":", 1)[0]
    low = model.lower()
    if low.startswith("claude"):
        return "anthropic"
    if low.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if low.startswith("gemini"):
        return "google-gla"
    return None
