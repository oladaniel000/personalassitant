#!/usr/bin/env bash
set -e
pip install -r requirements.txt
echo "Build complete"
echo "Python: $(python3 --version)"
python3 -c "import sqlalchemy; print('SQLAlchemy OK:', sqlalchemy.__version__)"
python3 -c "import uvicorn; print('uvicorn OK:', uvicorn.__version__)"
