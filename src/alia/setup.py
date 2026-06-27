"""`alia setup` — make a pip/pipx-installed ALIA usable on the desktop.

pipx/pip only install the `alia` command; this wires the GNOME pieces that a
package install can't: the `<Super>i` shortcut, the .desktop entry, a config
template, and a dependency check.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

BINDING = os.environ.get("ALIA_BINDING", "<Super>i")
_DESKTOP = Path.home() / ".local/share/applications/alia.desktop"
_CONFIG = Path.home() / ".config/alia/env"
_MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
_KEYPATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/alia/"


def _launcher() -> str:
    return shutil.which("alia") or os.path.abspath(sys.argv[0])


def _check_deps() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import Gtk, WebKit  # noqa: F401

        print("  ✓ GTK 4 + WebKitGTK 6.0 present")
        ok = True
    except (ImportError, ValueError) as exc:
        print(f"  ✗ missing GTK 4 / WebKitGTK 6.0 (HUD): {exc}")
        print("    Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0")
        print("    Fedora:        sudo dnf install python3-gobject gtk4 webkitgtk6.0")
        print("    (then reinstall: pipx install --system-site-packages alia-ai)")
        ok = False

    import ctypes.util
    import shutil

    missing = [n for n, p in (("PortAudio", ctypes.util.find_library("portaudio")),
                              ("espeak-ng", shutil.which("espeak-ng"))) if not p]
    if missing:
        print(f"  ! voice needs {', '.join(missing)} (optional)")
        print("    Ubuntu/Debian: sudo apt install libportaudio2 espeak-ng")
        print("    Fedora:        sudo dnf install portaudio espeak-ng")
    else:
        print("  ✓ PortAudio + espeak-ng present (voice ready)")
    return ok


def _write_desktop(launcher: str) -> None:
    _DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    _DESKTOP.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ALIA\n"
        "Comment=The cognitive partner of the AI-n-Box desktop\n"
        f"Exec={launcher}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
    )
    print(f"  ✓ desktop entry: {_DESKTOP}")


def _install_shortcut(launcher: str) -> None:
    if not shutil.which("gsettings"):
        print("  ! gsettings not found — set a shortcut manually")
        return
    cur = subprocess.check_output(
        ["gsettings", "get", _MEDIA_KEYS, "custom-keybindings"]).decode().strip()
    try:
        items = ast.literal_eval(cur) if cur and cur != "@as []" else []
    except (ValueError, SyntaxError):
        items = []
    if _KEYPATH not in items:
        items.append(_KEYPATH)
        subprocess.check_call(
            ["gsettings", "set", _MEDIA_KEYS, "custom-keybindings", str(items)])
    schema = f"{_MEDIA_KEYS}.custom-keybinding:{_KEYPATH}"
    subprocess.check_call(["gsettings", "set", schema, "name", "ALIA"])
    subprocess.check_call(["gsettings", "set", schema, "command", launcher])
    subprocess.check_call(["gsettings", "set", schema, "binding", BINDING])
    print(f"  ✓ shortcut: {BINDING} → {launcher}")


def _ensure_config() -> None:
    if _CONFIG.exists():
        print(f"  ✓ config present: {_CONFIG}")
        return
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG.write_text(
        "# ALIA config — any OpenAI-compatible endpoint\n"
        "# ALIA_API_KEY=sk-or-...\n"
        "# ALIA_MODEL=anthropic/claude-haiku-4.5\n"
        "# ALIA_BASE_URL=https://openrouter.ai/api/v1\n"
    )
    print(f"  ✓ config template: {_CONFIG}  (add your ALIA_API_KEY)")


def run_setup() -> int:
    print("ALIA setup")
    launcher = _launcher()
    _check_deps()
    _write_desktop(launcher)
    _install_shortcut(launcher)
    _ensure_config()
    print(f"\nDone. Summon with {BINDING}  (or run: alia)")
    return 0
