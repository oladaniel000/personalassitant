#!/usr/bin/env bash
set -e

# Install packages
pip3 install -r requirements.txt

# Write a launcher using the pip3-linked python — guaranteed same environment
PYTHON=$(python3 -c "import sys; print(sys.executable)")
echo "Python executable: $PYTHON"

cat > run.sh << INNER
#!/usr/bin/env bash
set -e
exec ${PYTHON} -m uvicorn bot:web_app --host 0.0.0.0 --port \${PORT:-8080}
INNER

chmod +x run.sh
echo "Launcher written: $(cat run.sh)"
