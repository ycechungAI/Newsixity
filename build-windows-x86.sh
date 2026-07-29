#!/usr/bin/env bash
# Build Newsixity for Windows x86 (32-bit) using the MinGW/GNU toolchain.
# Run this from Git Bash: ./build-windows-x86.sh
#
# Assumes:
#   - Rust installed via rustup (~/.cargo)
#   - MinGW32 GCC toolchain at C:\MinGW (gcc, windres, dlltool, ar)
#   - Node.js installed (winget/installer, on system PATH)
#   - Rust target i686-pc-windows-gnu added (this script adds it if missing)
#   - src-tauri/.cargo/config.toml pins the linker to C:/MinGW/bin/gcc.exe

set -e

# Make sure cargo + MinGW are on PATH for this shell (harmless if already there)
export PATH="$HOME/.cargo/bin:/c/MinGW/bin:$PATH"

cd "$(dirname "$0")"

echo "==> [1/4] Ensuring Rust target i686-pc-windows-gnu is installed..."
rustup target add i686-pc-windows-gnu

echo "==> [2/4] Installing frontend dependencies..."
npm install

echo "==> [3/4] Building frontend (vite)..."
npm run build

echo "==> [4/4] Building Tauri app for Windows x86 (release)..."
cd src-tauri
cargo build --release --target i686-pc-windows-gnu

echo ""
echo "Build complete."
echo "Executable: src-tauri/target/i686-pc-windows-gnu/release/newsixity.exe"
