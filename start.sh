#!/bin/bash
set -e

# Newsixity start script — sets up environment and runs frontend + backend in parallel.
#
# Cross-platform (macOS / Linux / Arch / Ubuntu / Windows via Git Bash):
#   * finds a modern Python (>= 3.11) — older system pythons (e.g. the macOS
#     3.9.6 shim) are too old for the backend's hatchling build backend
#   * creates/rebuilds the project venv with it, upgrading pip so the PEP 660
#     editable install works
#   * locates npm/node (nvm included) even when the calling shell doesn't
#     have it on PATH
#   * starts backend + frontend, adapting to the platform's venv layout

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ── Platform detection ────────────────────────────────────────────────────
IS_WINDOWS=0
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WINDOWS=1 ;;
esac
IS_LINUX=0
[ "$(uname -s)" = "Linux" ] && IS_LINUX=1

echo "🚀 Starting Newsixity setup & launch..."
echo ""

# ============================================================================
# PYTHON SELECTION (>= 3.11 only)
# ============================================================================

echo "🐍 Locating a modern Python (>= 3.11)..."

PYTHON_CANDIDATES=(
  "${NEWSIXITY_PYTHON:-}"
  python3.14 python3.13 python3.12 python3.11
  python3 python
)
# On Git Bash, prefer the Windows Python installs used by the build scripts.
if [ "$IS_WINDOWS" = 1 ]; then
  PYTHON_CANDIDATES=( "${NEWSIXITY_PYTHON:-}" python py python3.14 python3.13 python3.12 python3.11 python3 )
fi

PYTHON=""
for candidate in "${PYTHON_CANDIDATES[@]}"; do
  [ -z "$candidate" ] && continue
  if command -v "$candidate" >/dev/null 2>&1; then
    # Reject < 3.11: the backend requires >= 3.11 and hatchling (PEP 660).
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "   ❌ No Python >= 3.11 found." >&2
  echo "   Install one and/or set NEWSIXITY_PYTHON to its path:" >&2
  echo "     macOS:   brew install python@3.12" >&2
  echo "     Ubuntu:  sudo apt install python3 python3-venv python3-pip" >&2
  echo "     Arch:    sudo pacman -S python python-pip" >&2
  echo "     Windows: python.org installer (or NEWSIXITY_PYTHON=/c/Python312/python.exe)" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON" --version 2>&1 | sed -E 's/^Python //')"
echo "   ✓ Using $PYTHON ($PYTHON_VERSION)"

# venv layout differs by platform.
if [ "$IS_WINDOWS" = 1 ]; then
  VENV_PY="$REPO_ROOT/.venv/Scripts/python.exe"
  VENV_ACTIVATE="$REPO_ROOT/.venv/Scripts/activate"
else
  VENV_PY="$REPO_ROOT/.venv/bin/python"
  VENV_ACTIVATE="$REPO_ROOT/.venv/bin/activate"
fi

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENT SETUP
# ============================================================================

echo "🐍 Setting up Python virtual environment..."

# venv's activate script/shebangs bake in an absolute path at creation time.
# If this folder was renamed or moved since, those paths point nowhere and
# every python/pip/uvicorn invocation breaks with "bad interpreter". Detect
# that mismatch and rebuild .venv automatically instead of failing.
if [ -d ".venv" ]; then
    # Take everything after the first '=' and strip optional surrounding
    # quotes. Modern venvs (Python >= 3.14) write this line with an `export`
    # prefix (`export VIRTUAL_ENV=/path`); older ones wrote it bare
    # (`VIRTUAL_ENV=/path`). Match both, and read it from the platform's own
    # activate path so the check works on Windows (Scripts/) too.
    VENV_RECORDED_PATH="$(grep -m1 -E '^(export[[:space:]]+)?VIRTUAL_ENV=' "$VENV_ACTIVATE" 2>/dev/null \
        | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//")"
    if [ "$VENV_RECORDED_PATH" != "$REPO_ROOT/.venv" ]; then
        echo "   ⚠️  .venv points at a stale path (folder renamed/moved) — rebuilding..."
        rm -rf .venv
    fi
