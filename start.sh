#!/bin/bash
set -e

# Newsixity start script — sets up environment and runs frontend + backend in parallel

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "🚀 Starting Newsixity setup & launch..."
echo ""

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENT SETUP
# ============================================================================

echo "🐍 Setting up Python virtual environment..."

if [ ! -d ".venv" ]; then
    echo "   Creating .venv..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate
echo "   ✓ Virtual environment activated"

# Install/update backend dependencies
echo "   Installing backend dependencies..."
cd backend
pip install -q -e ".[dev,integrations]" 2>&1 | grep -v "already satisfied" || true
cd ..
echo "   ✓ Backend dependencies installed"

# ============================================================================
# CACHE CLEANUP
# ============================================================================

echo ""
echo "🧹 Cleaning cache directories..."

# Frontend caches
rm -rf .next .turbo node_modules/.cache 2>/dev/null || true
echo "   ✓ Frontend caches cleared"

# Backend caches
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
echo "   ✓ Backend caches cleared"

# ============================================================================
# DEPENDENCIES
# ============================================================================

echo ""
echo "📦 Installing dependencies..."

# Frontend dependencies
if [ ! -d "node_modules" ] || [ -f "package-lock.json" -a ! -f ".node-modules-installed" ]; then
    echo "   npm: installing..."
    npm ci --legacy-peer-deps 2>&1 | tail -3
    touch .node-modules-installed
else
    echo "   npm: already installed"
fi

echo "   ✓ Dependencies ready"

# ============================================================================
# PORT AVAILABILITY CHECK
# ============================================================================

echo ""
echo "🔌 Checking port availability..."

PORTS_OK=true

if command -v lsof &> /dev/null; then
    if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   ⚠️  Port 3000 in use (kill with: lsof -ti:3000 | xargs kill -9)"
        PORTS_OK=false
    fi

    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   ⚠️  Port 8000 in use (kill with: lsof -ti:8000 | xargs kill -9)"
        PORTS_OK=false
    fi
fi

if [ "$PORTS_OK" = true ]; then
    echo "   ✓ Ports 3000 & 8000 available"
fi

# ============================================================================
# START SERVERS
# ============================================================================

echo ""
echo "📚 Starting backend (FastAPI on :8000)..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Give backend time to start
sleep 2

echo "🎨 Starting frontend (Next.js on :3000)..."
npm run dev &
FRONTEND_PID=$!

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; deactivate 2>/dev/null || true" EXIT

echo ""
echo "✅ Both servers running:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo "   Logs:      Frontend (^C to stop), Backend (/logs endpoint)"
echo ""
echo "Press Ctrl+C to stop both servers and deactivate venv"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
