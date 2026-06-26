#!/usr/bin/env bash
# Install ALIA as a user-local app: system deps + a venv + launcher + shortcut.
#
#   ./install.sh
#
# Installs into ~/.local (no sudo for the app itself; sudo is used ONLY to add
# the GTK4/WebKit system libraries, and only if they're missing). The engine
# (lovelaice + lingo + beaver) resolves from PyPI.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${ALIA_PREFIX:-$HOME/.local/share/alia}"
VENV="$PREFIX/venv"
BINDIR="$HOME/.local/bin"
LAUNCHER="$BINDIR/alia"
BINDING="${ALIA_BINDING:-<Super>i}"

say() { printf '  %s\n' "$*"; }

have_gui_deps() {
  python3 - <<'PY' 2>/dev/null
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit  # noqa
PY
}

install_system_deps() {
  if have_gui_deps; then say "✓ GTK 4 + WebKitGTK 6.0 already present"; return; fi
  say "Installing GTK 4 + PyGObject + WebKitGTK 6.0 (needs sudo)…"
  if command -v apt >/dev/null 2>&1; then
    sudo apt update && sudo apt install -y \
      python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-webkit-6.0
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-gobject gtk4 webkitgtk6.0
  else
    echo "Unsupported distro — install GTK 4 + PyGObject + WebKitGTK 6.0 manually." >&2
    exit 1
  fi
}

echo "ALIA installer → $PREFIX"
install_system_deps

say "building venv…"
rm -rf "$VENV"
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install -qU pip
"$VENV/bin/pip" install -q "$REPO_DIR"   # alia + engine from PyPI

mkdir -p "$BINDIR"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" -m alia "\$@"
EOF
chmod +x "$LAUNCHER"
say "✓ launcher: $LAUNCHER"

# Wire .desktop + GNOME shortcut + config template (shared with pip/pipx installs).
ALIA_BINDING="$BINDING" "$LAUNCHER" setup

echo
echo "Done."
echo "  • Configure a key in ~/.config/alia/env (ALIA_API_KEY=…)"
echo "  • Summon with ${BINDING}, or run: alia"
case ":$PATH:" in *":$BINDIR:"*) : ;; *) echo "  • NOTE: add $BINDIR to PATH to run 'alia' directly" ;; esac
