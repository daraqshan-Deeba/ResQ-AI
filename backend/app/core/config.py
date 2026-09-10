from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Groq API
    groq_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GROQ_API_KEY", "GROK_API_KEY", "groq_api_key", "grok_api_key"
        ),
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        validation_alias=AliasChoices(
            "GROQ_MODEL", "GROK_MODEL", "groq_model", "grok_model"
        ),
    )

    # OpenWeatherMap
    openweather_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENWEATHER_API_KEY", "openweather_api_key"
        ),
    )

    # Google Maps Platform
    google_maps_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_MAPS_API_KEY", "google_maps_api_key"
        ),
    )

    # Firebase (Firestore + Cloud Messaging)
    firebase_credentials_path: str = Field(
        default="firebase-service-account.json",
        validation_alias=AliasChoices(
            "FIREBASE_CREDENTIALS_PATH", "firebase_credentials_path"
        ),
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
        default="http://localhost:5500",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_groq_available(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.strip())


settings = Settings()
