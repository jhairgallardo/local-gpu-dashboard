#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"

cd "$PROJECT_DIR"

is_enabled() {
  [[ "${1:-}" =~ ^(1|true|TRUE|yes|YES|on|ON|enable|ENABLE|enabled|ENABLED|show|SHOW|visible|VISIBLE|demo|DEMO)$ ]]
}

is_disabled() {
  [[ "${1:-}" =~ ^(0|false|FALSE|no|NO|off|OFF|disable|DISABLE|disabled|DISABLED|hide|HIDE|hidden|HIDDEN)$ ]]
}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: Python 3 was not found. Install Python 3 or set PYTHON_BIN to a valid interpreter." >&2
  exit 1
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "Error: PORT must be a number between 1 and 65535." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating local Python virtual environment in .venv..."
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck source=/dev/null
. .venv/bin/activate

echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "Starting GPU Usage Dashboard"
echo "Dashboard: http://${HOST}:${PORT}"
echo "Health:    http://${HOST}:${PORT}/health"
if is_enabled "${DEMO_MODE:-}"; then
  echo "Demo:      enabled (synthetic telemetry)"
fi
if [ "$HOST" != "127.0.0.1" ] && [ "$HOST" != "localhost" ]; then
  echo "Warning:  HOST=${HOST} may expose local process and GPU data beyond this machine."
fi
if is_disabled "${SHOW_PROCESS_DETAILS:-1}"; then
  echo "Privacy:  process details hidden"
else
  if is_disabled "${SHOW_COMMAND_LINES:-1}"; then
    echo "Privacy:  process command lines hidden"
  fi
  if is_disabled "${SHOW_USERNAMES:-1}"; then
    echo "Privacy:  process usernames hidden"
  fi
fi
echo

exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
