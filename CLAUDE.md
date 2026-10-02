All rules for this project live in **AGENTS.md** at the repo root. That file is
authoritative — read it and follow it before making changes here.

@AGENTS.md

Specifically, and most important:

- **Never delete, truncate, reset, or recreate any database** without asking me
  first. Both `data/newsixity.db` (dev) and
  `~/Library/Application Support/Newsixity/newsixity.db` (packaged macOS app)
  hold real reading history and are not reproducible from the repo.
- **Reproduce a bug with a failing test before fixing it**, and show the full
  suite green afterwards — not just the new test.