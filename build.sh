#!/usr/bin/env bash
set -e
python3 -m venv /opt/render/project/venv
/opt/render/project/venv/bin/pip install --upgrade pip -q
/opt/render/project/venv/bin/pip install -r requirements.txt -q
echo "Build complete"
