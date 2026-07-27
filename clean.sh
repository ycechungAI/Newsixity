#!/bin/bash
set -e

# Reclaim build-cache disk space. Nothing here touches source, your database,
# or ~/Library/Application Support/Newsixity/ — only regenerable build output.
#
# Usage:
#   ./clean.sh          Safe: build scratch + debug artifacts. No rebuild cost.
#   ./clean.sh --deep   Also drops the Rust dependency cache (~1GB). The next
#                       desktop build recompiles every crate — several minutes.
#   ./clean.sh --all    Also removes kept installers in install_file/.
#
# Why this exists: src-tauri/target grows without bound. `tauri dev` leaves a
# debug/ tree that release builds never use, and the DMG step leaves
# full-size rw.*.dmg scratch images behind.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

DEEP=0
ALL=0
for arg in "$@"; do
    case "$arg" in
        --deep) DEEP=1 ;;
        --all)  DEEP=1; ALL=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

size_of() { du -sk "$1" 2>/dev/null | awk '{print $1}' || echo 0; }
BEFORE=$(du -sk . 2>/dev/null | awk '{print $1}')

echo "🧹 Cleaning build caches..."

# 1. Debug build tree — produced only by `tauri dev`, unused by release builds.
if [ -d src-tauri/target/debug ]; then
    echo "   • src-tauri/target/debug ($(du -sh src-tauri/target/debug | cut -f1))"
    rm -rf src-tauri/target/debug
fi

# 2. DMG scratch images — full-size copies nothing cleans up automatically.
for f in src-tauri/target/release/bundle/macos/rw.*.dmg; do
    [ -e "$f" ] || continue
    echo "   • $(basename "$f") ($(du -sh "$f" | cut -f1))"
    rm -f "$f"
done

# 3. PyInstaller intermediates. dist/ is kept: build_sidecar.sh copies it into
#    src-tauri/resources/, and removing it would force a full re-freeze.
if [ -d backend/build ]; then
    echo "   • backend/build ($(du -sh backend/build | cut -f1))"
    rm -rf backend/build
fi

# 4. Python bytecode and test caches.
find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name .pytest_cache -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
rm -rf node_modules/.cache .ruff_cache tsconfig.tsbuildinfo 2>/dev/null || true
echo "   • __pycache__ / .pytest_cache / tool caches"

if [ "$DEEP" -eq 1 ]; then
    echo ""
    echo "🔥 Deep clean — the next desktop build recompiles all Rust crates."
    if [ -d src-tauri/target/release ]; then
        echo "   • src-tauri/target/release ($(du -sh src-tauri/target/release | cut -f1))"
        rm -rf src-tauri/target/release
    fi
fi

if [ "$ALL" -eq 1 ]; then
    if [ -d install_file ]; then
        echo "   • install_file ($(du -sh install_file | cut -f1)) — kept installers"
        rm -rf install_file
    fi
fi

AFTER=$(du -sk . 2>/dev/null | awk '{print $1}')
RECLAIMED=$(( (BEFORE - AFTER) / 1024 ))
echo ""
echo "✅ Reclaimed ~${RECLAIMED} MB. Repo now $(du -sh . | cut -f1)."
[ "$DEEP" -eq 0 ] && echo "   Run './clean.sh --deep' to also drop the Rust cache (~1GB)."
exit 0
