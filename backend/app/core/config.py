# backend/app/core/config.py
"""
Application Configuration Settings
"""

import os
import secrets
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator  # v2-style validators

RAG_INDEX_PATH = os.getenv("RAG_INDEX_PATH")  # may be None; chat.py fills it
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
USE_MOCK_EMBEDDINGS = os.getenv("USE_MOCK_EMBEDDINGS", "false").lower() == "true"


# --- locate project root and .env ---
# this file: <root>/backend/app/core/config.py
ROOT_DIR = Path(__file__).resolve().parents[3]  # -> <root>
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # APP
    # -------------------------------------------------------------------------
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536  # <- single authority
    USE_MOCK_EMBEDDINGS: bool = False
    APP_NAME: str = Field(default="OpsVista Business Intelligence System")
    APP_VERSION: str = Field(default="1.0.0")
    ENVIRONMENT: str = Field(default="development")  # development|staging|production
    DEBUG: bool = Field(default=True)
    API_V1_STR: str = Field(default="/api/v1")

    # -------------------------------------------------------------------------
    # SERVER
    # -------------------------------------------------------------------------
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000, ge=1, le=65535)
    RELOAD: bool = Field(default=True)

    # -------------------------------------------------------------------------
    # SECURITY
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)
    ALGORITHM: str = Field(default="HS256")

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "https://opsvista.vercel.app",
        ]
    )
    ALLOWED_HOSTS: List[str] = Field(
        default=["localhost", "127.0.0.1", "0.0.0.0", "opsvista-api.com"]
    )
    ALLOWED_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    )
    ALLOWED_HEADERS: List[str] = Field(default=["*"])

    # -------------------------------------------------------------------------
    # DATABASE (Supabase)
    # -------------------------------------------------------------------------
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str

    # Make service key optional so we can fill it from SUPABASE_SERVICE_ROLE_KEY
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # These were raising "extra inputs are not permitted" — add them explicitly
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None  # alias for service key

    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = Field(default=20, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=30, ge=0, le=100)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1)

    # -------------------------------------------------------------------------
    # GOOGLE DRIVE
    # -------------------------------------------------------------------------
    GOOGLE_DRIVE_CREDENTIALS_PATH: str = Field(
        default="backend/credentials/google_credentials.json"
    )
    GOOGLE_DRIVE_FOLDERS: Dict[str, str] = Field(
        default={
            "finance": "Finance",
            "hr": "HR",
            "lc": "LC Documents",
            "inventory": "Inventory",
            "reports": "Reports",
        }
    )
    GOOGLE_DRIVE_SCOPES: List[str] = Field(
        default=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ]
    )
    GOOGLE_DRIVE_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)

    # -------------------------------------------------------------------------
    # RAG SETTINGS
    # -------------------------------------------------------------------------
    RAG_MAX_FILE_SIZE_MB: int = Field(default=50, ge=1, le=500)
    RAG_BATCH_SIZE: int = Field(default=10, ge=1, le=100)
    RAG_TIMEOUT_SECONDS: int = Field(default=300, ge=30, le=3600)
    RAG_MAX_RETRIES: int = Field(default=3, ge=0, le=10)
    RAG_EXCEL_MAX_SIZE_MB: int = Field(default=50, ge=1, le=200)
    RAG_PDF_MAX_SIZE_MB: int = Field(default=100, ge=1, le=500)
    RAG_CSV_MAX_SIZE_MB: int = Field(default=20, ge=1, le=100)
    RAG_EXCEL_SAMPLE_ROWS: int = Field(default=100, ge=10, le=1000)
    RAG_PDF_QUALITY_THRESHOLD: float = Field(default=0.7, ge=0.0, le=1.0)
    RAG_CLASSIFICATION_CONFIDENCE_THRESHOLD: float = Field(default=0.3, ge=0.0, le=1.0)

    # -------------------------------------------------------------------------
    # OPENAI (future)
    # -------------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = Field(default="gpt-4")
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    OPENAI_MAX_TOKENS: int = Field(default=4000, ge=100, le=8000)
    OPENAI_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    EMBEDDING_DIM: int = 1536  # <- single authority
    USE_MOCK_EMBEDDINGS: bool = False

    # -------------------------------------------------------------------------
    # EMAIL (Resend)
    # -------------------------------------------------------------------------
    RESEND_API_KEY: Optional[str] = None
    EMAIL_FROM: str = Field(default="noreply@opsvista.com")
    EMAIL_FROM_NAME: str = Field(default="OpsVista System")
    EMAIL_ENABLED: bool = Field(default=True)
    EMAIL_BATCH_SIZE: int = Field(default=50, ge=1, le=100)

    # -------------------------------------------------------------------------
    # REDIS / CELERY
    # -------------------------------------------------------------------------
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = Field(default=20, ge=1, le=100)
    REDIS_SOCKET_TIMEOUT: int = Field(default=5, ge=1, le=60)

    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")
    CELERY_TASK_SERIALIZER: str = Field(default="json")
    CELERY_ACCEPT_CONTENT: List[str] = Field(default=["json"])
    CELERY_TIMEZONE: str = Field(default="Asia/Dhaka")

    # -------------------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE_PATH: Optional[str] = None
    LOG_ROTATION_SIZE: str = Field(default="10MB")
    LOG_RETENTION_DAYS: int = Field(default=30, ge=1, le=365)
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    LOG_JSON: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # RATE LIMITS
    # -------------------------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=100, ge=1, le=10000)
    RAG_DISCOVERY_RATE_LIMIT: int = Field(default=5, ge=1, le=60)
    RAG_ANALYSIS_RATE_LIMIT: int = Field(default=10, ge=1, le=100)

    # -------------------------------------------------------------------------
    # BUSINESS
    # -------------------------------------------------------------------------
    COMPANY_NAME: str = Field(default="Precision Textile Industry Limited")
    COMPANY_TIMEZONE: str = Field(default="Asia/Dhaka")
    BUSINESS_HOURS_START: str = Field(default="08:00")
    BUSINESS_HOURS_END: str = Field(default="18:00")
    DEFAULT_CURRENCY: str = Field(default="BDT")
    SUPPORTED_CURRENCIES: List[str] = Field(default=["BDT", "USD", "EUR", "GBP"])
    DOCUMENT_PRIORITIES: Dict[str, int] = Field(
        default={
            "lc": 1,
            "finance": 2,
            "invoice": 3,
            "hr": 4,
            "inventory": 5,
            "reports": 6,
            "unknown": 8,
        }
    )

    # -------------------------------------------------------------------------
    # FEATURE FLAGS
    # -------------------------------------------------------------------------
    FEATURE_FINANCE_ENABLED: bool = Field(default=True)
    FEATURE_TASKS_ENABLED: bool = Field(default=True)
    FEATURE_RAG_ENABLED: bool = Field(default=True)
    FEATURE_INVENTORY_ENABLED: bool = Field(default=False)
    FEATURE_HR_ENABLED: bool = Field(default=False)
    FEATURE_CCTV_ENABLED: bool = Field(default=False)
    FEATURE_LOCATION_ENABLED: bool = Field(default=False)
    FEATURE_AI_CHAT_ENABLED: bool = Field(default=False)
    FEATURE_PREDICTIVE_ANALYTICS_ENABLED: bool = Field(default=False)

    # -------------------------------------------------------------------------
    # Pydantic Settings (v2)
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),          # load .env from project root
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        extra="allow",                   # <-- accept extra env keys (fixes errors)
    )

    # -------------------------------------------------------------------------
    # Normalization hook (v2)
    # -------------------------------------------------------------------------
    def model_post_init(self, __context: Any) -> None:
        """
        Normalize aliases coming from .env:
        - If SUPABASE_SERVICE_ROLE_KEY is provided but SUPABASE_SERVICE_KEY is not,
          copy it over so downstream code can rely on SUPABASE_SERVICE_KEY.
        """
        if not self.SUPABASE_SERVICE_KEY and self.SUPABASE_SERVICE_ROLE_KEY:
            object.__setattr__(
                self, "SUPABASE_SERVICE_KEY", self.SUPABASE_SERVICE_ROLE_KEY
            )

    # -------------------------------------------------------------------------
    # Validators (v2)
    # -------------------------------------------------------------------------
    @field_validator("ENVIRONMENT")
    @classmethod
    def _env_ok(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        lv = v.lower()
        if lv not in allowed:
            raise ValueError(f"Environment must be one of: {sorted(allowed)}")
        return lv

    @field_validator("DEBUG")
    @classmethod
    def _debug_auto_off_in_prod(cls, v: bool, info):
        env = (info.data.get("ENVIRONMENT") or "development").lower()
        return False if env == "production" else v

    @field_validator("LOG_LEVEL")
    @classmethod
    def _loglevel_ok(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        up = v.upper()
        if up not in allowed:
            raise ValueError(f"Log level must be one of: {sorted(allowed)}")
        return up

    @field_validator("GOOGLE_DRIVE_CREDENTIALS_PATH")
    @classmethod
    def _check_gdrive_path(cls, v: str) -> str:
        raw = (v or "").strip()
        # normalize "/backend/..." -> "backend/..." so it resolves from project root
        if raw.startswith("/backend/"):
            raw = raw.lstrip("/")
        p = (ROOT_DIR / raw).resolve() if not os.path.isabs(raw) else Path(raw)
        if not p.exists():
            env = os.getenv("ENVIRONMENT", "development").lower()
            msg = f"Warning: Google Drive credentials file not found: {p}"
            if env == "development":
                print(msg)
                return str(p)
            raise ValueError(f"Google Drive credentials file not found: {p}")
        return str(p)


    @field_validator("SUPABASE_URL")
    @classmethod
    def _supabase_url_ok(cls, v: str, info) -> str:
        env = (info.data.get("ENVIRONMENT") or "development").lower()
        # allow any https in dev so local boot is easy
        if env == "development":
            if not v.startswith("https://"):
                raise ValueError("SUPABASE_URL must start with https://")
            return v
        # stricter in staging/prod
        if not (v.startswith("https://") and ".supabase.co" in v):
            raise ValueError("SUPABASE_URL must be a valid Supabase project URL")
        return v

    # -------------------------------------------------------------------------
    # Computed
    # -------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def database_url_sync(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # fallback placeholder; override via env for real use
        return "postgresql://postgres:[password]@db.[project-id].supabase.co:5432/postgres"

    @property
    def rag_file_size_limits(self) -> Dict[str, int]:
        mb = 1024 * 1024
        return {
            "excel": self.RAG_EXCEL_MAX_SIZE_MB * mb,
            "pdf": self.RAG_PDF_MAX_SIZE_MB * mb,
            "csv": self.RAG_CSV_MAX_SIZE_MB * mb,
        }

    @property
    def cors_origins_list(self) -> List[str]:
        return self.ALLOWED_ORIGINS


def get_settings() -> Settings:
    return Settings()


def get_settings_for_environment(env: str) -> Settings:
    return Settings(ENVIRONMENT=env)


settings = get_settings()


def validate_settings() -> Dict[str, Any]:
    out = {"status": "valid", "warnings": [], "errors": [], "recommendations": []}

    if not settings.SUPABASE_URL:
        out["errors"].append("SUPABASE_URL is required")
    if not settings.SUPABASE_ANON_KEY:
        out["errors"].append("SUPABASE_ANON_KEY is required")
    if not settings.SUPABASE_SERVICE_KEY:
        out["errors"].append("SUPABASE_SERVICE_KEY is required")

    if settings.FEATURE_RAG_ENABLED:
        if not Path(settings.GOOGLE_DRIVE_CREDENTIALS_PATH).exists():
            out["warnings"].append(
                f"Google Drive credentials not found: {settings.GOOGLE_DRIVE_CREDENTIALS_PATH}"
            )

    if settings.is_production:
        if settings.SECRET_KEY == "your-secret-key":
            out["errors"].append("SECRET_KEY must be changed in production")
        if settings.DEBUG:
            out["warnings"].append("DEBUG should be False in production")
        if not settings.OPENAI_API_KEY and settings.FEATURE_AI_CHAT_ENABLED:
            out["warnings"].append("OPENAI_API_KEY required for AI features")

    if settings.RAG_BATCH_SIZE > 50:
        out["recommendations"].append(
            "Consider reducing RAG_BATCH_SIZE for better memory usage"
        )

    if out["errors"]:
        out["status"] = "invalid"
    elif out["warnings"]:
        out["status"] = "warning"
    return out


__all__ = [
    "Settings",
    "settings",
    "get_settings",
    "get_settings_for_environment",
    "validate_settings",
]
