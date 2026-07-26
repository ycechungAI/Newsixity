# Newsixity

A self-hosted, local-first news aggregation dashboard built with a FastAPI
(Python) backend and a Vite/React (TypeScript) frontend, backed by SQLite.
Pulls RSS and podcast feeds, groups duplicate stories, generates AI
summaries, and lets you do deep research on any article — all running on
your own machine. Packaged as a native desktop app via Tauri.

---

## Features

- **RSS feed aggregation** across categories: World News, Finance, Gaming, Technology, Sports, Weather, Top News, Security, Others
- **Podcasts** — subscribe by RSS feed URL, native audio playback with resume/speed control
- **Smart ranking** — scores and promotes the top 20 articles per day in key categories using a multi-signal algorithm ([docs/ranking.md](docs/ranking.md))
- **AI summarization** via Ollama (local LLM, no cloud required)
- **Deep research** — ask any question about an article; searches the web, fetches sources, and synthesizes an answer with citations ([docs/deep-research.md](docs/deep-research.md))
- **Finance dashboard** — real-time stock quotes, charts, market heatmap, and watchlist
- **Weather** — current conditions and forecast
- **Article deduplication** — groups near-duplicate stories from different sources
- **Video/webpage embedding** — YouTube, Vimeo, Dailymotion, Odysee, and more
- **Backup system** — automatic daily SQLite backups + on-demand backup from the console ([docs/backup.md](docs/backup.md))
- **Security hardened** — CSRF protection, API token auth, SSRF guards, rate limiting, input sanitization
- **Desktop app** — packaged with Tauri for macOS (Windows/Linux via CI); see [docs/desktop.md](docs/desktop.md)

---

## Quick Start

### Prerequisites

- **Node.js 20+** — [nodejs.org](https://nodejs.org)
- **Python 3.11+**
- **Ollama** — [ollama.ai](https://ollama.ai) (required for AI features)

### Install

```bash
git clone <your-repo-url> newsixity
cd newsixity
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./backend[integrations]"
```

### Run

```bash
./start.sh
```

This starts the FastAPI backend (`:8000`) and the Vite dev server (`:5173`,
proxying `/api/*` to the backend) together.

Open **http://localhost:5173** in your browser. API docs: **http://localhost:8000/docs**

### Stop

```bash
./stop.sh
# Or click STOP in the console at http://localhost:5173/console
```

Full setup, project structure, and workflow details: [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md).

---

## npm / test commands

| Command | What it does |
|---|---|
| `npm run dev` | Start Vite dev server only |
| `npm run build` | Production frontend build |
| `npm run lint` | Run ESLint (check only) |
| `npm run lint:fix` | Run ESLint and auto-fix issues |
| `npm run build:mac` | Build the macOS desktop app (`.app` + `.dmg`) — see [docs/desktop.md](docs/desktop.md) |
| `sh scripts/install-hooks.sh` | Install git pre-commit lint hook |
| `.venv/bin/python -m pytest backend/tests` | Run the full backend test suite |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NEWSIXITY_DB_PATH` | No | Custom path to SQLite database file |
| `NEWSIXITY_SETTINGS_ENCRYPTION_KEY` | Recommended | Secret key for encrypting sensitive settings in DB |
| `NEWSIXITY_ADMIN_TOKEN` | No | Bearer token for admin API routes (`/api/console`, `/api/settings`, etc.) |
| `NEWSIXITY_API_TOKEN` | No | Bearer token for read-only API routes |
| `BRAVE_SEARCH_API_KEY` | No | Brave Search API key for deep research (can also be set in `/settings`) |

When no token is configured, all API access is restricted to `localhost`.

```bash
# Add to ~/.zshrc or ~/.bashrc to persist
export NEWSIXITY_SETTINGS_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export NEWSIXITY_ADMIN_TOKEN="$(openssl rand -hex 24)"
```

---

## Further Reading

- [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) — full developer reference (setup, project structure, testing, security)
- [docs/desktop.md](docs/desktop.md) — building and running the packaged desktop app
- [docs/ranking.md](docs/ranking.md) — smart article ranking system
- [docs/deep-research.md](docs/deep-research.md) — deep research configuration and quota
- [docs/backup.md](docs/backup.md) — backup and restore procedures
