#!/usr/bin/env sh
set -eu

: "${PORT:=10000}"
export PORT
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
