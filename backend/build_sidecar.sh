#!/bin/bash
set -e

# Build script for Newsixity backend sidecar (PyInstaller frozen executable).
# Builds the frontend, freezes the backend with PyInstaller, and copies the
# binary into src-tauri/binaries/ where Tauri expects it.
#
# Usage: ./backend/build_sidecar.sh
#        Produces: src-tauri/binaries/newsixity-backend-aarch64-apple-darwin (macOS arm64)

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
echo "🧊 Freezing backend with PyInstaller..."
cd backend
.venv/bin/pyinstaller newsixity-backend.spec
echo "✓ Backend frozen to dist/newsixity-backend/"
cd ..
echo ""

# Step 3: Copy the binary into src-tauri/binaries/.
echo "📍 Installing sidecar binary for Tauri..."
mkdir -p src-tauri/binaries

# Determine target triple based on current platform.
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ $(uname -m) == "arm64" ]]; then
        TARGET="aarch64-apple-darwin"
    else
        TARGET="x86_64-apple-darwin"
    fi
elif [[ "$OSTYPE" == "linux-gnu" ]]; then
    if [[ $(uname -m) == "x86_64" ]]; then
        TARGET="x86_64-unknown-linux-gnu"
    else
        TARGET="aarch64-unknown-linux-gnu"
    fi
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    TARGET="x86_64-pc-windows-gnu"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

SIDECAR_NAME="newsixity-backend-${TARGET}"
cp backend/dist/newsixity-backend/newsixity-backend "src-tauri/binaries/${SIDECAR_NAME}"
chmod +x "src-tauri/binaries/${SIDECAR_NAME}"
echo "✓ Sidecar installed: src-tauri/binaries/${SIDECAR_NAME}"
echo ""

echo "✅ Build complete. Run 'npm run tauri:build' to build the app."
