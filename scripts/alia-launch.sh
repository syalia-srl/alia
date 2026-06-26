#!/usr/bin/env bash
# Launcher used by the GNOME keybinding. Logs each invocation (so we can tell
# whether the shortcut fired at all) then hands off to the resident app.
LOG="${ALIA_LAUNCH_LOG:-/tmp/alia-launch.log}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
{
  echo "----"
  echo "$(date '+%F %T') fired | WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-} DISPLAY=${DISPLAY:-} DBUS=${DBUS_SESSION_BUS_ADDRESS:-}"
} >> "$LOG" 2>&1
exec "${REPO_DIR}/.venv/bin/python" -m alia >> "$LOG" 2>&1
