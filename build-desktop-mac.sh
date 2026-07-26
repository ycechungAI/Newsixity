#!/bin/bash
set -e

# One-command build for the macOS desktop app: freezes the backend (Python +
# all deps) with PyInstaller, then bundles it with the Tauri shell into a
# native .app + .dmg. Rebuild this any time backend or frontend code
# changes, regardless of which session/tool made the change — it always
# builds from whatever is currently on disk.
#
# Usage: ./build-desktop-mac.sh
# Output: src-tauri/target/release/bundle/macos/Newsixity.app
#         src-tauri/target/release/bundle/dmg/Newsixity_<version>_aarch64.dmg
#
# Does NOT touch the app's user data (~/Library/Application Support/Newsixity/)
# — that directory is separate from the build output, and the packaged app
# only seeds it from data/newsixity.db on first launch, when it doesn't
# already exist. See backend/app/db/init_db.py::_copy_seed_db_if_first_run.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

./backend/build_sidecar.sh

echo "📦 Building Tauri app bundle..."
npx tauri build

echo ""
echo "✅ Done. Bundle output:"
find src-tauri/target/release/bundle -maxdepth 2 -type d -not -name bundle
