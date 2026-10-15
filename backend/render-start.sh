#!/usr/bin/env sh
set -eu

: "${PORT:=10000}"
: "${MOCK_BANK_DATABASE_PATH:=/var/data/bank_ledger.db}"
export MOCK_BANK_DATABASE_PATH

python -m uvicorn mock_bank.main:app --host 127.0.0.1 --port 9000 &
bank_pid=$!
api_pid=

cleanup() {
  if [ -n "$api_pid" ]; then
    kill "$api_pid" 2>/dev/null || true
    wait "$api_pid" 2>/dev/null || true
  fi
  kill "$bank_pid" 2>/dev/null || true
  wait "$bank_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

attempt=0
until python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:9000/health', timeout=1)" >/dev/null 2>&1; do
  if ! kill -0 "$bank_pid" 2>/dev/null; then
    echo "Mock bank exited before becoming healthy." >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Mock bank did not become healthy within 30 seconds." >&2
    exit 1
  fi
  sleep 1
done

python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &
api_pid=$!
wait "$api_pid"
