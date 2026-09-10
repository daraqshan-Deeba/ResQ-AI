#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================"
echo "        ResQ AI Starting..."
echo "======================================"

echo ""
echo "[1/2] Starting backend..."

cd "$PROJECT_ROOT/backend"

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Backend started:"
echo "http://127.0.0.1:8000"
echo "Swagger:"
echo "http://127.0.0.1:8000/docs"

echo ""
echo "[2/2] Starting frontend..."

cd "$PROJECT_ROOT/frontend"

python -m http.server 5500 --bind 127.0.0.1 &
FRONTEND_PID=$!

echo "Frontend started:"
echo "http://127.0.0.1:5500/dashboard.html"

echo ""
echo "======================================"
echo "        ResQ AI is running"
echo "======================================"
echo ""
echo "Frontend : http://127.0.0.1:5500/dashboard.html"
echo "Backend  : http://127.0.0.1:8000"
echo "Swagger  : http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

cleanup() {
    echo ""
    echo "Stopping ResQ AI..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM

wait