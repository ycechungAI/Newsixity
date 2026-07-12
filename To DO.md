# To Do

1. [DONE - CRITICAL] Add authentication and authorization for all API routes, especially admin/mutation endpoints (`/api/console/*`, `/api/settings`, `/api/feeds/refresh`, `/api/summarize`, `/api/preferences`).
2. [DONE - CRITICAL] Fix stored XSS risk by sanitizing/escaping article HTML before rendering and removing unsafe direct `dangerouslySetInnerHTML` usage for untrusted content.
3. [DONE - HIGH] Add SSRF protections for server-side URL fetching (manual links and article content fetch): allowlist protocols, block private/localhost ranges, enforce egress controls.
4. [DONE - HIGH] Lock down console/log endpoints and redact sensitive data in logs before exposing anything to clients.
5. [DONE - HIGH] Add rate limiting and abuse controls for expensive endpoints (refresh, summarize, research).
6. [DONE - HIGH] Address identified architectural issues to improve maintainability and modularity.
7. [DONE - MEDIUM] Standardize strict request validation with Zod across all API routes (not just manual article route).
8. [DONE - MEDIUM] Replace raw internal error messages in API responses with safe generic messages and correlation IDs.
9. [DONE - MEDIUM] Improve secret handling: stop storing API keys as plain text in SQLite; use env/keychain/KMS or encryption at rest.
10. [DONE - LOW] Add security headers/CSP in Next.js config (`Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, etc.).
11. [DONE - LOW] Run dependency security checks in CI (`npm audit`/SCA), remediate findings, and prune extraneous packages.
12. [DONE - HIGH] Add a local test harness and scripts (`npm run tests`) that run category-specific suites (lint → basic → security → database).
13. [DONE - HIGH] Implement basic functionality tests (URL/search/video parsing and core utility behavior) — 129 tests in `tests/basic/`.
14. [DONE - HIGH] Implement security tests (input hardening and API access control checks) — 54 tests in `tests/security/`.
15. [DONE - HIGH] Implement database tests using isolated in-memory SQLite — 39 tests in `tests/database/`.
16. [DONE - MEDIUM] Add auto-linter: `npm run lint:fix` for on-demand fixing, git pre-commit hook via `npm run hooks:install`, lint wired into `npm run tests`.
17. [DONE - LOW] Write comprehensive README.md and update developer documentation (docs/DEVELOPER_GUIDE.md, STARTUP.md).
18. [DONE - HIGH] Fix `./start.sh` returning HTTP 500 on every route ("Could not find the module ... in the React Client Manifest") when the local `.next` build cache predates a `next` version bump — script now stamps the installed Next.js version and auto-clears `.next` on mismatch, with retries to survive macOS Finder's `.DS_Store` race on `rm -rf`.

## Performance

19. [TODO - MEDIUM] `ArticleCard.tsx` (`src/components/articles/ArticleCard.tsx:44-70`) fires one `PATCH /api/articles/{id}` per card via its own `IntersectionObserver`/`fetch` when a card scrolls into view — on a long list this bursts many sequential one-article HTTP round trips (~1s each observed in dev) instead of a single batched "mark read" call.
20. [TODO - MEDIUM/HIGH] `getArticleGroupsByCategory` (`src/lib/db/queries.ts:216-234`) issues 1-2 extra `SELECT`s per group row (up to ~90 queries for the default 30-group page) instead of a single JOIN/`IN` query — runs on every category page view.
21. [TODO - MEDIUM] `src/lib/rss/scheduler.ts:53-56` calls `getArticleById(id)` once per new article after every feed refresh (every 15 min) instead of a single `WHERE id IN (...)` batch query.
22. [TODO - LOW/MEDIUM] `getCachedQuotes` (`src/lib/db/queries.ts:~1241-1250`) loops over `symbols` calling `getCachedQuote` per symbol instead of one `IN (...)` query.
23. [TODO - LOW/MEDIUM] No index covers the `is_read` filter/sort used by `getArticlesByCategory` (`ORDER BY is_read ASC, published_at DESC WHERE is_read = 0`, hit on nearly every page load) — only `is_saved` has a partial index (`src/lib/db/schema.ts:132`). Consider a compound index on `(is_read, published_at)`.
24. [TODO - LOW] `src/app/api/console/backup/route.ts:15-70` uses synchronous `readdirSync`/`statSync`/`existsSync` in a request handler — blocking, but only affects the rarely-hit admin backup page.
