#!/usr/bin/env bash
set -e

# ============================================================
# Izumi Studio — 统一启动脚本
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# 从 .env 读取端口配置
if [ -f "$ENV_FILE" ]; then
  BACKEND_PORT=$(grep -E '^BACKEND_PORT\s*=' "$ENV_FILE" | head -1 | sed 's/.*=\s*//' | tr -d '"' | tr -d "'" | tr -d ' ')
  FRONTEND_PORT=$(grep -E '^FRONTEND_PORT\s*=' "$ENV_FILE" | head -1 | sed 's/.*=\s*//' | tr -d '"' | tr -d "'" | tr -d ' ')
fi

BACKEND_PORT="${BACKEND_PORT:-8004}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "========================================="
echo "  Izumi Studio 启动"
echo "  后端端口: $BACKEND_PORT"
echo "  前端端口: $FRONTEND_PORT"
echo "========================================="

# 停止旧进程
echo "[1/4] 停止旧进程..."
if command -v cmd >/dev/null 2>&1; then
  # Windows: 杀掉占用端口的进程
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    cmd //c "netstat -ano | findstr :$port | findstr LISTENING" 2>/dev/null | \
      awk '{print $NF}' | sort -u | while read -r pid; do
      [ -n "$pid" ] && cmd //c "taskkill /F /PID $pid" 2>/dev/null || true
    done
  done
else
  # Linux/macOS
  lsof -ti ":$BACKEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
  lsof -ti ":$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
fi
sleep 2

# 启动后端 (在后台)
echo "[2/4] 启动后端 (uvicorn)..."
cd "$SCRIPT_DIR/backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"

# 启动前端 (在后台)
echo "[3/4] 启动前端 (vite)..."
cd "$SCRIPT_DIR/frontend"
npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" &
FRONTEND_PID=$!
echo "  前端 PID: $FRONTEND_PID"

# 等待启动
echo "[4/4] 等待服务就绪..."
sleep 4

# 检查健康状态
echo ""
echo "========================================="
echo "  服务状态检查"
echo "========================================="

if curl -sf "http://localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
  echo "  后端: http://localhost:$BACKEND_PORT ✓"
else
  echo "  后端: http://localhost:$BACKEND_PORT ✗ (启动中...)"
fi

if curl -sf -o /dev/null "http://localhost:$FRONTEND_PORT/" 2>&1; then
  echo "  前端: http://localhost:$FRONTEND_PORT ✓"
else
  echo "  前端: http://localhost:$FRONTEND_PORT ✗ (启动中...)"
fi

echo ""
echo "按 Ctrl+C 停止所有服务"
echo "或运行 ./stop.sh 停止"

# 保存 PID 以便停止脚本使用
echo "$BACKEND_PID" > /tmp/izumi_backend.pid
echo "$FRONTEND_PID" > /tmp/izumi_frontend.pid

# 等待前台进程
wait
