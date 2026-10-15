#!/usr/bin/env bash
# Start Keeper API (8000) and frontend (8080) together.
# Usage (from this folder):
#   ./start.sh
#   bash start.sh
# Stop with Ctrl+C.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -d "$ROOT/backend" || ! -d "$ROOT/frontend" ]]; then
  if [[ -d "$ROOT/Keeper/backend" && -d "$ROOT/Keeper/frontend" ]]; then
    ROOT="$ROOT/Keeper"
  else
    echo "Cannot find backend/ and frontend/ next to this script." >&2
    exit 1
  fi
fi

BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
API_HOST="127.0.0.1"
API_PORT="8000"
FE_HOST="127.0.0.1"
FE_PORT="8080"

is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null || grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null
}

if [[ -x "$BACKEND/.venv/bin/python" ]]; then
  PYTHON="$BACKEND/.venv/bin/python"
elif [[ -x "$BACKEND/.venv/Scripts/python.exe" ]]; then
  if is_wsl; then
    echo "backend/.venv is a Windows virtualenv. WSL bash cannot start it reliably." >&2
    echo "From PowerShell, run:  .\\start.ps1" >&2
    echo "Or use Git Bash:       bash start.sh" >&2
    exit 1
  fi
  PYTHON="$BACKEND/.venv/Scripts/python.exe"
else
  echo "Backend virtualenv not found at backend/.venv" >&2
  echo "Create it first (see README.md), then run this script again." >&2
  exit 1
fi

if [[ ! -f "$BACKEND/.env" ]]; then
  echo "Missing backend/.env — copy backend/.env.example and fill it in." >&2
  exit 1
fi

if [[ ! -f "$FRONTEND/.env" ]]; then
  echo "Missing frontend/.env — copy frontend/.env.example and fill it in." >&2
  exit 1
fi

if command -v npm >/dev/null 2>&1; then
  NPM=(npm)
elif command -v npm.cmd >/dev/null 2>&1; then
  NPM=(npm.cmd)
else
  echo "npm is not installed or not on PATH." >&2
  exit 1
fi

PIDS=()

cleanup() {
  trap - EXIT INT TERM
  echo
  echo "Stopping Keeper..."
  local pid
  for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait "${PIDS[@]+"${PIDS[@]}"}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting Keeper API on http://${API_HOST}:${API_PORT}"
(
  cd "$BACKEND"
  exec "$PYTHON" -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT"
) &
PIDS+=($!)

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND" && "${NPM[@]}" install)
fi

echo "Starting frontend on http://localhost:${FE_PORT}"
(
  cd "$FRONTEND"
  # Lovable/Vite defaults to 8080, not 3000. Pin it so CORS matches the backend.
  exec "${NPM[@]}" run dev -- --host "$FE_HOST" --port "$FE_PORT" --strictPort
) &
PIDS+=($!)

echo
echo "Keeper is running:"
echo "  Frontend   http://localhost:${FE_PORT}"
echo "  API        http://${API_HOST}:${API_PORT}"
echo "  Mock bank  embedded at http://${API_HOST}:${API_PORT}/_internal/mock-bank"
echo
echo "Press Ctrl+C to stop all services."

fail=0
for pid in "${PIDS[@]}"; do
  if ! wait "$pid"; then
    fail=1
  fi
done
exit "$fail"
