"""The ALIA HUD — a borderless GNOME overlay you summon with a key.

Transcript is a WebKitGTK WebView (real markdown + syntax highlighting, reusing
superbot's marked/highlight assets). The input entry and the Approve/Deny bar
stay native GTK below it. Enter sends, Esc hides; closing hides (the app stays
resident). Input is locked while a turn runs; an in-page spinner shows activity.
"""

from __future__ import annotations

import json
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gtk, WebKit  # noqa: E402

_STATIC = Path(__file__).parent / "static"
_TRANSCRIPT_URI = (_STATIC / "transcript.html").as_uri()

_CSS = b"""
.alia-hud { background-color: rgba(17, 19, 23, 0.96); border-radius: 16px; }
.alia-header { font-weight: 700; color: #d7c9ff; }
.alia-dot { color: #9b7dff; font-size: 16px; }
.alia-entry { background: rgba(255,255,255,0.06); color: #ffffff; border-radius: 10px; padding: 8px; }
.alia-approval { background: rgba(155,125,255,0.14); border-radius: 10px; padding: 8px; }
.alia-cmd { font-family: monospace; color: #ffd28a; }
"""


class HudWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="ALIA")
        self.app = app
        self.set_decorated(False)
        self.set_default_size(660, 520)
        self.add_css_class("alia-hud")

        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for m in ("top", "bottom", "start", "end"):
            getattr(root, f"set_margin_{m}")(14)
        self.set_child(root)
        self.root = root

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dot = Gtk.Label(label="●"); dot.add_css_class("alia-dot")
        title = Gtk.Label(label="ALIA"); title.add_css_class("alia-header")
        header.append(dot); header.append(title)
        header.append(Gtk.Box(hexpand=True))  # spacer
        self.voice_out_btn = Gtk.ToggleButton(label="🔊")
        self.voice_out_btn.set_active(True)
        self.voice_out_btn.set_tooltip_text("Speak replies aloud")
        self.mic_btn = Gtk.Button(label="🎤")
        self.mic_btn.set_tooltip_text("Talk to ALIA (click to start/stop)")
        self.mic_btn.connect("clicked", self._on_mic)
        header.append(self.voice_out_btn)
        header.append(self.mic_btn)
        root.append(header)

        # Transcript: WebKit WebView.
        self.web = WebKit.WebView()
        self.web.set_vexpand(True)
        self.web.set_background_color(Gdk.RGBA(red=0.067, green=0.075, blue=0.090, alpha=1.0))
        settings = self.web.get_settings()
        settings.set_property("allow-file-access-from-file-urls", True)
        settings.set_property("enable-developer-extras", True)
        self._ready = False
        self._pending: list[str] = []
        self.web.connect("load-changed", self._on_load_changed)
        self.web.load_uri(_TRANSCRIPT_URI)
        root.append(self.web)

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
        self.connect("close-request", self._on_close)

        self._busy = False
        self._listening = False
        self._last_was_voice = False

    # ---- JS bridge ----------------------------------------------------------

    def _on_load_changed(self, _web, event) -> None:
        if event == WebKit.LoadEvent.FINISHED:
            self._ready = True
            for js in self._pending:
                self._eval(js)
            self._pending.clear()
            self._greet()

    def _eval(self, js: str) -> None:
        self.web.evaluate_javascript(js, -1, None, None, None, None)

    def _js(self, js: str) -> None:
        if self._ready:
            self._eval(js)
        else:
            self._pending.append(js)

    def _call(self, fn: str, *args) -> None:
        packed = ", ".join(json.dumps(a) for a in args)
        self._js(f"{fn}({packed});")

    # ---- visibility ---------------------------------------------------------

    def toggle(self) -> None:
        if self.get_visible():
            self.set_visible(False)
        else:
            self.present()
            self.entry.grab_focus()

    def _on_close(self, *_a) -> bool:
        self.set_visible(False)
        return True

    def _on_key(self, _c, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.set_visible(False)
            return True
        return False

    # ---- conversation -------------------------------------------------------

    def _greet(self) -> None:
        from .agent import api_key_configured

        self._call("aliaAddAssistant", "Hola. Soy ALIA — estoy aquí.")
        if not api_key_configured():
            self._call(
                "aliaAddAssistant",
                "*(aún no tengo una API key configurada — exporta `ALIA_API_KEY` "
                "o `OPENROUTER_API_KEY` antes de iniciarme para poder responder.)*",
            )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.entry.set_sensitive(not busy)  # input lock; turn timer shows activity
        if not busy:
            self.entry.grab_focus()  # ready to type again, no click needed

    def _on_submit(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if not text or self._busy:
            return
        entry.set_text("")
        self._last_was_voice = False
        self._submit_text(text)

    def _submit_text(self, text: str) -> None:
        self._call("aliaAddUser", text)
        self._call("aliaBeginTurn")  # ALIA header + live turn timer; tools nest under it
        self._set_busy(True)
        self.app.submit(text, self._on_token, self._on_reply_done)

    # ---- voice -------------------------------------------------------------

    def _on_mic(self, _btn) -> None:
        if self._busy:
            return
        if not self._listening:
            self._listening = True
            self.mic_btn.set_label("●")
            self.entry.set_sensitive(False)
            self.entry.set_text("")
            self.entry.set_placeholder_text("Escuchando…  (clic para terminar)")
            self.app.start_listening(self._on_voice_partial, self._on_listen_ready)
        else:
            self._listening = False
            self.mic_btn.set_label("🎤")
            self.entry.set_placeholder_text("Procesando voz…")
            self.app.stop_listening(self._on_voice_final)

    def _on_listen_ready(self, ok: bool, err: str) -> bool:
        if not ok:
            self._listening = False
            self.mic_btn.set_label("🎤")
            self.entry.set_sensitive(True)
            self.entry.set_placeholder_text("Habla con ALIA…  (Enter envía · Esc cierra)")
            self._call("aliaAddAssistant", f"*(no pude usar el micrófono: {err})*")
        return False

    def _on_voice_partial(self, text: str) -> bool:
        self.entry.set_text(text)  # live transcription in the input
        return False

    def _on_voice_final(self, text: str) -> bool:
        self.entry.set_sensitive(True)
        self.entry.set_placeholder_text("Habla con ALIA…  (Enter envía · Esc cierra)")
        text = (text or "").strip()
        self.entry.set_text("")
        if text:
            self._last_was_voice = True
            self._submit_text(text)  # auto-send
        return False

    def _on_token(self, chunk: str) -> None:
        # Each chunk is a finalized assistant message; render in arrival order
        # so text and tool rows interleave correctly within the turn.
        if chunk:
            self._call("aliaAddAssistant", chunk)

    def _on_reply_done(self, reply: str) -> None:
        self._call("aliaEndTurn")
        self._set_busy(False)
        # Modality mirroring: if you spoke, she speaks back (unless muted).
        if self._last_was_voice and self.voice_out_btn.get_active() and reply.strip():
            self.app.speak(reply)

    # ---- tools & approval ---------------------------------------------------

    def on_tool_event(self, kind: str, params: dict) -> None:
        call_id = params.get("toolCallId", "")
        if kind == "tool_call":
            raw = params.get("rawInput") or {}
            detail = raw.get("command") or raw.get("path") or ""
            self._call("aliaAddTool", call_id, params.get("title", "tool"), detail)
        elif kind == "tool_call_update":
            status = "done" if params.get("status") == "completed" else "failed"
            self._call("aliaEndTool", call_id, status)

    def ask_approval(self, tool_name: str, arguments: dict, resolve) -> bool:
        """Inline approval bar for a gated command. resolve("deny"|"once"|"session")."""
        from .policy import approval_prefix

        self.present()
        command = arguments.get("command", "")
        prefix = approval_prefix(command)
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bar.add_css_class("alia-approval")

        prompt = Gtk.Label(label="Ejecutar este comando?", xalign=0.0)
        cmd = Gtk.Label(label=command, xalign=0.0, wrap=True, selectable=True)
        cmd.add_css_class("alia-cmd")
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                          halign=Gtk.Align.END)
        deny = Gtk.Button(label="Denegar")
        once = Gtk.Button(label="Aprobar")
        always = Gtk.Button(label=f"Permitir «{prefix}» esta sesión")
        buttons.append(deny); buttons.append(always); buttons.append(once)
        bar.append(prompt); bar.append(cmd); bar.append(buttons)
        self.approval_holder.append(bar)

        def decide(decision: str) -> None:
            self.approval_holder.remove(bar)
            resolve(decision)

        deny.connect("clicked", lambda _b: decide("deny"))
        once.connect("clicked", lambda _b: decide("once"))
        always.connect("clicked", lambda _b: decide("session"))
        once.grab_focus()
        return False
