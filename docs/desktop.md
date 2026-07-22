# Newsixity Desktop App

Newsixity is packaged as a native macOS desktop application using Tauri, a lightweight framework that uses the OS's built-in WebView instead of bundling Chromium.

## Prerequisites

- **Ollama** (optional but recommended): Download from [ollama.ai](https://ollama.ai) and run `ollama serve` to enable article summarization. The app works without Ollama but summarization features require it to be running.

## Building Locally

### Quick Start

```bash
# Ensure dependencies are installed
npm install

# Build the frontend and freeze the backend, then package as .app
./backend/build_sidecar.sh
npx tauri build
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

**"output directory is not empty" error during PyInstaller freeze:**
```bash
rm -rf backend/build backend/dist
./backend/build_sidecar.sh
```

PyInstaller's `COLLECT` step fails if the output directory contains stale content. Clean both directories before rebuilding.

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
