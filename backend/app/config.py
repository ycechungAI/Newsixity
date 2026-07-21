"""Application settings.

Mirrors the environment variables the Next.js app understood so the migrated
backend is a drop-in on the same machine:

  NEWSIXITY_DB_PATH                       override for the SQLite file location
  NEWSIXITY_DISABLE_BACKGROUND_SERVICES   "1" to skip RSS/summarize/backup jobs
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "newsixity.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEWSIXITY_", env_file=".env", extra="ignore")

    # Left as None so the default (the existing repo data/ DB) is computed lazily.
    db_path: str | None = Field(default=None)
    disable_background_services: bool = Field(default=False)

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    def resolve_db_path(self) -> Path:
        """Resolve the SQLite path, matching the Node app's rules.

        Absolute override wins; a relative override resolves against the repo
        root; otherwise fall back to the existing ``data/newsixity.db``.
        """
        override = (self.db_path or "").strip()
        if not override:
            return DEFAULT_DB_PATH
        p = Path(override)
        return p if p.is_absolute() else (REPO_ROOT / p)


settings = Settings()
