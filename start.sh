#!/usr/bin/env bash
set -e
python3 -m uvicorn bot:web_app --host 0.0.0.0 --port "${PORT:-8080}"
