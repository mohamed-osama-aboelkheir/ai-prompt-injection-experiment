"""
Thin async wrapper around the Claude Agent SDK `query()` loop, shared by every role
(victim task agent, guardrail judge, attack payload generator).

Why a wrapper: each role needs the same handful of things out of a run — the final
text, which tools got called, whether the model refused, MCP connection status — and
we want ONE place that isolates the run from the developer's ~/.claude settings
(`setting_sources=[]`) and picks a locked-down permission posture.

Auth is implicit: the Agent SDK uses ANTHROPIC_API_KEY when set, otherwise the local
Claude Code login (subscription). Nothing to pass here.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ClaudeSDKError,
)

from refusals import looks_like_refusal  # noqa: E402,F401  (re-exported for callers)

try:  # SystemMessage carries the MCP init status; import defensively
    from claude_agent_sdk import SystemMessage  # type: ignore
except Exception:  # pragma: no cover
    SystemMessage = None  # type: ignore


@dataclass
class RunResult:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str | None = None
    result_subtype: str | None = None
    refusal_category: str | None = None
    mcp_servers: Any = None
    raw_result: Any = None
    total_cost_usd: float | None = None
    error: str | None = None

    @property
    def refused(self) -> bool:
        return self.stop_reason == "refusal"

    def tool_names(self) -> list[str]:
        return [c.get("name", "") for c in self.tool_calls]


async def run_claude(
    prompt: str,
    *,
    model: str,
    system_prompt: str | None = None,
    mcp_servers: dict | None = None,
    allowed_tools: list[str] | None = None,
    disallowed_tools: list[str] | None = None,
    tools: list[str] | None = None,
    max_turns: int | None = None,
    env: dict[str, str] | None = None,
    permission_mode: str = "dontAsk",
    cwd: str | None = None,
) -> RunResult:
    """
    Run one agent turn-loop and collect a structured result.

    permission_mode defaults to "dontAsk": anything not explicitly in `allowed_tools`
    is denied rather than prompting (there is no human in the loop). Grant MCP tools
    via allowed_tools=["mcp__<server>__*"].

    tools controls the base built-in tool set: pass [] to disable all built-in Claude Code
    tools (Bash/Read/Write/WebSearch/...) so the agent has ONLY the MCP tools you attach —
    a realistic, minimal surface. None (default) keeps the standard built-ins.
    """
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        mcp_servers=mcp_servers or {},
        allowed_tools=allowed_tools or [],
        disallowed_tools=disallowed_tools or [],
        tools=tools,
        permission_mode=permission_mode,
        max_turns=max_turns,
        env=env or {},
        cwd=cwd,
        setting_sources=[],  # ignore ~/.claude + project settings for a clean, reproducible run
    )

    out = RunResult()
    texts: list[str] = []
    # A terminal condition (max-turns reached, process error) is raised as a ClaudeSDKError
    # *after* the assistant messages have already been yielded. Catch it and return what we
    # collected, so one agent hiccup never 500s the route or crashes the eval.
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                if getattr(message, "stop_reason", None):
                    out.stop_reason = message.stop_reason
                for block in message.content:
                    if isinstance(block, TextBlock):
                        texts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        out.tool_calls.append({"name": block.name, "input": block.input})
            elif SystemMessage is not None and isinstance(message, SystemMessage):
                if getattr(message, "subtype", None) == "init":
                    data = getattr(message, "data", {}) or {}
                    out.mcp_servers = data.get("mcp_servers")
            elif isinstance(message, ResultMessage):
                out.result_subtype = message.subtype
                out.raw_result = message.result
                out.total_cost_usd = getattr(message, "total_cost_usd", None)
                # Prefer an assistant-level stop_reason; fall back to the result's.
                if out.stop_reason is None:
                    out.stop_reason = getattr(message, "stop_reason", None)
    except ClaudeSDKError as e:
        out.error = f"{type(e).__name__}: {e}"
        if out.result_subtype is None:
            out.result_subtype = "error"

    out.text = "".join(texts).strip()
    # If the transport gave us a result string but no text blocks, fall back to it.
    if not out.text and isinstance(out.raw_result, str):
        out.text = out.raw_result.strip()
    return out


def run_claude_sync(*args, **kwargs) -> RunResult:
    """Blocking convenience wrapper for Flask routes and CLI scripts."""
    return asyncio.run(run_claude(*args, **kwargs))
