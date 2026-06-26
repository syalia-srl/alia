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
        self.agent = AliaAgent()

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def do_activate(self) -> None:
        if self.window is None:
            self.window = HudWindow(self)
        self.window.toggle()

    def submit(self, text, on_token, on_done) -> None:
        """Run one agent turn off the GTK thread, marshalling results back to it."""
        assert self.agent is not None and self._loop is not None
        self.agent.set_on_token(lambda tok: GLib.idle_add(on_token, tok))
        future = asyncio.run_coroutine_threadsafe(self.agent.chat(text), self._loop)

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
    _load_config()
    return AliaApp().run(None)
