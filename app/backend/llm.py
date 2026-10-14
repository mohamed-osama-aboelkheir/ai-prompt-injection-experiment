"""
Central model configuration + auth resolution — the single source of truth for
"which model does each role use, on which provider, and how do we authenticate".

Design goal (see config/models.yaml): swapping the model for ANY role — victim app,
attack agent, guardrail — must be a one-line change, never a code edit.

Resolution precedence for a role:  explicit override > env var > models.yaml > built-in default.
No model ID is hardcoded in agent code; everything routes through resolve_model().

Two runtimes:
  * app_model / guardrail_model run on Pydantic AI (llm_runner.py) and are
    provider-qualified ("anthropic:claude-haiku-4-5", "openai:gpt-5-mini"). Each needs
    that provider's API key (ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY ...).
  * attack_model runs on the Claude Agent SDK (claude_runner.py) and may use the local
    Claude Code subscription login when ANTHROPIC_API_KEY is unset.

This module deliberately has NO heavy imports (no SDK, no yaml package) so it can be
imported from the Flask backend, the attack CLI, and the eval harness alike.
"""
from __future__ import annotations

import os
from pathlib import Path

# Built-in defaults (kept in sync with config/models.yaml). Used when the yaml is
# absent — e.g. inside the backend container, where env vars supply the values.
BUILTIN_DEFAULTS: dict[str, str | None] = {
    "app_model": "anthropic:claude-haiku-4-5",       # victim task-extraction agent
    "attack_model": "claude-opus-5",                 # injection payload generator (Agent SDK)
    "guardrail_model": "anthropic:claude-haiku-4-5",  # injection-detection judge
    "judge_model": None,                             # eval success check: None => deterministic regex
}

# Roles that run on Pydantic AI (multi-provider) vs the Claude Agent SDK.
PYDANTIC_ROLES = {"app_model", "guardrail_model", "judge_model"}

# Models reachable on the Claude Code subscription login (no API key). The API-key
# path additionally unlocks the full range (fable, mythos, effort levels, ...).
_SUBSCRIPTION_PREFIXES = ("claude-opus", "claude-sonnet", "claude-haiku")
_SUBSCRIPTION_ALIASES = {"opus", "sonnet", "haiku"}

# provider prefix -> env var holding its API key (Pydantic AI reads these itself).
PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google-gla": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def qualify_model(model: str) -> str:
    """Return a provider-qualified Pydantic AI model id. Bare ids are inferred:
    claude-* -> anthropic:, gpt-*/o1/o3/o4 -> openai:, gemini-* -> google-gla:."""
    m = model.strip()
    if ":" in m:
        return m
    low = m.lower()
    if low.startswith("claude"):
        return f"anthropic:{m}"
    if low.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")):
        return f"openai:{m}"
    if low.startswith("gemini"):
        return f"google-gla:{m}"
    raise ValueError(f"Can't infer the provider for model {model!r}; write it as 'provider:model'.")


# USD per 1M tokens (input, output, cache read, cache write) for models genai-prices doesn't
# know yet, so the spend ledger doesn't record $0. Cache rates assume the usual 0.1x / 1.25x.
FALLBACK_PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),  # prompts <= 100K tokens
}


