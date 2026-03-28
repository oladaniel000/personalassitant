#!/usr/bin/env bash
set -e
exec /opt/render/project/venv/bin/python -m uvicorn bot:web_app --host 0.0.0.0 --port "${PORT:-8080}"
