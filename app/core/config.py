"""
Configuration centrale de l'application via Pydantic-Settings.
Charge les variables d'environnement obligatoires et optionnelles.

Validation conditionnelle : les clés propres à chaque fournisseur LLM
ne sont obligatoires que lorsque ce fournisseur est sélectionné
(LLM_PROVIDER=mistral → MISTRAL_API_KEY requise ;
 LLM_PROVIDER=vertex  → GCP_PROJECT_ID requise).
"""

from typing import Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Base de données PostgreSQL (OBLIGATOIRE)
    # ------------------------------------------------------------------ #
    DATABASE_URL: str

    # ------------------------------------------------------------------ #
    # Fournisseur LLM (OBLIGATOIRE) : "mistral" | "vertex"
    # ------------------------------------------------------------------ #
    LLM_PROVIDER: Literal["mistral", "vertex"] = "mistral"

    # ------------------------------------------------------------------ #
    # Mistral AI (requis uniquement si LLM_PROVIDER=mistral)
    # ------------------------------------------------------------------ #
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_CHAT_MODEL: str = "mistral-large-latest"
    MISTRAL_EMBED_MODEL: str = "mistral-embed"

    # ------------------------------------------------------------------ #
    # Vertex AI / Google Cloud (requis uniquement si LLM_PROVIDER=vertex)
    # ------------------------------------------------------------------ #
    GCP_PROJECT_ID: Optional[str] = None
    GCP_LOCATION: str = "europe-west1"
    GEMINI_MODEL: str = "gemini-3-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-multilingual-embedding-002"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # ------------------------------------------------------------------ #
    # JWT (authentification)
    # ------------------------------------------------------------------ #
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ------------------------------------------------------------------ #
    # ChromaDB
    # ------------------------------------------------------------------ #
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # ------------------------------------------------------------------ #
    # Application générale
    # ------------------------------------------------------------------ #
    APP_TITLE: str = "Assistant Juridique Malgache — API"
    APP_VERSION: str = "0.1.0"
    APP_PORT: int = 8080
    DEBUG: bool = False

    # ------------------------------------------------------------------ #
    # Validation conditionnelle des secrets par fournisseur
    # ------------------------------------------------------------------ #
    @model_validator(mode="after")
    def _validate_provider_credentials(self) -> "Settings":
        if self.LLM_PROVIDER == "mistral":
            if not self.MISTRAL_API_KEY:
                raise ValueError(
                    "MISTRAL_API_KEY est obligatoire lorsque LLM_PROVIDER=mistral."
                )
        if self.LLM_PROVIDER == "vertex":
            if not self.GCP_PROJECT_ID:
                raise ValueError(
                    "GCP_PROJECT_ID est obligatoire lorsque LLM_PROVIDER=vertex."
                )
            if self.GOOGLE_APPLICATION_CREDENTIALS:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.GOOGLE_APPLICATION_CREDENTIALS
        return self


# Singleton importé par tous les modules
settings = Settings()
