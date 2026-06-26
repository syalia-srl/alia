#!/usr/bin/env bash
# Register a GNOME custom keyboard shortcut that summons ALIA.
#
# Default binding: <Super>a  (the bare Super key is reserved by GNOME for the
# Activities overview and can't be cleanly rebound here — that's a follow-up).
# Override with:  BINDING='<Super>space' ./scripts/install-shortcut.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BINDING="${BINDING:-<Super>a}"
COMMAND="${REPO_DIR}/.venv/bin/python -m alia"
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
