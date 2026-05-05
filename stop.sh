#!/usr/bin/env bash

# ============================================================
# Izumi Studio — 停止脚本
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

echo "停止 Izumi Studio..."

if command -v cmd >/dev/null 2>&1; then
  # Windows: 通过端口杀掉进程
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    echo "  检查端口 $port..."
    cmd //c "netstat -ano | findstr :$port | findstr LISTENING" 2>/dev/null | \
      awk '{print $NF}' | sort -u | while read -r pid; do
      if [ -n "$pid" ]; then
        echo "  停止 PID $pid (端口 $port)"
        cmd //c "taskkill /F /PID $pid" 2>/dev/null || true
      fi
    done
  done
else
  # Linux/macOS
  lsof -ti ":$BACKEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "  后端 (端口 $BACKEND_PORT) 已停止" || echo "  后端未运行"
  lsof -ti ":$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null && echo "  前端 (端口 $FRONTEND_PORT) 已停止" || echo "  前端未运行"
fi

# 清理 PID 文件
rm -f /tmp/izumi_backend.pid /tmp/izumi_frontend.pid

echo "完成"
