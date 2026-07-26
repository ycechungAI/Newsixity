#!/bin/bash
set -e

# Build script for Newsixity backend sidecar (PyInstaller frozen executable).
# Builds the frontend, freezes the backend with PyInstaller, and copies the
# resulting --onedir output into src-tauri/resources/ where Tauri bundles it
# as a resource (not externalBin/sidecar() — PyInstaller's --onedir output is
# a directory of files the executable depends on, not a single self-contained
# binary, so it can't use Tauri's single-file sidecar convention; see the
# comment atop src-tauri/src/lib.rs for how it's spawned at runtime instead).
#
# Usage: ./backend/build_sidecar.sh
#        Produces: src-tauri/resources/newsixity-backend/ (full onedir tree)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "🔨 Building Newsixity backend sidecar for Tauri..."
echo ""

# Step 1: Build the frontend (Vite).
echo "📦 Building frontend (Vite)..."
npm run build
echo "✓ Frontend built to dist/"
echo ""

# Step 2: Freeze the backend with PyInstaller.
# Venv layout differs by platform: POSIX venvs put scripts in bin/, Windows
# venvs (including CI runners under Git Bash) put them in Scripts/.
if [ -x ".venv/bin/pyinstaller" ]; then
    PYINSTALLER="$REPO_ROOT/.venv/bin/pyinstaller"
elif [ -x ".venv/Scripts/pyinstaller.exe" ]; then
    PYINSTALLER="$REPO_ROOT/.venv/Scripts/pyinstaller.exe"
else
    echo "ERROR: pyinstaller not found in .venv (checked bin/ and Scripts/)" >&2
    exit 1
fi

echo "🧊 Freezing backend with PyInstaller..."
cd backend
# --noconfirm: PyInstaller refuses to write into a non-empty dist/ dir by
# default, which breaks every rebuild after the first. Safe here since
# dist/newsixity-backend only ever holds this script's own prior output.
"$PYINSTALLER" --noconfirm newsixity-backend.spec
echo "✓ Backend frozen to dist/newsixity-backend/"
cd ..
echo ""

# Step 3: Copy the full onedir tree into src-tauri/resources/.
echo "📍 Installing backend resource for Tauri..."
rm -rf src-tauri/resources/newsixity-backend
mkdir -p src-tauri/resources
cp -R backend/dist/newsixity-backend src-tauri/resources/newsixity-backend
chmod +x src-tauri/resources/newsixity-backend/newsixity-backend* 2>/dev/null || true
echo "✓ Resource installed: src-tauri/resources/newsixity-backend/"
echo ""

echo "✅ Build complete. Run 'npx tauri build' to build the app."
