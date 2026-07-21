from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Groq API
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    
    # OpenWeatherMap
    openweather_api_key: str

    # Google Maps Platform
    google_maps_api_key: str

    # Firebase (Firestore + Cloud Messaging)
    firebase_credentials_path: str = "firebase-service-account.json"
    firebase_alert_topic: str = "resq_alerts"

    # Defaults (used when the client doesn't send a location)
    default_city: str = "Hyderabad"
    default_lat: float = 17.3850
    default_lon: float = 78.4867

    cors_origins: str = "http://localhost:5500"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
