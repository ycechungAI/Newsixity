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

# Rust lives in ~/.cargo (rustup); make sure it's visible even when this
# script runs from a non-login shell (IDE, agent, double-click), where
# ~/.zprofile was never sourced and cargo would otherwise not be found.
export PATH="$HOME/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
    echo "ERROR: cargo not found. Install Rust first:" >&2
    echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y" >&2
    exit 1
fi

# Tauri's macOS build needs the Xcode Command Line Tools: cc for linking
# the Rust binary, codesign for the .app, hdiutil for the .dmg. Without
# them `npx tauri build` dies with cryptic linker errors.
if ! xcode-select -p >/dev/null 2>&1; then
    echo "ERROR: Xcode Command Line Tools not found. Install them with:" >&2
    echo "  xcode-select --install" >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found. Install Node.js first (https://nodejs.org/):" >&2
    echo "  brew install node" >&2
    exit 1
fi

# Node 24+ only (package.json "engines", .nvmrc). 20 and 22 are retired; fail
# here with a clear message instead of deep inside `npm ci` / vite.
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [ "$NODE_MAJOR" -lt 24 ]; then
    echo "ERROR: Node.js 24 or newer is required (found: $(node -v 2>/dev/null || echo none))." >&2
    echo "  nvm install && nvm use      # reads .nvmrc" >&2
    exit 1
fi

# --- Self-healing first-time setup --------------------------------------
# A fresh checkout (or a new Mac) is missing things the build needs. Set
# them up here automatically instead of failing with cryptic errors.

# 1. Frontend dependencies: `vite: command not found` on a fresh clone
#    just means node_modules was never installed.
if [ ! -d "node_modules" ]; then
    echo "📦 node_modules not found — installing frontend dependencies (npm ci)..."
    npm ci
fi

# 2. Backend venv: pyproject requires Python >= 3.11, but macOS ships
#    python3 = 3.9, which pip rejects with a confusing error. Pick the
#    newest suitable interpreter explicitly, and recreate a venv that was
#    built with the wrong Python.
pick_python() {
    for _py in python3.12 python3.11 python3; do
        if command -v "$_py" >/dev/null 2>&1 \
            && "$_py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            echo "$_py"
            return 0
        fi
    done
    return 1
}

VENV="$REPO_ROOT/backend/.venv"
if [ ! -x "$VENV/bin/pyinstaller" ]; then
    if [ -x "$VENV/bin/python" ] \
        && ! "$VENV/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        echo "⚠️  backend/.venv was built with an unsuitable Python — recreating it..."
        rm -rf "$VENV"
    fi
    if [ ! -x "$VENV/bin/python" ]; then
        PYBIN="$(pick_python)" || {
            echo "ERROR: need Python >= 3.11, none found. Install one with:" >&2
            echo "  brew install python@3.12" >&2
            exit 1
        }
        echo "📦 Creating backend/.venv with $PYBIN..."
        "$PYBIN" -m venv "$VENV"
        # Fresh venvs ship an ancient pip that can't do editable installs
        # with the hatchling build backend — upgrade it first.
        "$VENV/bin/pip" install --quiet --upgrade pip
    fi
    echo "📦 Installing backend dependencies into backend/.venv..."
    "$VENV/bin/pip" install -e "$REPO_ROOT/backend[integrations,desktop]"
fi
# --- end self-healing ---------------------------------------------------

./backend/build_sidecar.sh

BUNDLE="src-tauri/target/release/bundle"

# Scratch images from a previous DMG run. These are full-size (~180MB each)
# and are never cleaned up automatically, so they accumulate silently.
rm -f "$BUNDLE"/macos/rw.*.dmg 2>/dev/null || true

echo "📦 Building Tauri app bundle..."
# A failing DMG step (bundle_dmg.sh drives Finder via AppleScript, which
# fails without automation permission, e.g. from a non-interactive shell)
# makes `tauri build` exit non-zero after the .app is already complete.
# Under `set -e` that skipped the verification below entirely — let the
# verification decide instead.
if ! npx tauri build; then
    echo "⚠️  tauri build exited non-zero (usually the DMG step) — verifying the .app..."
fi

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
