"""ALIA host — assembles a lovelaice ``Agent`` for the cognitive-partner use case.

Mirrors ``lovelaice.coding.host.create_coding_agent`` but with ALIA's persona
and (for the current chat-only slice) no tools. Tools and MCP servers get wired
here next — this is the seam. Building on the real Agent means we inherit
lovelaice's session persistence, conversation store, tool dispatch, and hooks
for free, instead of re-implementing an agent loop on bare lingo.
"""

from __future__ import annotations

import os
from pathlib import Path

from lovelaice.agent import Agent, AgentConfig
from lovelaice.agent.loops.react_native import ReActNative

from .persona import ALIA_SYSTEM_PROMPT

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Placeholder so the OpenAI client constructs even with no key configured;
# the auth error then surfaces at call time (shown in the HUD) instead of
# crashing the app at startup.
_NO_KEY = "NO_API_KEY_SET"


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
    model: str | None = None,
    cwd: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Agent:
    """Build ALIA's agent: persona + ReActNative loop, no tools yet."""
    cfg = AgentConfig(
        model=model or _first_env("ALIA_MODEL", "MODEL", default=DEFAULT_MODEL),
        system_prompt=ALIA_SYSTEM_PROMPT,
        cwd=cwd or os.path.expanduser("~"),
        api_key=api_key
        or _first_env("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY")
        or _NO_KEY,
        base_url=base_url or _first_env("ALIA_BASE_URL", "BASE_URL", default=DEFAULT_BASE_URL),
    )
    return Agent(
        config=cfg,
        tools=[],  # chat-only slice; tools + MCP wire in here next
        loop=ReActNative(),
        session_path=session_path,
    )
