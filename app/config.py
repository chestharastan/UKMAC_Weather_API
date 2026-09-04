import os
from pathlib import Path

from dotenv import load_dotenv

API_DIR = Path(__file__).resolve().parents[1]
load_dotenv(API_DIR / ".env")


class Settings:
    app_name: str = os.getenv("APP_NAME", "Weather Monitor System")
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL", "")
    direct_database_url: str = os.getenv("DIRECT_DATABASE_URL", "")
    open_meteo_base_url: str = os.getenv(
        "OPEN_METEO_BASE_URL",
        "https://api.open-meteo.com/v1/forecast",
    )
    open_meteo_archive_url: str = os.getenv(
        "OPEN_METEO_ARCHIVE_URL",
        "https://archive-api.open-meteo.com/v1/archive",
    )
    weather_sync_interval_minutes: int = int(os.getenv("WEATHER_SYNC_INTERVAL_MINUTES", "45"))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:8000,http://localhost:8000",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
