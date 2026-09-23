from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_BACKEND_ENV = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # Groq API
    groq_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GROQ_API_KEY", "GROK_API_KEY", "groq_api_key", "grok_api_key"
        ),
    )
    groq_model: str = Field(
        default="qwen/qwen3.6-27b",
        validation_alias=AliasChoices(
            "GROQ_MODEL", "GROK_MODEL", "groq_model", "grok_model"
        ),
    )
    groq_whisper_model: str = Field(
        default="whisper-large-v3",
        validation_alias=AliasChoices(
            "GROQ_WHISPER_MODEL", "groq_whisper_model"
        ),
    )

    # OpenWeatherMap
    openweather_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENWEATHER_API_KEY", "openweather_api_key"
        ),
    )

    # TomTom Traffic (optional — live accidents / congestion near user)
    tomtom_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("TOMTOM_API_KEY", "tomtom_api_key"),
    )

    # Google Maps Platform
    google_maps_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_MAPS_API_KEY", "google_maps_api_key"
        ),
    )

    # Firebase (FCM push + Firestore fallback)
    firebase_credentials_path: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FIREBASE_CREDENTIALS_PATH", "firebase_credentials_path"
        ),
    )
    firebase_project_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FIREBASE_PROJECT_ID",
            "NEXT_PUBLIC_FIREBASE_PROJECT_ID",
        ),
    )
    firebase_client_email: str = Field(
        default="",
        validation_alias=AliasChoices("FIREBASE_CLIENT_EMAIL", "firebase_client_email"),
    )
    firebase_private_key: str = Field(
        default="",
        validation_alias=AliasChoices("FIREBASE_PRIVATE_KEY", "firebase_private_key"),
    )
    firebase_alert_topic: str = Field(
        default="resq_alerts",
        validation_alias=AliasChoices(
            "FIREBASE_ALERT_TOPIC", "firebase_alert_topic"
        ),
    )

    # Defaults (used when the client doesn't send a location)
    default_city: str = Field(
        default="Hyderabad",
        validation_alias=AliasChoices("DEFAULT_CITY", "default_city"),
    )
    default_lat: float = Field(
        default=17.3850,
        validation_alias=AliasChoices("DEFAULT_LAT", "default_lat"),
    )
    default_lon: float = Field(
        default=78.4867,
        validation_alias=AliasChoices("DEFAULT_LON", "default_lon"),
    )

    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    # Redis Agent Memory (chat session + semantic recall)
    redis_agent_memory_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "REDIS_AGENT_MEMORY_KEY",
            "REDIS_AGENT_MEMORY_API_KEY",
            "AGENT_MEMORY_API_KEY",
        ),
    )
    redis_agent_memory_url: str = Field(
        default="https://aws-us-east-1.memory.redis.io",
        validation_alias=AliasChoices(
            "REDIS_AGENT_MEMORY_URL",
            "AGENT_MEMORY_URL",
        ),
    )
    redis_agent_memory_store_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "REDIS_AGENT_MEMORY_STORE_ID",
            "AGENT_MEMORY_STORE_ID",
        ),
    )

    # Supabase (Postgres persistence — preferred over Firestore when configured)
    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    supabase_service_role_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SECRET_KEY",
        ),
    )
    supabase_anon_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_ANON_KEY",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        ),
    )
    postgres_url: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_URL", "POSTGRES_PRISMA_URL"),
    )
    postgres_url_non_pooling: str = Field(
        default="",
        validation_alias=AliasChoices(
            "POSTGRES_URL_NON_POOLING",
            "postgres_url_non_pooling",
        ),
    )
    supabase_storage_bucket: str = Field(
        default="resq-assets",
        validation_alias=AliasChoices(
            "SUPABASE_STORAGE_BUCKET",
            "supabase_storage_bucket",
        ),
    )
    triage_ml_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("TRIAGE_ML_ENABLED", "triage_ml_enabled"),
    )

    # Vercel Cron / external keep-alive scheduler
    cron_secret: str = Field(
        default="",
        validation_alias=AliasChoices("CRON_SECRET", "cron_secret"),
    )
    keepalive_secret: str = Field(
        default="",
        validation_alias=AliasChoices("KEEPALIVE_SECRET", "keepalive_secret"),
    )

    supabase_max_upload_bytes: int = Field(
        default=5 * 1024 * 1024,
        validation_alias=AliasChoices(
            "SUPABASE_MAX_UPLOAD_BYTES",
            "supabase_max_upload_bytes",
        ),
    )

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_groq_available(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.strip())

    @property
    def is_agent_memory_available(self) -> bool:
        return bool(
            self.redis_agent_memory_api_key.strip()
            and self.redis_agent_memory_store_id.strip()
            and self.redis_agent_memory_url.strip()
        )

    @property
    def is_supabase_available(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_service_role_key.strip())


settings = Settings()
