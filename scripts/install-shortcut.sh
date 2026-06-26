#!/usr/bin/env bash
# Register a GNOME custom keyboard shortcut that summons ALIA.
#
# Default binding: <Super>i  (mnemonic for IA). Note that many obvious combos
# are already grabbed and won't fire a custom shortcut:
#   - the bare Super key      -> GNOME Activities overview
#   - <Super>space            -> ibus input-source switch (independent grabber)
#   - F12                     -> often a terminal-dropdown shortcut
# If your chosen binding does nothing, it's almost certainly already taken.
# Override with:  BINDING='<Super>j' ./scripts/install-shortcut.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BINDING="${BINDING:-<Super>i}"
# Launch via the wrapper (logs each fire to /tmp/alia-launch.log; handy for
# diagnosing whether the shortcut fired at all).
COMMAND="${REPO_DIR}/scripts/alia-launch.sh"
SLOT="alia"
BASE="org.gnome.settings-daemon.plugins.media-keys"
PATH_PREFIX="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
KEYPATH="${PATH_PREFIX}/${SLOT}/"

if ! command -v gsettings >/dev/null 2>&1; then
  echo "gsettings not found — are you on GNOME?" >&2
  exit 1
fi

# Append our slot to the custom-keybindings list without clobbering existing ones.
python3 - "$BASE" "$KEYPATH" <<'PY'
import ast, subprocess, sys
base, keypath = sys.argv[1], sys.argv[2]
cur = subprocess.check_output(["gsettings", "get", base, "custom-keybindings"]).decode().strip()
try:
    items = ast.literal_eval(cur) if cur and cur != "@as []" else []
except (ValueError, SyntaxError):
    items = []
if keypath not in items:
    items.append(keypath)
subprocess.check_call(["gsettings", "set", base, "custom-keybindings", str(items)])
PY

SCHEMA="${BASE}.custom-keybinding:${KEYPATH}"
gsettings set "$SCHEMA" name "ALIA"
gsettings set "$SCHEMA" command "$COMMAND"
gsettings set "$SCHEMA" binding "$BINDING"

echo "Bound ${BINDING} → ${COMMAND}"
echo "Change it in Settings → Keyboard → Custom Shortcuts, or re-run with BINDING=..."
