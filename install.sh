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
APPDIR="$HOME/.local/share/applications"
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

install_shortcut() {
  command -v gsettings >/dev/null 2>&1 || { say "gsettings absent — set a shortcut manually"; return; }
  local base="org.gnome.settings-daemon.plugins.media-keys"
  local kp="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/alia/"
  python3 - "$base" "$kp" <<'PY'
import ast, subprocess, sys
base, kp = sys.argv[1], sys.argv[2]
cur = subprocess.check_output(["gsettings", "get", base, "custom-keybindings"]).decode().strip()
try:
    items = ast.literal_eval(cur) if cur and cur != "@as []" else []
except (ValueError, SyntaxError):
    items = []
if kp not in items:
    items.append(kp)
subprocess.check_call(["gsettings", "set", base, "custom-keybindings", str(items)])
PY
  local schema="${base}.custom-keybinding:${kp}"
  gsettings set "$schema" name "ALIA"
  gsettings set "$schema" command "$LAUNCHER"
  gsettings set "$schema" binding "$BINDING"
  say "✓ shortcut: $BINDING → alia"
}

echo "ALIA installer → $PREFIX"
install_system_deps

say "building venv…"
rm -rf "$VENV"
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install -qU pip
"$VENV/bin/pip" install -q "$REPO_DIR"   # alia + engine from PyPI

mkdir -p "$BINDIR" "$APPDIR"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" -m alia "\$@"
EOF
chmod +x "$LAUNCHER"
say "✓ launcher: $LAUNCHER"

cat > "$APPDIR/alia.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ALIA
Comment=The cognitive partner of the AI-n-Box desktop
Exec=$LAUNCHER
Terminal=false
Categories=Utility;
EOF
say "✓ desktop entry"

install_shortcut

echo
echo "Done."
echo "  • Configure a key: export ALIA_API_KEY (or ~/.config/alia/env)"
echo "  • Summon with ${BINDING}, or run: alia"
case ":$PATH:" in *":$BINDIR:"*) : ;; *) echo "  • NOTE: add $BINDIR to PATH to run 'alia' directly" ;; esac
