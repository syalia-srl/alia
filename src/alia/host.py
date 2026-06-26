"""ALIA host — assembles a lovelaice ``Agent`` for the cognitive-partner use case.

Mirrors ``lovelaice.coding.host.create_coding_agent`` but with ALIA's persona
and the v1.0 capability surface: read (silent) + bash (approval-gated).

Safety model for v1.0:
- ``bash_prefix_guard`` is a hard red-line (blocks ``sudo``/``rm -rf /`` etc.)
  and runs first, so the worst is blocked before the user is even asked.
- the approval hook gates every surviving ``bash`` call behind an explicit
  user decision; ``read`` and anything else auto-allow (observation is free).
- no ``path_guard``: a partner reads anywhere; reads don't mutate.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Awaitable, Callable

from lovelaice.agent import Agent, AgentConfig, AgentTool, Allow, Block
from lovelaice.agent.loops.react_native import ReActNative
from lovelaice.coding.hooks import bash_prefix_guard
from lovelaice.coding.tools.bash import bash as bash_tool
from lovelaice.coding.tools.read import read as read_tool

from .persona import ALIA_SYSTEM_PROMPT

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_NO_KEY = "NO_API_KEY_SET"

# Tools that mutate / execute and therefore require approval. Everything else
# (notably read) is auto-allowed.
GATED_TOOLS = {"bash"}

# async (tool_name, arguments) -> bool
ApprovalHandler = Callable[[str, dict], Awaitable[bool]]


async def _deny_all(_tool_name: str, _arguments: dict) -> bool:
    """Fail-safe default: deny gated tools when no handler is wired."""
    return False


def make_approval_hook(handler: ApprovalHandler):
    """A tool_call reducer hook: gate GATED_TOOLS behind `handler`, allow rest."""

    async def approval_hook(call):
        if call.name not in GATED_TOOLS:
            return None  # auto-allow (read, etc.)
        approved = await handler(call.name, dict(call.arguments or {}))
        return Allow() if approved else Block(reason="declined by the user")

    return approval_hook


def _first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def api_key_configured() -> bool:
    return _first_env("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY") is not None


def create_alia_agent(
    *,
    session_path: Path,
    approval_handler: ApprovalHandler | None = None,
    model: str | None = None,
    cwd: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Agent:
    """Build ALIA's agent: persona + read + approval-gated bash."""
    cfg = AgentConfig(
        model=model or _first_env("ALIA_MODEL", "MODEL", default=DEFAULT_MODEL),
        system_prompt=ALIA_SYSTEM_PROMPT,
        cwd=cwd or os.path.expanduser("~"),
        api_key=api_key
        or _first_env("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY")
        or _NO_KEY,
        base_url=base_url or _first_env("ALIA_BASE_URL", "BASE_URL", default=DEFAULT_BASE_URL),
    )
    tools = [
        AgentTool(inner=read_tool, kind="read", title_template="Reading {path}"),
        AgentTool(inner=bash_tool, sequential=True, kind="execute",
                  title_template="Running a command"),
    ]
    agent = Agent(config=cfg, tools=tools, loop=ReActNative(), session_path=session_path)
    # Order matters: hard red-line first (short-circuits to Block before we ask),
    # then the interactive approval gate.
    agent.harness.hooks.register("tool_call", bash_prefix_guard)
    agent.harness.hooks.register(
        "tool_call", make_approval_hook(approval_handler or _deny_all))
    return agent
