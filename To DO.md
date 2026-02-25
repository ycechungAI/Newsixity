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
