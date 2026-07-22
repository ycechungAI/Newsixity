"""Application settings.

Mirrors the environment variables the Next.js app understood so the migrated
backend is a drop-in on the same machine:

  NEWSIXITY_DB_PATH                       override for the SQLite file location
  NEWSIXITY_DISABLE_BACKGROUND_SERVICES   "1" to skip RSS/summarize/backup jobs
  NEWSIXITY_RESUMMARIZE_BATCH_SIZE        batch size for resummarization (0 = unlimited, default 50)
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

    # Batch size for resummarization endpoint. 0 = unlimited (for local LLM).
    # Defaults to 0 for local Ollama, 50 for cloud LLMs. Override with env var if needed.
    resummarize_batch_size: int | None = Field(default=None)

    def _get_default_batch_size(self) -> int:
        """Default to unlimited (0) for local Ollama, 50 for cloud LLMs."""
        # Check if Ollama is configured to run locally
        from app.db.repository import get_setting
        host = get_setting("ollama_host") or "http://localhost:11434"
        is_local = "localhost" in host or "127.0.0.1" in host
        return 0 if is_local else 50

    def get_resummarize_batch_size(self) -> int:
        """Get the effective batch size (explicit setting or smart default)."""
        if self.resummarize_batch_size is not None:
            return self.resummarize_batch_size
        return self._get_default_batch_size()

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
