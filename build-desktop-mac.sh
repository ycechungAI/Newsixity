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
#         install_file/Newsixity-<timestamp>.app  (kept copy — see below)
#
# Tauri rebuilds Newsixity.app in place, so a build you haven't installed yet
# is silently replaced by the next one. This script keeps a timestamped copy
# under install_file/ so a working build is never lost, and verifies the
# artifacts actually exist rather than trusting the build's own summary —
# the DMG step in particular can leave a half-finished rw.*.dmg scratch
# image behind and still report success.
#
# Does NOT touch the app's user data (~/Library/Application Support/Newsixity/)
# — that directory is separate from the build output, and the packaged app
# only seeds it from data/newsixity.db on first launch, when it doesn't
# already exist. See backend/app/db/init_db.py::_copy_seed_db_if_first_run.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

./backend/build_sidecar.sh

BUNDLE="src-tauri/target/release/bundle"

# Scratch images from a previous DMG run. These are full-size (~180MB each)
# and are never cleaned up automatically, so they accumulate silently.
rm -f "$BUNDLE"/macos/rw.*.dmg 2>/dev/null || true

echo "📦 Building Tauri app bundle..."
npx tauri build

APP="$BUNDLE/macos/Newsixity.app"

# Verify rather than trust: the build prints a success summary listing
# artifacts even when the DMG conversion left only a scratch image.
if [ ! -d "$APP" ]; then
    echo "❌ Build reported success but $APP does not exist." >&2
    exit 1
fi
if [ ! -x "$APP/Contents/MacOS/Newsixity" ]; then
    echo "❌ $APP has no runnable binary — the bundle is incomplete." >&2
    exit 1
fi
if [ ! -d "$APP/Contents/Resources/resources/newsixity-backend" ]; then
    echo "❌ $APP is missing the Python backend resource — it would start" >&2
    echo "   and then fail to reach its own API. Re-run build_sidecar.sh." >&2
    exit 1
fi

# Keep a timestamped copy so an un-installed build can't be lost to the next
# run. Cheap in wall-clock terms next to the build itself.
KEEP_DIR="install_file"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
mkdir -p "$KEEP_DIR"
cp -R "$APP" "$KEEP_DIR/Newsixity-$STAMP.app"

# Keep the 3 most recent; older ones are ~140MB each.
ls -dt "$KEEP_DIR"/Newsixity-*.app 2>/dev/null | tail -n +4 | while read -r old; do
    rm -rf "$old"
done

rm -f "$BUNDLE"/macos/rw.*.dmg 2>/dev/null || true

echo ""
echo "✅ Done."
echo "   Installable app : $APP"
echo "   Kept copy       : $KEEP_DIR/Newsixity-$STAMP.app"
DMG="$(ls "$BUNDLE"/dmg/*.dmg 2>/dev/null | head -1)"
if [ -n "$DMG" ]; then
    echo "   Disk image      : $DMG"
else
    echo "   Disk image      : not produced (the .app above is complete and installable)"
fi
du -sh "$APP" | awk '{print "   Size            : "$1}'
