"""The ALIA agent — an in-process ACP client over the lovelaice runtime.

We drive a ``lovelaice`` Agent through its ACP server/client (the same path
lovelaice's own CLI uses), so we inherit sessions, JSONL persistence, tool
dispatch, hooks, and (later) MCP — rather than re-implementing an agent loop.

The HUD talks to this class; this class talks ACP. One session is opened per
app lifetime and reused across turns, so the conversation accumulates and
persists to ``~/.alia/sessions/<ts>.jsonl``.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from typing import Awaitable

from lovelaice.acp.client import InProcessAcpClient
from lovelaice.acp.server import AcpServer

from .host import ApprovalHandler, api_key_configured, create_alia_agent

__all__ = ["AliaAgent", "api_key_configured"]


def _default_session_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.home() / ".alia" / "sessions" / f"{ts}.jsonl"


class AliaAgent:
    """ALIA's conversational core, backed by the lovelaice ACP runtime."""

    def __init__(
        self,
        session_path: Path | None = None,
        cwd: str | None = None,
        approval_handler: ApprovalHandler | None = None,
        on_event: Callable[[str, dict], None] | None = None,
    ) -> None:
        self.session_path = Path(session_path) if session_path else _default_session_path()
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.cwd = cwd or os.path.expanduser("~")
        self._approval_handler = approval_handler
        # Session-scoped set of bash prefixes the user approved "for this
        # session"; shared with the host's approval hook, reset per app launch.
        self.approved_prefixes: set[str] = set()
        # on_event(kind, params): kind is "tool_call" | "tool_call_update".
        self._on_event = on_event
        self._server = AcpServer(
            agent_factory=lambda: create_alia_agent(
                session_path=self.session_path,
                cwd=self.cwd,
                approval_handler=self._approval_handler,
                approved_prefixes=self.approved_prefixes,
            )
        )
        self._client = InProcessAcpClient(self._server)
        self._client.on_notification(self._on_notification)
        self._sid: str | None = None
        self._chunks: list[str] = []
        self._on_chunk: Callable[[str], None] | None = None

    async def start(self) -> None:
        await self._client.initialize()
        self._sid = await self._client.session_new(self.cwd)

    def _on_notification(self, note) -> None:
        if note.method != "session/update":
            return
        params = note.params or {}
        kind = params.get("sessionUpdate")
        if kind == "agent_message_chunk":
            content = params.get("content", {})
            if content.get("type") == "text":
                text = content.get("text", "")
                self._chunks.append(text)
                if self._on_chunk is not None:
                    self._on_chunk(text)
        elif kind in ("tool_call", "tool_call_update") and self._on_event is not None:
            self._on_event(kind, params)

    async def chat(self, text: str, on_chunk: Callable[[str], None] | None = None) -> str:
        """Send a user turn; stream assistant text via on_chunk; return full reply."""
        if self._sid is None:
            await self.start()
        self._on_chunk = on_chunk
        self._chunks = []
        try:
            await self._client.session_prompt(self._sid, text)
        finally:
            self._on_chunk = None
        return "".join(self._chunks)
