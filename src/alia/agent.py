"""The ALIA agent — a thin wrapper over a lingo ``Lingo`` instance.

lingo is the engine under lovelaice ("a single ReAct loop on top of lingo").
We use the bare ``Lingo`` chat surface with ALIA's persona and no tools, so
the voice is the cognitive partner — not the coding agent.

Model config resolves from the environment, defaulting to Haiku over
OpenRouter:

    ALIA_MODEL    / MODEL              -> model slug   (default anthropic/claude-haiku-4.5)
    ALIA_BASE_URL / BASE_URL           -> API base url (default https://openrouter.ai/api/v1)
    ALIA_API_KEY  / OPENROUTER_API_KEY / API_KEY -> key
"""

from __future__ import annotations

import os
from typing import Callable

from lingo import LLM, Lingo

from .persona import ALIA_SYSTEM_PROMPT

DEFAULT_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


# Placeholder so the OpenAI client constructs even with no key configured;
# the auth error then surfaces at call time (in the HUD) instead of crashing
# the app at startup.
_NO_KEY = "NO_API_KEY_SET"


def api_key_configured() -> bool:
    return _first_env("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY") is not None


def build_llm(on_token: Callable[[str], None] | None = None) -> LLM:
    """Build the LLM from the environment, with ALIA's OpenRouter/Haiku defaults."""
    return LLM(
        model=_first_env("ALIA_MODEL", "MODEL", default=DEFAULT_MODEL),
        base_url=_first_env("ALIA_BASE_URL", "BASE_URL", default=DEFAULT_BASE_URL),
        api_key=_first_env("ALIA_API_KEY", "OPENROUTER_API_KEY", "API_KEY") or _NO_KEY,
        on_token=on_token,
    )


class AliaAgent:
    """ALIA's conversational core. Keeps history across turns within a session."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or build_llm()
        self.lingo = Lingo(
            name="ALIA",
            description="The cognitive partner of the AI-n-Box desktop.",
            llm=self.llm,
            system_prompt=ALIA_SYSTEM_PROMPT,
        )

    def set_on_token(self, callback: Callable[[str], None] | None) -> None:
        """Stream reply tokens as they arrive (set None to stop streaming)."""
        self.llm._on_token = callback

    async def chat(self, text: str) -> str:
        """Send a user turn, return ALIA's full reply text."""
        message = await self.lingo.chat(text)
        content = message.content
        return content if isinstance(content, str) else str(content)
