#!/usr/bin/env bash
set -e

# Find whatever python is available and run uvicorn through it
if command -v python3 &>/dev/null; then
    exec python3 -m uvicorn bot:web_app --host 0.0.0.0 --port "${PORT:-8080}"
elif command -v python &>/dev/null; then
    exec python -m uvicorn bot:web_app --host 0.0.0.0 --port "${PORT:-8080}"
else
    # Last resort: find it in the virtualenv
    exec /opt/render/project/src/.venv/bin/python -m uvicorn bot:web_app --host 0.0.0.0 --port "${PORT:-8080}"
fi
