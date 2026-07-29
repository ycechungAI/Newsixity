@echo off
REM Build Newsixity for Windows x86 (32-bit)
REM Requires: Rust, Visual Studio Build Tools, Node.js

echo [1/4] Installing/updating Rust x86 target...
rustup target add i686-pc-windows-msvc

echo [2/4] Installing frontend dependencies...
npm install

echo [3/4] Building frontend...
npm run build

echo [4/4] Building Tauri app for x86...
cd src-tauri
cargo build --release --target i686-pc-windows-msvc

echo.
echo Build complete! Output: src-tauri\target\i686-pc-windows-msvc\release\newsixity.exe
pause
