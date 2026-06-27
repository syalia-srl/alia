"""The resident ALIA application.

A single-instance GTK application that stays alive in the background. Running
``alia`` again (e.g. from a keyboard shortcut) re-activates it and toggles the
HUD. A background asyncio loop runs the agent so the GTK main loop never blocks.
"""

from __future__ import annotations

import asyncio
import os
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from .agent import AliaAgent  # noqa: E402
from .hud import HudWindow  # noqa: E402

APP_ID = "dev.syalia.Alia"


class AliaApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window: HudWindow | None = None
        self.agent: AliaAgent | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.hold()  # stay resident even when the HUD is hidden
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()
        self.agent = AliaAgent(
            approval_handler=self._approve,
            on_event=self._forward_event,
        )
        self._transcriber = None  # alia.voice.Transcriber (lazy)
        self._speaker = None  # alia.voice.Speaker (lazy)

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _ensure_window(self) -> HudWindow:
        if self.window is None:
            self.window = HudWindow(self)
        return self.window

    def do_activate(self) -> None:
        self._ensure_window().toggle()

    async def _approve(self, tool_name: str, arguments: dict) -> str:
        """Bridge an agent approval request to the HUD; await the choice.

        Returns "deny" | "once" | "session".
        """
        loop = self._loop
        assert loop is not None
        future = loop.create_future()

        def resolve(decision: str) -> None:
            loop.call_soon_threadsafe(future.set_result, decision)

        GLib.idle_add(self._ensure_window().ask_approval, tool_name, arguments, resolve)
        return await future

    def _forward_event(self, kind: str, params: dict) -> None:
        GLib.idle_add(self._ensure_window().on_tool_event, kind, params)

    # ---- voice (STT in / TTS out), off the GTK thread -----------------------

    def start_listening(self, on_partial, on_ready) -> None:
        """Open the mic and stream partial transcripts (lazy whisper load)."""
        from .voice import Transcriber

        def work() -> None:
            try:
                if self._transcriber is None:
                    self._transcriber = Transcriber()
                self._transcriber.start(on_partial=lambda t: GLib.idle_add(on_partial, t))
                GLib.idle_add(on_ready, True, "")
            except Exception as exc:  # mic/model failure → tell the HUD
                GLib.idle_add(on_ready, False, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def stop_listening(self, on_final) -> None:
        """Stop capture and deliver the final transcript to on_final(text)."""
        def work() -> None:
            text = self._transcriber.stop() if self._transcriber else ""
            GLib.idle_add(on_final, text)

        threading.Thread(target=work, daemon=True).start()

    def speak(self, text: str) -> None:
        """Speak a reply aloud (lazy kokoro load); fire-and-forget."""
        from .voice import Speaker

        def work() -> None:
            try:
                if self._speaker is None:
                    self._speaker = Speaker()
                self._speaker.speak(text)
            except Exception:
                pass  # TTS is best-effort; never break the turn

        threading.Thread(target=work, daemon=True).start()

    def submit(self, text, on_token, on_done) -> None:
        """Run one agent turn off the GTK thread, marshalling results back to it."""
        assert self.agent is not None and self._loop is not None

        def on_chunk(tok: str) -> None:
            GLib.idle_add(on_token, tok)

        future = asyncio.run_coroutine_threadsafe(
            self.agent.chat(text, on_chunk=on_chunk), self._loop
        )

        def _done(fut) -> None:
            try:
                reply = fut.result()
            except Exception as exc:  # surface auth/network errors in the HUD
                reply = f"[error: {exc}]"
                GLib.idle_add(on_token, reply)
            GLib.idle_add(on_done, reply)

        future.add_done_callback(_done)


def _load_config() -> None:
    """Load config so a GNOME-shortcut launch (no shell env) still gets the key.

    Order: ~/.config/alia/env, then a local .env if present. Real environment
    variables already set always win.
    """
    from dotenv import load_dotenv

    load_dotenv(os.path.expanduser("~/.config/alia/env"))
    load_dotenv()


def main() -> int:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from .setup import run_setup

        return run_setup()
    _load_config()
    return AliaApp().run(None)
