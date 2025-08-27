# backend/app/core/config.py
from __future__ import annotations

import os
import json
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

# --- dotenv (safe if not installed) ---
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*args: Any, **kwargs: Any) -> None:
        return None

# --- pydantic v2 settings ---
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, AnyHttpUrl

# Compute project paths robustly no matter where uvicorn is run from
_THIS_FILE = Path(__file__).resolve()
CORE_DIR = _THIS_FILE.parent
APP_DIR = CORE_DIR.parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent

# Load .env from repo root if present (without requiring shell `export`)
load_dotenv(REPO_ROOT / ".env")
# Also load a backend-scoped .env if you keep one there
load_dotenv(BACKEND_DIR / ".env")
# And finally allow an app-local .env (lowest priority)
load_dotenv(APP_DIR / ".env")


def _default_gdrive_creds() -> Path:
    # your canonical location
    return BACKEND_DIR / "credentials" / "google_credentials.json"


def _default_rag_index() -> Path:
    # your canonical enhanced index location
    return BACKEND_DIR / "app" / "features" / "rag_chatbot" / "vector" / "enhanced_index.json"


class Settings(BaseSettings):
    """
    Central application settings.
    - Reads from environment AND .env (via python-dotenv above)
    - Keeps all prior fields but adds safe defaults + validators
    """

    # ---- App / server ----
    APP_NAME: str = Field(default="opsvista-backend")
    APP_ENV: str = Field(default=os.getenv("APP_ENV", "local"))
    DEBUG: bool = Field(default=os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"})
    LOG_LEVEL: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))

    # CORS
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: json.loads(os.getenv("CORS_ALLOWED_ORIGINS", "[]") or "[]")
    )

    # ---- Supabase (optional unless finance/tasks needs it) ----
    SUPABASE_URL: Optional[AnyHttpUrl] = Field(default=os.getenv("SUPABASE_URL") or None)
    SUPABASE_ANON_KEY: Optional[str] = Field(default=os.getenv("SUPABASE_ANON_KEY") or None)
    SUPABASE_SERVICE_KEY: Optional[str] = Field(default=os.getenv("SUPABASE_SERVICE_KEY") or None)
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(default=os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None)
    SUPABASE_JWT_SECRET: Optional[str] = Field(default=os.getenv("SUPABASE_JWT_SECRET") or None)

    # ---- Database (optional; many flows use Supabase directly) ----
    DATABASE_URL: Optional[str] = Field(default=os.getenv("DATABASE_URL") or None)

    # ---- OpenAI / embeddings ----
    OPENAI_API_KEY: Optional[str] = Field(default=os.getenv("OPENAI_API_KEY") or None)
    OPENAI_MODEL: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    OPENAI_TEMPERATURE: float = Field(default=float(os.getenv("OPENAI_TEMPERATURE", "0.2")))
    OPENAI_MAX_TOKENS: int = Field(default=int(os.getenv("OPENAI_MAX_TOKENS", "1000")))

    # Use real embeddings if API key present, otherwise mock (can be overridden by env)
    USE_MOCK_EMBEDDINGS: bool = Field(
        default=os.getenv("USE_MOCK_EMBEDDINGS", "false" if os.getenv("OPENAI_API_KEY") else "true").lower()
        in {"1", "true", "yes"}
    )
    OPENAI_EMBEDDING_MODEL: str = Field(default=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))

    # RAG index defaults (works for your integrated vector store)
    RAG_INDEX_PATH: Path = Field(default_factory=_default_rag_index)
    RAG_EMBEDDING_DIM: int = Field(default=int(os.getenv("RAG_EMBEDDING_DIM", "1536")))

    # ---- Google Drive integration ----
    GOOGLE_DRIVE_ENABLED: bool = Field(
        default=os.getenv("GOOGLE_DRIVE_ENABLED", "true").lower() in {"1", "true", "yes"}
    )
    GOOGLE_DRIVE_CREDENTIALS_PATH: Path = Field(
        default_factory=_default_gdrive_creds
    )
    # Comma-separated in env -> list here
    GOOGLE_DRIVE_FOLDER_IDS: List[str] = Field(
        default_factory=lambda: [s for s in (os.getenv("GOOGLE_DRIVE_FOLDER_IDS") or "").split(",") if s.strip()]
    )

    # ---- Feature toggles (keep flexible) ----
    FEATURE_FINANCE: bool = Field(default=os.getenv("FEATURE_FINANCE", "true").lower() in {"1", "true", "yes"})
    FEATURE_TASKS: bool = Field(default=os.getenv("FEATURE_TASKS", "true").lower() in {"1", "true", "yes"})
    FEATURE_RAG: bool = Field(default=os.getenv("FEATURE_RAG", "true").lower() in {"1", "true", "yes"})

    # ---- Static paths ----
    STATIC_DIR: Path = Field(default=APP_DIR / "static")

    # pydantic v2 config
    model_config = SettingsConfigDict(env_file=None, extra="allow")

    # -------- Validators / post-init tweaks --------

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _coerce_cors(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str) and v.strip():
            # allow simple comma-separated forms without JSON
            if v.strip().startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [s.strip() for s in v.split(",") if s.strip()]
        return []

    @field_validator("GOOGLE_DRIVE_CREDENTIALS_PATH", mode="after")
    @classmethod
    def _warn_if_gdrive_missing(cls, p: Path) -> Path:
        # Don’t fail startup if GDrive creds are missing; routes can skip gracefully.
        if p and not p.exists():
            warnings.warn(
                f"Google Drive credentials not found at: {p}. "
                f"Set GOOGLE_DRIVE_CREDENTIALS_PATH or place file there."
            )
        return p

    @field_validator("RAG_INDEX_PATH", mode="after")
    @classmethod
    def _note_rag_index(cls, p: Path) -> Path:
        # Safe note; many code paths can build the index on the fly.
        if p and not p.exists():
            warnings.warn(
                f"RAG index file not found at: {p}. "
                f"Vector search will fall back to mock/empty store unless you seed it."
            )
        return p

    @field_validator("USE_MOCK_EMBEDDINGS", mode="after")
    @classmethod
    def _respect_openai_key(cls, use_mock: bool) -> bool:
        # If user provided OPENAI_API_KEY but also forced USE_MOCK_EMBEDDINGS=true, keep it.
        # Otherwise, auto-enable mock if key is absent.
        if os.getenv("OPENAI_API_KEY"):
            return use_mock
        return True

    # Convenience helpers (don’t break existing imports)
    @property
    def has_supabase(self) -> bool:
        return bool(self.SUPABASE_URL and (self.SUPABASE_ANON_KEY or self.SUPABASE_SERVICE_KEY))

    @property
    def gdrive_ready(self) -> bool:
        return bool(self.GOOGLE_DRIVE_ENABLED and self.GOOGLE_DRIVE_CREDENTIALS_PATH.exists())

    @property
    def repo_root(self) -> Path:
        return REPO_ROOT

    @property
    def backend_dir(self) -> Path:
        return BACKEND_DIR


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Keep backward-compat for `from app.core.config import settings`
settings = get_settings()

__all__ = ["Settings", "get_settings", "settings", "REPO_ROOT", "BACKEND_DIR", "APP_DIR"]
