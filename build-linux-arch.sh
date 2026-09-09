#!/bin/bash
set -e

# One-command build for the Arch-based Linux desktop app: builds the frontend,
# freezes the backend (Python + all deps) with PyInstaller, and bundles it with
# the Tauri shell into a native AppImage. Rebuild this any time backend or
# frontend code changes, regardless of which session/tool made the change — it
# always builds from whatever is currently on disk.
#
# Usage: ./build-linux-arch.sh
# Output: src-tauri/target/release/bundle/appimage/*.AppImage
#         install_file/Newsixity-<timestamp>.AppImage  (kept copy — see below)
#
# Why AppImage and not .deb/.rpm: AppImage is produced entirely by Tauri with
# no extra packaging tools (dpkg/rpmbuild), so it works on any -based distro
# and needs no install step — download, chmod +x, run. The Ubuntu .deb build
# lives in build-linux-ubuntu.sh (run that on an actual Ubuntu/Debian box,
# where dpkg-deb exists).
#
# NO_STRIP: linuxdeploy ships an old `strip` that chokes on the `.relr.dyn`
# ELF sections emitted by current Arch toolchains ("unknown type .relr.dyn"),
# which aborts every AppImage bundle. Skipping the strip step is harmless
# here — the Rust release profile already strips the binary.
#
# Does NOT touch user data (~/.local/share/com.newsixity.desktop/) — separate
# from build output; the packaged app only seeds it from data/newsixity.db on
# first launch. See backend/app/db/init_db.py::_copy_seed_db_if_first_run.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Rust lives in ~/.cargo (rustup) or via mise shims; make sure it's visible.
export PATH="$HOME/.cargo/bin:$HOME/.local/share/mise/shims:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
    echo "ERROR: cargo not found. Install the Rust toolchain first:" >&2
    echo "  opkg install rust (or: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y)" >&2
    exit 1
fi
export NO_STRIP=1

./backend/build_sidecar.sh

BUNDLE="src-tauri/target/release/bundle"

echo "📦 Building Tauri AppImage bundle..."
TAURI_BUILD_ARGS=(--bundles appimage)
if [ -n "${NEWSIXITY_TAURI_VERBOSE:-}" ]; then
    TAURI_BUILD_ARGS+=(-vvv)
fi
npx tauri build "${TAURI_BUILD_ARGS[@]}"

APPIMAGE="$(ls "$BUNDLE"/appimage/*.AppImage 2>/dev/null | head -1)"

# Verify rather than trust: the build prints a success summary even when the
# AppImage step silently failed to produce an artifact.
if [ -z "$APPIMAGE" ] || [ ! -f "$APPIMAGE" ]; then
    echo "❌ Build reported success but no .AppImage exists under $BUNDLE/appimage/." >&2
    exit 1
fi

# ── Linux-only AppImage post-processing ────────────────────────────────────
# Tauri bundles a copy of WebKitGTK + GTK + GStreamer into the AppImage.
# On Linux that bundled WebKit is inconsistent with the system GStreamer
# (bundled core libs + system plugins), which crashes the WebKitWebProcess on
# podcast/audio playback, and the X11 webview backend applies the session's
# GDK_SCALE on top of the real 1.0 monitor scale, which renders text at 2x.
#
# Fix: repackage the AppDir (a) using the system WebKitGTK/GStreamer instead
# of the bundled copies, and (b) neutralising GDK_SCALE so UI renders at the
# true 1.0 scale. This step lives ONLY in this Linux build script — Windows
# and macOS builds never run it and keep their own (required) WebKit stacks.
#
# Relies on appimagetool bundled inside the linuxdeploy plugin AppImage that
# Tauri already cached under ~/.cache/tauri — no extra packages needed.
PLUGIN_APPIMAGE="$(find "$HOME/.cache/tauri" -name 'linuxdeploy-plugin-appimage.AppImage' 2>/dev/null | head -1)"
if [ -z "$PLUGIN_APPIMAGE" ]; then
    echo "❌ Could not find linuxdeploy-plugin-appimage.AppImage under ~/.cache/tauri." >&2
    exit 1
fi

APPDIR="$(ls -d "$BUNDLE"/appimage/*.AppDir 2>/dev/null | head -1)"
if [ -z "$APPDIR" ] || [ ! -d "$APPDIR" ]; then
    echo "❌ AppDir not found under $BUNDLE/appimage/." >&2
    exit 1
fi

# 1. Drop bundled WebKit and GStreamer core libs so the app links the
#    consistent system set. GTK/GDK are fine bundled and stay.
echo "  Stripping bundled WebKitGTK/GStreamer from AppDir…"
rm -rf \
  "$APPDIR/usr/lib/libwebkit2gtk-4.1.so.0" \
  "$APPDIR/usr/lib/libjavascriptcoregtk-4.1.so.0" \
  "$APPDIR/usr/lib/webkit2gtk-4.1" \
  "$APPDIR"/usr/lib/libgst*.so.0 \
  "$APPDIR"/usr/lib/libwebp*.so* \
  "$APPDIR"/usr/lib/libsharpyuv*.so* \
  "$APPDIR"/usr/lib/libglib-2.0.so* \
  "$APPDIR"/usr/lib/libgobject-2.0.so* \
  "$APPDIR"/usr/lib/libgio-2.0.so* \
  "$APPDIR"/usr/lib/libgmodule-2.0.so* \
  "$APPDIR"/usr/lib/libgthread-2.0.so* \
  "$APPDIR"/usr/lib/libpcre2-*.so* \
  "$APPDIR"/usr/lib/libmount.so* \
  "$APPDIR"/usr/lib/libblkid.so* 2>/dev/null || true

