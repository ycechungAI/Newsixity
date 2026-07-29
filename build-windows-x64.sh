#!/usr/bin/env bash
# One-command build for the Windows x64 desktop app: sets up the Python
# venv, freezes the backend with PyInstaller, builds the frontend, and
# bundles everything with Tauri.
#
# Run from Git Bash: ./build-windows-x64.sh
#
# Why x64 and not x86: pandas (a yfinance dependency) has no prebuilt wheel
# for 32-bit Windows Python, and building it from source needs a matching
# 32-bit MSVC + Cython toolchain this machine doesn't have. A 64-bit MSVC
# compiler (cl.exe) is already present (from an earlier Node.js installer
# step), so x64 is the path of least resistance. The Tauri shell itself has
# no such constraint — this just targets x64 throughout for simplicity.
#
# Output: src-tauri/target/release/bundle/  (msi/nsis installer + raw .exe)

set -e
cd "$(dirname "$0")"

export PATH="$HOME/.cargo/bin:$PATH"

PYTHON64="/c/Python314/python.exe"
if [ ! -x "$PYTHON64" ]; then
    echo "ERROR: expected 64-bit Python at $PYTHON64 — not found." >&2
    echo "Edit PYTHON64 in this script to point at a 64-bit python.exe." >&2
    exit 1
fi

echo "==> [1/4] Checking Python is actually 64-bit..."
"$PYTHON64" -c "import struct,sys; b=struct.calcsize('P')*8; print(f'{sys.version.split()[0]} ({b}-bit)'); assert b==64, 'not 64-bit!'"

echo "==> [2/4] Setting up backend venv at project root (.venv)..."
if [ ! -d ".venv" ]; then
    "$PYTHON64" -m venv .venv
fi
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -e "./backend[integrations,desktop]"

echo "==> [3/4] Building frontend + freezing backend sidecar (PyInstaller)..."
./backend/build_sidecar.sh

echo "==> [4/4] Building Tauri app bundle (x64)..."
npx tauri build

echo ""
echo "Build complete."
echo "Bundle output: src-tauri/target/release/bundle/"
