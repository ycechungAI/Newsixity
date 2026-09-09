#!/bin/bash
set -e

# One-command build for the Ubuntu/Debian desktop app: builds the frontend,
# freezes the backend (Python + all deps) with PyInstaller, and bundles it with
# the Tauri shell into a native .deb package. Rebuild this any time backend or
# frontend code changes.
#
# Usage: ./build-linux-ubuntu.sh
# Output: src-tauri/target/release/bundle/deb/*.deb
#         install_file/Newsixity-<timestamp>.deb  (kept copy — see below)
#
# Required tooling on the build machine:
#   - Rust toolchain  (rustup recommended)
#   - Tauri Linux system deps:
#       libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev
#       libssl-dev libayatana-appindicator3-dev librsvg2-dev
#   - dpkg-deb (ships with dpkg, present on every Ubuntu/Debian box)
#
# Does NOT touch user data (~/.local/share/com.newsixity.desktop/) — separate
# from build output; the packaged app only seeds it from data/newsixity.db on
# first launch. See backend/app/db/init_db.py::_copy_seed_db_if_first_run.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Rust lives in ~/.cargo (rustup); make sure it's visible.
export PATH="$HOME/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
    echo "ERROR: cargo not found. Install Rust first:" >&2
    echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y" >&2
    exit 1
fi

./backend/build_sidecar.sh

BUNDLE="src-tauri/target/release/bundle"

echo "📦 Building Tauri .deb bundle..."
npx tauri build --bundles deb

DEB="$(ls "$BUNDLE"/deb/*.deb 2>/dev/null | head -1)"

# Verify rather than trust: the build prints a success summary even when the
# .deb step silently failed.
if [ -z "$DEB" ] || [ ! -f "$DEB" ]; then
    echo "❌ Build reported success but no .deb exists under $BUNDLE/deb/." >&2
    exit 1
fi

# Keep a timestamped copy so an un-installed build can't be lost to the next
# run.
KEEP_DIR="install_file"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
mkdir -p "$KEEP_DIR"
KEEP="$KEEP_DIR/Newsixity-$STAMP.deb"
cp "$DEB" "$KEEP"

# Keep the 3 most recent; older ones are ~40MB each.
ls -t "$KEEP_DIR"/Newsixity-*.deb 2>/dev/null | tail -n +4 | while read -r old; do
    rm -f "$old"
done

echo ""
echo "✅ Done."
echo "   Installable app : $DEB"
echo "   Kept copy       : $KEEP"
echo "   To install      : sudo apt install \"$KEEP\"   (or: sudo dpkg -i \"$KEEP\")"
du -sh "$DEB" | awk '{print "   Size            : "$1}'