# 2. Neutralise the session GDK_SCALE (2x text), point GStreamer at system
#    plugins, and pin GLVND to a single (Mesa) EGL/GLX backend before the
#    binary execs.
echo "  Patching AppRun to fix 2x text scaling, GStreamer plugin discovery, and mixed-GL stack…"
python3 - "$APPDIR/AppRun" <<'PY'
import sys
path = sys.argv[1]
s = open(path).read()
anchor = 'exec "$this_dir"/AppRun.wrapped "$@"'
fix = (
    '\n# Neutralise the session-level GDK_SCALE override, which the X11 webview\n'
    '# backend would otherwise apply on top of the correct 1.0 monitor scale,\n'
    '# rendering the whole UI at 2x. Linux-only (env var absent on Win/macOS).\n'
    'export GDK_SCALE=1\n'
    'export WEBKIT_DISABLE_DMABUF_RENDERER=1\n'
    '\n'
    '# We stripped bundled WebKit and GStreamer from the AppDir so the binary links\n'
    '# the system copies. Force GStreamer to discover system plugins explicitly;\n'
    '# AppRun.wrapped only prepends the (now empty) AppDir gstreamer-1.0 dir.\n'
    '# Ask pkg-config for the active distro-specific plugin directory instead of\n'
    '# assuming the Arch /usr/lib layout (Ubuntu uses a multiarch directory).\n'
    'GST_SYSTEM_PLUGIN_DIR="$(pkg-config --variable=pluginsdir gstreamer-1.0 2>/dev/null || true)"\n'
    'if [ -z "$GST_SYSTEM_PLUGIN_DIR" ]; then GST_SYSTEM_PLUGIN_DIR="/usr/lib/gstreamer-1.0"; fi\n'
    'export GST_PLUGIN_SYSTEM_PATH_1_0="$GST_SYSTEM_PLUGIN_DIR:${GST_PLUGIN_SYSTEM_PATH_1_0:-}"\n'
    '\n'
    '# Pin the webview to a single GLVND backend. nvidia-utils is present on many\n'
    '# AMD/Intel-only boxes and its 10_nvidia.json makes every GL process dlopen\n'
    '# libEGL_nvidia/libGLX_nvidia even with no NVIDIA hardware, which crashes\n'
    '# WebKitWebProcess (segfaults inside libnvidia-gpucomp during teardown). If\n'
    '# the NVIDIA kernel module is really attached, leave the default dispatch\n'
    '# alone; otherwise restrict GLVND to the Mesa vendor.\n'
    'if [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ] && ! lsmod 2>/dev/null | grep -q "^nvidia"; then\n'
    '    export __EGL_VENDOR_LIBRARY_FILENAMES="/usr/share/glvnd/egl_vendor.d/50_mesa.json"\n'
    '    export __GLX_VENDOR_LIBRARY_NAME="mesa"\n'
    'fi\n'
)
if anchor in s and 'export GDK_SCALE=1' not in s:
    open(path, 'w').write(s.replace(anchor, fix + anchor))
    print("  AppRun patched: GDK_SCALE + GST plugin path + Mesa-only GLVND")
else:
    print("  AppRun already patched or anchor not found; skipping")
PY

# 3. Extract appimagetool from the cached plugin AppImage and re-squash.
PLUGIN_EXTRACT="$(mktemp -d)"
( cd "$PLUGIN_EXTRACT" && "$PLUGIN_APPIMAGE" --appimage-extract >/dev/null 2>&1 )
APPIMAGETOOL="$(find "$PLUGIN_EXTRACT" -name 'appimagetool' -path '*bin*' 2>/dev/null | head -1)"
if [ -z "$APPIMAGETOOL" ]; then
    echo "❌ appimagetool not found inside plugin AppImage." >&2
    exit 1
fi

echo "  Repacking AppImage (system WebKit + correct scale)…"
REPACK_STAMP="$(date +%Y%m%d-%H%M%S)"
REPACKED="$BUNDLE/appimage/Newsixity-$REPACK_STAMP.AppImage"
"$APPIMAGETOOL" "$APPDIR" "$REPACKED" >/dev/null 2>&1
echo "  ✅ Repacked: $(basename "$REPACKED") ($(du -sh "$REPACKED" | cut -f1))"
rm -rf "$PLUGIN_EXTRACT" 2>/dev/null || true

# Prefer the repacked AppImage as the deliverable.
APPIMAGE="$REPACKED"

# Keep a timestamped copy so an un-installed build can't be lost to the next
# run.
KEEP_DIR="install_file"
STAMP="$(date +%Y-%m-%dT%H-%M-%S)"
mkdir -p "$KEEP_DIR"
KEEP="$KEEP_DIR/Newsixity-$STAMP.AppImage"
cp "$APPIMAGE" "$KEEP"

# Keep the 3 most recent; older ones are ~80MB each.
ls -t "$KEEP_DIR"/Newsixity-*.AppImage 2>/dev/null | tail -n +4 | while read -r old; do
    rm -f "$old"
done

echo ""
echo "✅ Done."
echo "   Installable app : $APPIMAGE"
echo "   Kept copy       : $KEEP"
echo "   To install/run  : chmod +x \"$KEEP\" && ./\"$KEEP\""
du -sh "$APPIMAGE" | awk '{print "   Size            : "$1}'
