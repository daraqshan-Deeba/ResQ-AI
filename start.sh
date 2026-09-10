#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================"
echo "        ResQ AI Starting..."
echo "======================================"

echo ""
echo "[1/2] Starting Flask backend..."

cd "$PROJECT_ROOT/backend"

python run.py &
BACKEND_PID=$!

echo "Backend started:"
echo "http://127.0.0.1:8001"
echo "Health:"
echo "http://127.0.0.1:8001/health"

echo ""
echo "[2/2] Starting Next.js frontend..."

cd "$PROJECT_ROOT/frontend"

npm run dev -- --hostname 127.0.0.1 --port 3000 &
FRONTEND_PID=$!

echo "Frontend started:"
echo "http://127.0.0.1:3000"

echo ""
echo "======================================"
echo "        ResQ AI is running"
echo "======================================"
echo ""
echo "Frontend : http://127.0.0.1:3000"
echo "Backend  : http://127.0.0.1:8001"
echo ""
echo "Press Ctrl+C to stop both servers."

cleanup() {
    echo ""
    echo "Stopping ResQ AI..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM

wait
