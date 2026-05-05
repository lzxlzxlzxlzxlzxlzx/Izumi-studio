#!/bin/bash
# Start/Restart the backend server on port 8004
# Usage: ./run.sh         (start)
#        ./run.sh restart (restart)

PORT=8004
PID=""

# Find any process listening on the target port
PID=$(netstat -ano 2>/dev/null | grep ":$PORT " | grep LISTEN | awk '{print $5}' | head -1)

if [ -n "$PID" ]; then
    echo "[run] Port $PORT is in use by PID $PID, killing..."
    # Try graceful first, then force
    taskkill //PID "$PID" 2>/dev/null || true
    sleep 1
    taskkill //F //PID "$PID" 2>/dev/null || true
    sleep 1
fi

cd "$(dirname "$0")" || exit 1
echo "[run] Starting uvicorn on port $PORT..."
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info \
    > ../data/logs/backend.log 2>&1 &
sleep 2

# Verify
PID=$!
if kill -0 "$PID" 2>/dev/null; then
    echo "[run] Backend started (PID $PID), log: backend.log"
else
    echo "[run] Failed to start backend"
    exit 1
fi