fi

# Rebuild if the existing venv is built on a too-old Python (< 3.11).
HAVE_VALID_VENV=0
if [ -f "$VENV_PY" ]; then
    if "$VENV_PY" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null; then
        HAVE_VALID_VENV=1
    else
        echo "   ⚠️  Existing .venv uses an old Python — rebuilding..."
        rm -rf .venv
    fi
fi

if [ "$HAVE_VALID_VENV" = 0 ]; then
    echo "   Creating .venv with $PYTHON..."
    "$PYTHON" -m venv .venv
fi

# Upgrade pip first: old bundled pip (e.g. 3.9-era 21.x) cannot do the PEP 660
# editable install hatchling requires.
"$VENV_PY" -m pip install --upgrade pip --quiet

# Install/update backend dependencies
echo "   Installing backend dependencies..."
cd backend
# `desktop` (pyinstaller) is included so the desktop build scripts keep
# working after a start.sh run. Without it, any rebuild of .venv here
# silently drops pyinstaller and the next desktop build fails with
# "pyinstaller not found".
if ! "$VENV_PY" -m pip install -e ".[dev,integrations,desktop]" > /tmp/newsixity-pip.log 2>&1; then
    cat /tmp/newsixity-pip.log >&2
    echo "   ❌ Backend dependencies failed to install." >&2
    exit 1
fi
rm -f /tmp/newsixity-pip.log
cd ..
echo "   ✓ Backend dependencies installed"

# ============================================================================
# CACHE CLEANUP
# ============================================================================

echo ""
echo "🧹 Cleaning cache directories..."

# Frontend caches
rm -rf node_modules/.cache 2>/dev/null || true
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

# Locate node/npm: the caller's shell may not have nvm on PATH (e.g. macOS
# loads nvm only from ~/.zshrc). Source it explicitly when needed so `npm`
# always resolves. Any npm-internal config lookups (npm config get cache/
# prefix) then succeed instead of failing with ENOENT.
if ! command -v npm >/dev/null 2>&1 && ! command -v node >/dev/null 2>&1; then
    NVM_SCRIPT=""
    for candidate in \
        "$HOME/.nvm/nvm.sh" \
        "${NVM_DIR:-}/nvm.sh" \
        "$HOME/homebrew/opt/nvm/nvm.sh" \
        "/opt/homebrew/opt/nvm/nvm.sh" \
        "/usr/local/opt/nvm/nvm.sh"
    do
        if [ -s "$candidate" ]; then
            NVM_SCRIPT="$candidate"
            break
        fi
    done
    if [ -n "$NVM_SCRIPT" ]; then
        # shellcheck disable=SC1090
        . "$NVM_SCRIPT"
    fi
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "   ❌ npm not found on PATH." >&2
    echo "   Install Node.js or load your version manager (nvm/volta/fnm) first." >&2
    exit 1
fi

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
    if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   ⚠️  Port 5173 in use (kill with: lsof -ti:5173 | xargs kill -9)"
        PORTS_OK=false
    fi

    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   ⚠️  Port 8000 in use (kill with: lsof -ti:8000 | xargs kill -9)"
        PORTS_OK=false
    fi
fi

if [ "$PORTS_OK" = true ]; then
    echo "   ✓ Ports 5173 & 8000 available"
fi

# ============================================================================
# START SERVERS
# ============================================================================

echo ""
echo "📚 Starting backend (FastAPI on :8000)..."
cd backend
"$VENV_PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Give backend time to start
sleep 2

echo "🎨 Starting frontend (Vite on :5173)..."
npm run dev &
FRONTEND_PID=$!

# Cleanup on exit
cleanup() {
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "✅ Both servers running:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo "   Logs:      Frontend (^C to stop), Backend (/logs endpoint)"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
