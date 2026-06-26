"""The ALIA HUD — a borderless GNOME overlay you summon with a key.

Minimal slice: a transcript view + an input entry. Enter sends, Esc hides.
Closing hides too (the app stays resident in the background).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

_CSS = b"""
.alia-hud { background-color: rgba(20, 22, 28, 0.92); border-radius: 16px; }
.alia-header { font-weight: 700; color: #d7c9ff; }
.alia-dot { color: #9b7dff; font-size: 16px; }
.alia-transcript { background: transparent; color: #e8e8ec; padding: 8px; font-size: 14px; }
.alia-entry { background: rgba(255,255,255,0.06); color: #ffffff; border-radius: 10px; padding: 8px; }
.alia-approval { background: rgba(155,125,255,0.14); border-radius: 10px; padding: 8px; }
.alia-cmd { font-family: monospace; color: #ffd28a; }
"""


class HudWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="ALIA")
        self.app = app

        self.set_decorated(False)
        self.set_default_size(640, 460)
        self.add_css_class("alia-hud")

        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(14)
        root.set_margin_bottom(14)
        root.set_margin_start(16)
        root.set_margin_end(16)
        self.set_child(root)
        self.root = root

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dot = Gtk.Label(label="●")
        dot.add_css_class("alia-dot")
        title = Gtk.Label(label="ALIA")
        title.add_css_class("alia-header")
        header.append(dot)
        header.append(title)
        root.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.view = Gtk.TextView()
        self.view.set_editable(False)
        self.view.set_cursor_visible(False)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.add_css_class("alia-transcript")
        self.buffer = self.view.get_buffer()
        scroll.set_child(self.view)
        root.append(scroll)

        # Holder for the inline approval bar (shown only while a command waits).
        self.approval_holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self.approval_holder)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Habla con ALIA…  (Enter envía · Esc cierra)")
        self.entry.add_css_class("alia-entry")
        self.entry.connect("activate", self._on_submit)
        root.append(self.entry)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

        # Hide instead of destroy, so the agent stays resident.
        self.connect("close-request", self._on_close)

        self._busy = False
        self._greet()

    # ---- presence / visibility --------------------------------------------

    def toggle(self) -> None:
        if self.get_visible():
            self.set_visible(False)
        else:
            self.present()
            self.entry.grab_focus()

    def _on_close(self, *_args) -> bool:
        self.set_visible(False)
        return True  # stop the default destroy

    def _on_key(self, _ctrl, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.set_visible(False)
            return True
        return False

    # ---- conversation -------------------------------------------------------

    def _greet(self) -> None:
        from .agent import api_key_configured

        self._append("ALIA", "Hola. Soy ALIA — estoy aquí.")
        if not api_key_configured():
            self._append(
                "ALIA",
                "(aún no tengo una API key configurada — exporta ALIA_API_KEY "
                "o OPENROUTER_API_KEY antes de iniciarme para poder responder.)",
            )

    def _append(self, who: str, text: str) -> None:
        end = self.buffer.get_end_iter()
        prefix = "\n" if self.buffer.get_char_count() else ""
        self.buffer.insert(end, f"{prefix}{who}: {text}\n")
        self._scroll_to_end()

    def _append_token(self, token: str) -> None:
        self.buffer.insert(self.buffer.get_end_iter(), token)
        self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        mark = self.buffer.create_mark(None, self.buffer.get_end_iter(), False)
        self.view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

    def _on_submit(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if not text or self._busy:
            return
        entry.set_text("")
        self._busy = True
        self._append("Tú", text)
        # open ALIA's line; tokens stream into it
        self.buffer.insert(self.buffer.get_end_iter(), "\nALIA: ")
        self.app.submit(text, self._append_token, self._on_reply_done)

    def _on_reply_done(self, _reply: str) -> None:
        self.buffer.insert(self.buffer.get_end_iter(), "\n")
        self._busy = False
        self._scroll_to_end()

    # ---- tools & approval ---------------------------------------------------

    def on_tool_event(self, kind: str, params: dict) -> None:
        """Render tool activity from ACP session/update notifications."""
        if kind == "tool_call":
            title = params.get("title", "tool")
            raw = params.get("rawInput") or {}
            detail = raw.get("command") or raw.get("path") or ""
            self._append_dim(f"→ {title}: {detail}".rstrip(": "))
        elif kind == "tool_call_update":
            if params.get("status") == "completed":
                self._append_dim("  ✓ done")
            else:
                err = ""
                content = params.get("content") or []
                if content and isinstance(content[0], dict):
                    err = content[0].get("text", "")
                self._append_dim(f"  ✗ {err or 'failed'}")

    def _append_dim(self, text: str) -> None:
        self.buffer.insert(self.buffer.get_end_iter(), f"\n{text}")
        self._scroll_to_end()

    def ask_approval(self, tool_name: str, arguments: dict, resolve) -> bool:
        """Show an inline approval bar for a gated tool call; resolve(bool) on click.

        Runs on the GTK thread (via idle_add). Returns False to satisfy
        GLib.idle_add (one-shot).
        """
        self.present()
        command = arguments.get("command", "")
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bar.add_css_class("alia-approval")

        prompt = Gtk.Label(label=f"Run this {tool_name} command?", xalign=0.0)
        cmd = Gtk.Label(label=command, xalign=0.0, wrap=True, selectable=True)
        cmd.add_css_class("alia-cmd")
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          halign=Gtk.Align.END)
        approve = Gtk.Button(label="Approve")
        deny = Gtk.Button(label="Deny")
        buttons.append(deny)
        buttons.append(approve)
        bar.append(prompt)
        bar.append(cmd)
        bar.append(buttons)
        self.approval_holder.append(bar)

        def decide(decision: bool) -> None:
            self.approval_holder.remove(bar)
            resolve(decision)

        approve.connect("clicked", lambda _b: decide(True))
        deny.connect("clicked", lambda _b: decide(False))
        approve.grab_focus()
        return False
