# Newsixity

A self-hosted, local-first news aggregation dashboard built with Next.js 16 and SQLite.
Pulls RSS feeds, groups duplicate stories, generates AI summaries, and lets you do deep research on any article — all running on your own machine.

---

## Features

- **RSS feed aggregation** across categories: World News, Finance, Gaming, Technology, Sports, Top News, Others
- **Smart ranking** — scores and promotes the top 20 articles per day in key categories using a multi-signal algorithm
- **AI summarization** via Ollama (local LLM, no cloud required)
- **Deep research** — ask any question about an article; searches the web, fetches sources, and synthesizes an answer with citations
- **Finance dashboard** — real-time stock quotes, charts, market heatmap, and watchlist
- **Weather** — current conditions and forecast
- **Article deduplication** — groups near-duplicate stories from different sources
- **Video/webpage embedding** — YouTube, Vimeo, Dailymotion, Odysee, and more
- **Backup system** — automatic daily SQLite backups + on-demand backup from the console
- **Security hardened** — CSRF protection, API token auth, SSRF guards, rate limiting, input sanitization

---

## Quick Start

### Prerequisites

- **Node.js 20+** — [nodejs.org](https://nodejs.org)
- **Ollama** — [ollama.ai](https://ollama.ai) (required for AI features)
- SQLite is bundled via `better-sqlite3` — no separate install needed

### Install

```bash
git clone <your-repo-url> newsixity
cd newsixity
npm install
```

### Run

```bash
# Recommended: starts Ollama + Next.js and opens the browser
./start.sh

# Manual alternative
ollama serve
npm run dev
```

Open **http://localhost:3000** in your browser.

### Stop

```bash
./stop.sh
# Or click STOP in the console at http://localhost:3000/console
```

---

## npm Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Start Next.js development server |
| `npm run build` | Build for production |
| `npm run start` | Run production build |
| `npm run lint` | Run ESLint (check only) |
| `npm run lint:fix` | Run ESLint and auto-fix issues |
| `npm run hooks:install` | Install git pre-commit lint hook |
| `npm run tests` | Lint + run all test suites |
| `npm run test:basic` | Utility & parsing unit tests |
| `npm run test:security` | Input hardening & access control tests |
| `npm run test:db` | Database schema & CRUD tests |
| `npm run audit` | Security audit of all dependencies |
| `npm run audit:prod` | Security audit of production dependencies only |

---

## Auto-Linter (Pre-Commit Hook)

Run once after cloning to install the git pre-commit hook:

```bash
npm run hooks:install
```

After that, **ESLint runs automatically before every `git commit`**.
If lint fails, the commit is blocked. To auto-fix and retry:

```bash
npm run lint:fix
git add -u
git commit -m "your message"
```

To bypass the hook in an emergency:

```bash
git commit --no-verify -m "your message"
```

---

## Project Structure

```
newsixity/
├── src/
│   ├── app/                    # Next.js App Router pages + API routes
│   │   ├── api/                # REST API endpoints
│   │   ├── article/[id]/       # Article detail page
│   │   ├── category/[slug]/    # Category feed page
│   │   ├── finance/            # Finance dashboard
│   │   ├── saved/              # Saved articles
│   │   ├── settings/           # Settings page
│   │   ├── console/            # Admin console
│   │   └── weather/            # Weather page
│   ├── components/             # React components by domain
│   │   ├── articles/
│   │   ├── finance/
│   │   ├── layout/
│   │   ├── ui/
│   │   └── weather/
│   ├── lib/                    # Server-side logic
│   │   ├── db/                 # SQLite connection, schema, queries
│   │   ├── rss/                # Feed definitions, parsing, scheduling
│   │   ├── ollama/             # LLM client, summarization, scheduling
│   │   ├── research/           # Deep research orchestration + search
│   │   ├── ranking/            # Article scoring, promotion, preferences
│   │   ├── content/            # Content fetching (HTTP + headless browser)
│   │   ├── dedup/              # Duplicate detection (bigram similarity)
│   │   ├── finance/            # Market data (Yahoo Finance)
│   │   ├── weather/            # Open-Meteo weather API
│   │   ├── backup/             # DB backup scheduler
│   │   ├── server/             # Auth, rate limiting, request helpers
│   │   └── utils/              # Date, sanitize, URL, video, search helpers
│   └── types/                  # Shared TypeScript interfaces
├── tests/
│   ├── basic/                  # Utility & parsing unit tests
│   ├── security/               # Input hardening & auth tests
│   ├── database/               # Schema & CRUD tests (in-memory SQLite)
│   └── setup/                  # Test loader (ESM path alias resolver)
├── scripts/
│   └── install-hooks.sh        # Installs git pre-commit hook
├── data/                       # SQLite DB + backups (git-ignored)
├── docs/
│   ├── DEVELOPER_GUIDE.md
│   └── plans/
└── public/
```

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

### Setting variables permanently

```bash
# Add to ~/.zshrc or ~/.bashrc
export NEWSIXITY_SETTINGS_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export NEWSIXITY_ADMIN_TOKEN="$(openssl rand -hex 24)"
```

---

## Deep Research Setup

1. Get a free API key at [brave.com/search/api](https://brave.com/search/api/)
2. Open **Settings** (`/settings`) and paste the key under "Brave Search API Key"
3. Make sure Ollama is running and select a model in Settings

See [DEEP-RESEARCH-SETUP.md](./DEEP-RESEARCH-SETUP.md) for full details and quota management.

---

## macOS Auto-Start

To launch Newsixity automatically at login:

```bash
launchctl load ~/Library/LaunchAgents/com.newsixity.startup.plist
```

See [STARTUP.md](./STARTUP.md) for full launch agent setup and troubleshooting.

---

## Database & Backups

The database lives at `data/newsixity.db` (or `$NEWSIXITY_DB_PATH`).
Automatic daily backups are saved to `data/backups/`.
Manual backup: click the **BACKUP** button in the console (`/console`).

To restore a backup:

```bash
cp data/newsixity.db data/newsixity.db.bak
cp data/backups/<backup-file>.db data/newsixity.db
```

See [BACKUP_SYSTEM.md](./BACKUP_SYSTEM.md) for details.

---

## Testing

```bash
npm run tests          # lint + all suites
npm run test:basic     # 129 utility/parsing tests
npm run test:security  # 54 input hardening + auth tests
npm run test:db        # 39 schema + CRUD tests (isolated in-memory DB)
```

Tests use Node.js's built-in test runner (`node --test`) — no extra framework needed.
Each test suite runs in isolation; database tests never touch the real database.

---

## Further Reading

- [STARTUP.md](./STARTUP.md) — start/stop scripts and macOS auto-launch
- [DEEP-RESEARCH-SETUP.md](./DEEP-RESEARCH-SETUP.md) — deep research configuration
- [BACKUP_SYSTEM.md](./BACKUP_SYSTEM.md) — backup and restore procedures
- [docs/DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md) — full developer reference
