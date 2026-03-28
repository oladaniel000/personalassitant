#!/usr/bin/env bash
set -e
pip install -r requirements.txt
echo "Build complete. Python: $(python3 --version)"
echo "uvicorn: $(python3 -m uvicorn --version)"