def fallback_price(model: str, input_tokens: int, output_tokens: int,
                   cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float | None:
    """Cost from FALLBACK_PRICES. input_tokens is the total input, cache tokens included
    (genai-prices / Pydantic AI convention)."""
    p = FALLBACK_PRICES.get(bare_model(model))
    if p is None:
        return None
    uncached = max(input_tokens - cache_read_tokens - cache_write_tokens, 0)
    return (uncached * p[0] + output_tokens * p[1]
            + cache_read_tokens * p[2] + cache_write_tokens * p[3]) / 1_000_000


def provider_of(model: str) -> str:
    return qualify_model(model).split(":", 1)[0]


def bare_model(model: str) -> str:
    return model.split(":", 1)[1] if ":" in model else model


def _find_models_yaml() -> Path | None:
    """Locate config/models.yaml: explicit MODELS_CONFIG env, else walk up for config/."""
    env_path = os.getenv("MODELS_CONFIG")
    if env_path:
        p = Path(env_path)
        return p if p.is_file() else None
    # Walk up from this file's directory looking for <ancestor>/config/models.yaml.
    for base in Path(__file__).resolve().parents:
        candidate = base / "config" / "models.yaml"
        if candidate.is_file():
            return candidate
    return None


def _parse_flat_yaml(text: str) -> dict[str, str | None]:
    """Tiny flat `key: value` parser (values are scalars). Avoids a yaml dependency."""
    out: dict[str, str | None] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, rest = line.partition(":")
        value = rest.split("#", 1)[0].strip().strip("'\"")
        key = key.strip()
        if value == "" or value.lower() in ("null", "none", "~"):
            out[key] = None
        else:
            out[key] = value
    return out


_yaml_cache: dict[str, str | None] | None = None


def _yaml_values() -> dict[str, str | None]:
    global _yaml_cache
    if _yaml_cache is None:
        path = _find_models_yaml()
        if path is None:
            _yaml_cache = {}
        else:
            _yaml_cache = _parse_flat_yaml(path.read_text(encoding="utf-8"))
    return _yaml_cache


def has_api_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def auth_mode() -> str:
    """Agent SDK auth (attack agent): 'api_key' if ANTHROPIC_API_KEY is set, else 'subscription'."""
    return "api_key" if has_api_key() else "subscription"


def is_subscription_model(model: str) -> bool:
    m = bare_model(model).strip().lower()
    return m in _SUBSCRIPTION_ALIASES or m.startswith(_SUBSCRIPTION_PREFIXES)


def validate_model(model: str, role: str = "") -> str:
    """Normalize `model` for its role and raise with guidance if it can't be reached."""
    label = f" for role '{role}'" if role else ""
    if role in PYDANTIC_ROLES:
        model = qualify_model(model)
        key_env = PROVIDER_KEY_ENV.get(provider_of(model))
        if key_env and not os.getenv(key_env):
            raise ValueError(f"Model {model!r}{label} needs {key_env} to be set.")
        return model
    # attack_model: Claude Agent SDK
    is_claude = (model.startswith("anthropic:") if ":" in model
                 else model.lower().startswith(("claude", *_SUBSCRIPTION_ALIASES)))
    if not is_claude:
        raise ValueError(f"Model {model!r}{label} must be a Claude model (the attack agent runs on "
                         f"the Claude Agent SDK).")
    model = bare_model(model)
    if auth_mode() == "subscription" and not is_subscription_model(model):
        raise ValueError(
            f"Model {model!r}{label} is not available on the Claude Code subscription "
            f"login (which supports opus / sonnet / haiku). Either choose an "
            f"opus/sonnet/haiku model, or set ANTHROPIC_API_KEY to use the API path "
            f"which unlocks the full model range."
        )
    return model


def resolve_model(role: str, override: str | None = None) -> str | None:
    """
    Resolve the model for a role. Roles: 'app_model', 'attack_model',
    'guardrail_model', 'judge_model' (or short forms 'app'/'attack'/'guardrail'/'judge').

    Returns None only for judge_model when unset (=> deterministic regex).
    """
    role_key = role if role.endswith("_model") else f"{role}_model"
    if role_key not in BUILTIN_DEFAULTS:
        raise KeyError(f"Unknown model role {role!r}; known: {sorted(BUILTIN_DEFAULTS)}")

    if override:
        model = override
    else:
        env_val = os.getenv(role_key.upper())
        if env_val:
            model = env_val
        else:
            yaml_val = _yaml_values().get(role_key, "__missing__")
            model = yaml_val if yaml_val != "__missing__" else BUILTIN_DEFAULTS[role_key]

    if model is None:
        return None
    return validate_model(model, role_key)


if __name__ == "__main__":  # quick introspection: `python llm.py`
    print(f"auth_mode = {auth_mode()}")
    for r in BUILTIN_DEFAULTS:
        try:
            print(f"{r:16} -> {resolve_model(r)}")
        except ValueError as e:
            print(f"{r:16} -> ERROR: {e}")
