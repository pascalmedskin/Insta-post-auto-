"""Configuration centralisée, chargée depuis l'environnement / fichier .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "app" / "static" / "media"
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Serveur
    public_base_url: str = "http://localhost:8000"

    # Génération texte (Claude)
    anthropic_api_key: str = ""
    text_model: str = "claude-sonnet-4-6"

    # Génération image (OpenAI)
    openai_api_key: str = ""
    image_model: str = "gpt-image-1"

    # Instagram Graph API (legacy .env config, overridden by per-brand OAuth)
    ig_access_token: str = ""
    ig_business_account_id: str = ""
    ig_graph_version: str = "v21.0"

    # Meta / Facebook OAuth (for Instagram connection)
    meta_app_id: str = ""
    meta_app_secret: str = ""
    # Facebook Login for Business : ID de configuration de connexion.
    # Requis pour les apps de type « Entreprise » (le scope seul ne suffit plus).
    meta_login_config_id: str = ""

    # Scheduler
    scheduler_timezone: str = "Europe/Zurich"
    autopost_enabled: bool = True

    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"

    @property
    def has_text_ai(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_image_ai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_instagram(self) -> bool:
        return bool(self.ig_access_token and self.ig_business_account_id)

    @property
    def has_meta_oauth(self) -> bool:
        return bool(self.meta_app_id and self.meta_app_secret)


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()


settings = get_settings()
