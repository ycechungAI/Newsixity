# Newsixity Desktop App

Newsixity is packaged as a native desktop application using Tauri, a lightweight framework that uses the OS's built-in WebView instead of bundling Chromium. macOS is the primary, hand-tested target; Windows and Linux builds are produced via CI (see [Other Platforms](#other-platforms-windows--linux) below) and share the same codepath but are less battle-tested.

## Prerequisites

- **Ollama** (optional but recommended): Download from [ollama.ai](https://ollama.ai) and run `ollama serve` to enable article summarization. The app works without Ollama but summarization features require it to be running.

## Building Locally

### Quick Start

```bash
# Ensure dependencies are installed
npm install

# One command: builds the frontend, freezes the backend, packages as .app + .dmg
./build-desktop-mac.sh
```

This is the single entry point for rebuilding after **any** code change —
frontend, backend, or both — no matter which tool or session made the edit.
It always builds from whatever is currently on disk. Under the hood it's the
same two steps as before (kept as separate scripts in case you only need one):

```bash
./backend/build_sidecar.sh   # frontend build + PyInstaller freeze + resource install
npx tauri build               # Rust shell compile + .app/.dmg packaging
```

The packaged app will be created at:
- `src-tauri/target/release/bundle/macos/Newsixity.app` — double-clickable app bundle
- `src-tauri/target/release/bundle/dmg/Newsixity_0.1.0_aarch64.dmg` — disk image for distribution

### Build Steps Explained

1. **Frontend build** (`npm run build`): Compiles the React app to static files bundled in the Python backend.
2. **PyInstaller freeze** (`pyinstaller newsixity-backend.spec`): Freezes the FastAPI backend and all dependencies (yfinance, trafilatura, pandas, numpy, etc.) into a standalone `--onedir` executable.
3. **Resource install** (`cp -R backend/dist/newsixity-backend src-tauri/resources/`): Copies the frozen backend into the Tauri resources directory so it's bundled in the app.
4. **Tauri build** (`npx tauri build`): Compiles the Rust shell, embeds the resource, and produces the `.app` bundle and `.dmg`.

### Troubleshooting

**Compilation takes a long time:**
The first build compiles Rust and PyInstaller bundles heavy dependencies (pandas, numpy, lxml). Subsequent builds are faster.

## Running the App

Double-click `Newsixity.app` to launch. The app will:
1. Pick a free loopback port
2. Start the backend process (the frozen sidecar)
3. Wait for the backend to be ready (`/api/health` check)
4. Open the window and load the web interface

## User Data

All user data is stored in the macOS app-data directory, **not** in the app bundle or your repository:

```
~/Library/Application Support/Newsixity/
├── newsixity.db           # Main database (articles, feeds, state)
├── newsixity.db-shm       # SQLite write-ahead log
├── newsixity.db-wal       # SQLite write-ahead log
└── backups/               # Automatic daily backups + manual backups
    ├── newsixity-YYYY-MM-DDTHH-MM-SS.db  (manual)
    └── newsixity-auto-YYYY-MM-DDTHH-MM-SS.db  (automatic, 3 AM daily)
```

The app keeps the 2 most recent backups and auto-deletes older ones.

## Resetting the App

To reset to a clean state and re-copy the seed database:

```bash
rm -rf ~/Library/Application\ Support/Newsixity/
```

The next time you launch the app, it will detect the missing app-data directory and copy the seed database (~465 articles, 34 feeds) into place.

## Console & Maintenance

Open the Console tab inside the app to:
- **Resummarize articles** — re-run the summarizer on unsummarized articles
- **Backup DB** — create an immediate backup (saved to `~/Library/Application Support/Newsixity/backups/`)
- **Prune old articles** — remove low-scoring, old, duplicate articles (saved/unread articles are always kept)

## Ollama Integration

If Ollama is running on your machine, the app will automatically detect it and enable summarization. Check the health endpoint in Console to verify:
- **`ollama: true`** — Ollama is running and reachable at `localhost:11434`
- **`ollama: false`** — Ollama is not running; summarization is unavailable but the app continues to work

Models must be pre-pulled in Ollama:
```bash
ollama pull gemma4:12b
ollama pull llama3.2:3b
# ... any other models you want Newsixity to use
```

## Architecture Notes

The packaged app is a two-process system:
- **Tauri shell** (Rust): a tiny window manager that owns the native macOS window
- **FastAPI backend** (frozen Python): runs as a child process on a dynamic loopback port, serving the SPA and API

The shell and backend communicate via HTTP on `127.0.0.1:<port>`, which is only accessible locally. The loopback-only binding ensures the API never exposes to your local network.

## Troubleshooting App Launch

**App crashes immediately:**
Check that Ollama is not occupying the port the app tries to use (usually `127.0.0.1:11434` is reserved for Ollama). If you have multiple app instances running, each will pick a different free port.

**Database is locked / "database is busy":**
Ensure only one instance of the app is running. On rare occasions, a crash may leave a stale lock file. To clear it:
```bash
rm ~/Library/Application\ Support/Newsixity/newsixity.db-shm
rm ~/Library/Application\ Support/Newsixity/newsixity.db-wal
```

**Articles are missing after restart:**
Check the database is in the app-data directory (not in the repo). If articles vanished, they may have been pruned. Restore from a backup:
```bash
cp ~/Library/Application\ Support/Newsixity/backups/newsixity-YYYY-MM-DD*.db \
   ~/Library/Application\ Support/Newsixity/newsixity.db
```

## Development

To work on the desktop app during development:

1. **Frontend changes:** Edit `src/` and run `npm run build`, then restart the app to pick up new changes.
2. **Backend changes:** Edit `backend/app/` and run `./backend/build_sidecar.sh` to rebuild the frozen binary, then restart the app.
3. **Rust/Tauri changes:** Edit `src-tauri/src/` and run `npx tauri build` to recompile and test.

The dev workflow with `npm run dev` and `start.sh` continues to work unchanged for testing locally without packaging.

## Other Platforms (Windows & Linux)

`.github/workflows/desktop-build.yml` builds Windows (`.msi`/`.exe`) and Linux (`.deb`/`.AppImage`) installers via a GitHub Actions matrix, alongside macOS. Trigger it manually from the Actions tab (`workflow_dispatch`) — it's not wired to push/tag triggers yet.

Each runner freezes its own backend (PyInstaller doesn't cross-compile) and calls `./backend/build_sidecar.sh` + `npx tauri build`, same as the local macOS flow. The only difference: **CI builds ship with an empty database**, not your seeded one. `data/newsixity.db` is gitignored (it's your live reading data — saved articles, read history — and never gets committed), so CI runners simply don't have it. The app already handles a missing seed gracefully: it logs a warning and starts with a fresh, empty database that populates on the first RSS refresh. If you want a seeded CI build, you'd need to separately provision the seed DB to the runner (e.g. as a private release asset) — not currently wired up.

Building Windows/Linux locally instead of via CI works the same way as macOS (`build_sidecar.sh` then `tauri build`), but you need to be running on that OS — PyInstaller can't cross-freeze the Python backend for a different platform than it's running on.

### Linux (Arch-based)

```bash
./build-linux-arch.sh
```

Produces a single-file **AppImage** at `src-tauri/target/release/bundle/appimage/Newsixity_*_amd64.AppImage` (plus a timestamped copy under `install_file/`). No install step: `chmod +x` and run. The script sets `NO_STRIP=1` because linuxdeploy's bundled `strip` chokes on the `.relr.dyn` ELF sections current Arch toolchains emit — without it the AppImage bundle aborts.

Requires: Rust toolchain (rustup or mise), Node.js, and the Tauri Linux deps (`webkit2gtk-4.1`, `gtk3`, `libsoup-3.0`, `javascriptcoregtk-4.1` — installd via `opkg install webkit2gtk-4.1 gtk3 libsoup3 javascriptcoregtk` on Arch).

### Linux (Ubuntu/Debian)

```bash
./build-linux-ubuntu.sh
```

Produces a **.deb** at `src-tauri/target/release/bundle/deb/Newsixity_*_amd64.deb` (plus a timestamped copy under `install_file/`), installable via `sudo apt install <file>.deb`. Run the script on an actual Ubuntu/Debian machine (it needs `dpkg-deb`, which isn't present on Arch). Same tooling requirements as above, but with:

```bash
sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```
