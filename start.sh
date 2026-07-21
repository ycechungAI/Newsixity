#!/bin/bash
set -e

# Newsixity start script — runs frontend (Next.js) and backend (FastAPI) in parallel

echo "🚀 Starting Newsixity..."

# Check if processes are already running
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 3000 already in use (Next.js may be running)"
fi

if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 8000 already in use (FastAPI may be running)"
fi

# Start backend (FastAPI)
echo "📚 Starting backend (FastAPI on :8000)..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend (Next.js)
echo "🎨 Starting frontend (Next.js on :3000)..."
cd ..
npm run dev &
FRONTEND_PID=$!

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT

echo "✅ Both servers started:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
