"""
Thin async wrapper around a Pydantic AI agent run, shared by the multi-provider roles
(victim task agent, guardrail judge). The attack generator stays on the Claude Agent
SDK (claude_runner.py) so it can use the local Claude Code subscription.

Why Pydantic AI for these roles: the same agent code runs on Anthropic, OpenAI, Gemini,
... by changing a provider-qualified model id ("openai:gpt-5-mini"), with no harness of
its own between the model and our prompt + MCP tools — so a measured attack-success rate
is about the model and the defense, not a framework.

Auth is per provider via env (ANTHROPIC_API_KEY, OPENAI_API_KEY, ...); llm.validate_model
checks the key is present before we get here.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # keep server logs clean

from pydantic_ai import (Agent, ModelRequest, ModelResponse, RetryPromptPart, ToolCallPart,
                         ToolReturnPart, UsageLimits, capture_run_messages)
from pydantic_ai.exceptions import AgentRunError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.mcp import MCPToolset, StdioTransport

from refusals import looks_like_refusal
from llm import fallback_price, provider_of


@dataclass
class McpStdio:
    """An MCP server to spawn over stdio for one run."""
    command: str
    args: list[str]
    env: dict[str, str] | None = None


@dataclass
class RunResult:
    text: str = ""
    output: Any = None  # typed output when output_type is not str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str | None = None
    refusal_category: str | None = None
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    cost_usd: float | None = None
    error: str | None = None

    @property
    def refused(self) -> bool:
        return self.stop_reason == "refusal"

    def tool_names(self) -> list[str]:
        return [c.get("name", "") for c in self.tool_calls]


def _response_cost(resp: ModelResponse) -> float | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return float(resp.cost().total_price)
    except Exception:  # model missing from genai-prices -> our fallback table, else unknown
        u = resp.usage
        return fallback_price(resp.model_name or "", u.input_tokens, u.output_tokens,
                              u.cache_read_tokens, u.cache_write_tokens)


def _truncate(text: str, limit: int = 2000) -> str:
    return text if len(text) <= limit else text[:limit] + f"... [{len(text) - limit} more chars]"


def _collect(messages: list, out: RunResult) -> None:
    """Fill tool calls (with their results), stop reason, refusal and cost from the run's
    message history. Tool results matter for the eval: a scoped MCP's denial
    ("User not found in your team") is the defense firing even when the model complied."""
    costs: list[float | None] = []
    by_id: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                call = by_id.get(getattr(part, "tool_call_id", None) or "")
                if call is None:
                    continue
                if isinstance(part, ToolReturnPart):
                    call["result"] = _truncate(part.model_response_str())
                elif isinstance(part, RetryPromptPart):
                    call["result"] = _truncate(f"retry: {part.content}")
            continue
        if not isinstance(msg, ModelResponse):
            continue
        costs.append(_response_cost(msg))
        details = msg.provider_details or {}
        if msg.finish_reason == "content_filter" or "refusal" in details:
            out.stop_reason = "refusal"
            out.refusal_category = details.get("refusal_category")
        elif msg.finish_reason:
            out.stop_reason = msg.finish_reason
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                call = {"name": part.tool_name, "input": part.args_as_dict()}
                out.tool_calls.append(call)
                by_id[part.tool_call_id] = call
    known = [c for c in costs if c is not None]
    out.cost_usd = sum(known) if known else None


async def run_agent(
    prompt: str,
    *,
    model: str,
    system_prompt: str,
    mcp: McpStdio | None = None,
    output_type: Any = str,
    request_limit: int = 50,
    model_settings: dict | None = None,
) -> RunResult:
    """
    Run one agent loop and collect a structured result. Never raises for model-side
    problems (refusal, invalid output, request-limit hit, HTTP error): those come back
    in `error` / `stop_reason`, so one bad cell never 500s the route or crashes the eval.
    """
    toolsets = []
    if mcp is not None:
        toolsets.append(MCPToolset(StdioTransport(command=mcp.command, args=mcp.args, env=mcp.env)))
    agent = Agent(model, instructions=system_prompt, output_type=output_type,
                  toolsets=toolsets, model_settings=model_settings)

    out = RunResult(model=str(model), provider=provider_of(model) if isinstance(model, str) else "test")
    with capture_run_messages() as messages:
        try:
            async with agent:
                result = await agent.run(prompt, usage_limits=UsageLimits(request_limit=request_limit))
        except (UnexpectedModelBehavior, AgentRunError, ModelHTTPError) as e:
            out.error = f"{type(e).__name__}: {e}"
            # Partial history is still useful (tool calls made before the failure, cost).
            _collect(messages, out)
            return out

    _collect(result.all_messages(), out)
    usage = result.usage
    out.input_tokens, out.output_tokens, out.requests = usage.input_tokens, usage.output_tokens, usage.requests
    if output_type is str:
        out.text = result.output or ""
        if out.stop_reason != "refusal" and looks_like_refusal(out.text):
            out.stop_reason = "refusal"
    else:
        out.output = result.output
        out.text = result.output.model_dump_json() if hasattr(result.output, "model_dump_json") else str(result.output)
    return out
