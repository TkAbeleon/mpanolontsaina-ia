# =============================================================================
# tests/test_validation.py
#
# Suite de tests de VALIDATION D'ARCHITECTURE — à exécuter localement pour
# vérifier la cohérence structurelle du projet avant tout déploiement.
#
# Ces tests ne font AUCUN appel réseau réel (pas de PostgreSQL, pas de Mistral,
# pas de Vertex AI). Ils valident :
#   1. Le contrat de l'endpoint /health via FastAPI TestClient (DB mockée).
#   2. Le bon instanciement du fournisseur LLM par la factory selon LLM_PROVIDER.
#   3. Le chargement correct des paramètres critiques via Pydantic-Settings.
#
# Lancement :
#   pytest tests/test_validation.py -v
# =============================================================================

from __future__ import annotations

from types import SimpleNamespace
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# --------------------------------------------------------------------------- #
# Fixtures globales
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Injecte les variables d'environnement minimales requises par Pydantic-Settings
    pour que l'application puisse démarrer sans fichier .env réel.
    Ces valeurs sont factices et ne donnent accès à aucun service.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://test:test@localhost:5432/test_db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-suffisamment-longue-pour-les-tests")
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-test-fake-key-for-architecture-tests")
    monkeypatch.setenv("MISTRAL_CHAT_MODEL", "mistral-large-latest")
    monkeypatch.setenv("MISTRAL_EMBED_MODEL", "mistral-embed")


@pytest.fixture()
def app_client() -> Generator[TestClient, None, None]:
    """
    Fournit un TestClient FastAPI avec la connexion PostgreSQL mockée
    (check_db_connection retourne True sans connexion réelle).
    """
    with (
        patch("app.db.database.check_db_connection", return_value=True),
        patch("app.db.database.create_all_tables", return_value=None),
    ):
        from app.main import app  # noqa: PLC0415

        with TestClient(app, raise_server_exceptions=True) as client:
            yield client


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_fake_settings(**overrides) -> SimpleNamespace:
    """
    Construit un objet settings factice utilisé pour patcher app.core.config.settings
    à l'intérieur des fonctions qui importent settings localement (ex: factory.py).
    On contrôle uniquement les attributs nécessaires aux tests.
    """
    defaults = {
        "LLM_PROVIDER": "mistral",
        "MISTRAL_API_KEY": "sk-test-fake-key",
        "MISTRAL_CHAT_MODEL": "mistral-large-latest",
        "MISTRAL_EMBED_MODEL": "mistral-embed",
        "GCP_PROJECT_ID": "",
        "GCP_LOCATION": "europe-west1",
        "GEMINI_MODEL": "gemini-3-flash",
        "GEMINI_EMBEDDING_MODEL": "text-multilingual-embedding-002",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# --------------------------------------------------------------------------- #
# Tests — Endpoint /health
# --------------------------------------------------------------------------- #

class TestHealthEndpoint:
    """Valide le comportement de l'endpoint GET /health."""

    def test_health_returns_200_when_db_is_reachable(
        self, app_client: TestClient
    ) -> None:
        """
        Scénario nominal : la base de données est accessible.
        L'endpoint doit retourner HTTP 200 avec status="healthy".
        """
        with patch("app.main.check_db_connection", return_value=True):
            response = app_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["dependencies"]["postgresql"] == "ok"
        assert "timestamp" in body
        assert "version" in body

    def test_health_returns_503_when_db_is_unreachable(
        self, app_client: TestClient
    ) -> None:
        """
        Scénario dégradé : la base de données est inaccessible.
        L'endpoint doit retourner HTTP 503 avec status="degraded".
        """
        with patch("app.main.check_db_connection", return_value=False):
            response = app_client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["dependencies"]["postgresql"] == "unreachable"

    def test_health_response_contains_llm_provider_field(
        self, app_client: TestClient
    ) -> None:
        """
        Le champ llm_provider doit être présent dans la réponse /health
        pour permettre la vérification opérationnelle du fournisseur actif.
        """
        with patch("app.main.check_db_connection", return_value=True):
            response = app_client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert "llm_provider" in body
        assert body["llm_provider"] in ("mistral", "vertex")


# --------------------------------------------------------------------------- #
# Tests — Factory LLM Provider
# --------------------------------------------------------------------------- #

class TestLLMProviderFactory:
    """
    Valide que la factory get_llm_provider() instancie le bon adaptateur
    en fonction de LLM_PROVIDER.

    Stratégie de mock :
      - factory.py importe `settings` à l'intérieur de get_llm_provider() via
        `from app.core.config import settings`. La cible de patch correcte est
        donc `app.core.config.settings`, qui est remplacé par un SimpleNamespace
        contrôlé pour chaque test.
      - Le cache lru_cache est vidé avant chaque test pour forcer la
        ré-instanciation du provider.
    """

    @pytest.fixture(autouse=True)
    def _clear_factory_cache(self) -> Generator[None, None, None]:
        """Vide le cache lru_cache de get_llm_provider avant et après chaque test."""
        from app.providers import factory as factory_module  # noqa: PLC0415
        factory_module.get_llm_provider.cache_clear()
        yield
        factory_module.get_llm_provider.cache_clear()

    def test_factory_returns_mistral_provider_when_llm_provider_is_mistral(self) -> None:
        """
        LLM_PROVIDER=mistral → la factory doit retourner une instance de MistralProvider.
        Le client Mistral est mocké pour éviter tout appel réseau.
        """
        fake_settings = _make_fake_settings(LLM_PROVIDER="mistral")

        with (
            patch("app.core.config.settings", fake_settings),
            patch("app.providers.mistral.Mistral", return_value=MagicMock()),
        ):
            from app.providers import factory as factory_module  # noqa: PLC0415
            from app.providers.mistral import MistralProvider  # noqa: PLC0415

            provider = factory_module.get_llm_provider()

        assert isinstance(provider, MistralProvider)

    def test_factory_returns_vertex_provider_when_llm_provider_is_vertex(self) -> None:
        """
        LLM_PROVIDER=vertex → la factory doit retourner une instance de VertexAIProvider.
        Le client Vertex AI est mocké pour éviter toute authentification GCP réelle.
        """
        fake_settings = _make_fake_settings(
            LLM_PROVIDER="vertex",
            GCP_PROJECT_ID="test-gcp-project",
        )

        mock_genai = MagicMock()
        mock_genai.Client.return_value = MagicMock()

        with (
            patch("app.core.config.settings", fake_settings),
            patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_genai}),
            patch("app.providers.vertex.settings", fake_settings),
        ):
            from app.providers import factory as factory_module  # noqa: PLC0415
            from app.providers.vertex import VertexAIProvider  # noqa: PLC0415

            provider = factory_module.get_llm_provider()

        assert isinstance(provider, VertexAIProvider)

    def test_factory_raises_value_error_for_unknown_provider(self) -> None:
        """
        Un LLM_PROVIDER non reconnu doit lever une ValueError explicite
        plutôt que de démarrer dans un état incohérent.
        """
        fake_settings = _make_fake_settings(LLM_PROVIDER="openai_inconnu")

        with patch("app.core.config.settings", fake_settings):
            from app.providers import factory as factory_module  # noqa: PLC0415

            with pytest.raises(ValueError, match="inconnu"):
                factory_module.get_llm_provider()

    def test_factory_singleton_returns_same_instance(self) -> None:
        """
        Le décorateur lru_cache garantit que la factory retourne toujours
        la même instance (pattern singleton). Deux appels successifs doivent
        retourner le même objet.
        """
        fake_settings = _make_fake_settings(LLM_PROVIDER="mistral")

        with (
            patch("app.core.config.settings", fake_settings),
            patch("app.providers.mistral.Mistral", return_value=MagicMock()),
        ):
            from app.providers import factory as factory_module  # noqa: PLC0415

            provider_1 = factory_module.get_llm_provider()
            provider_2 = factory_module.get_llm_provider()

        assert provider_1 is provider_2


# --------------------------------------------------------------------------- #
# Tests — Chargement des paramètres critiques (Pydantic-Settings)
# --------------------------------------------------------------------------- #

class TestSettings:
    """
    Valide que Pydantic-Settings charge et expose correctement
    les paramètres critiques de l'application.

    Ces tests vérifient le singleton `settings` déjà instancié au démarrage
    du process (chargé depuis les variables injectées par _required_env_vars).
    Les tests de validation du modèle Pydantic (champs manquants, valeurs
    invalides) instancient directement la classe Settings avec des arguments
    explicites, indépendamment du singleton.
    """

    def test_settings_loads_database_url(self) -> None:
        """DATABASE_URL doit être présent et démarrer par 'postgresql'."""
        from app.core.config import settings  # noqa: PLC0415

        assert settings.DATABASE_URL
        assert settings.DATABASE_URL.startswith("postgresql")

    def test_settings_loads_llm_provider(self) -> None:
        """LLM_PROVIDER doit valoir 'mistral' ou 'vertex'."""
        from app.core.config import settings  # noqa: PLC0415

        assert settings.LLM_PROVIDER in ("mistral", "vertex")

    def test_settings_loads_jwt_secret_key(self) -> None:
        """JWT_SECRET_KEY doit être présent et non vide."""
        from app.core.config import settings  # noqa: PLC0415

        assert settings.JWT_SECRET_KEY
        assert len(settings.JWT_SECRET_KEY) > 0

    def test_settings_model_rejects_missing_mistral_key_when_provider_is_mistral(self) -> None:
        """
        Validation du modèle Pydantic : si LLM_PROVIDER=mistral et
        MISTRAL_API_KEY est None, Settings doit lever une ValidationError.
        Ce test instancie Settings directement (pas le singleton) pour
        contrôler précisément les valeurs passées.
        """
        from pydantic import ValidationError  # noqa: PLC0415

        from app.core.config import Settings  # noqa: PLC0415

        with pytest.raises(ValidationError, match="MISTRAL_API_KEY"):
            Settings(
                DATABASE_URL="postgresql+psycopg2://test:test@localhost/test",
                JWT_SECRET_KEY="test-secret-key-longue-pour-validation",
                LLM_PROVIDER="mistral",
                MISTRAL_API_KEY=None,  # type: ignore[arg-type]
            )

    def test_settings_model_rejects_missing_gcp_project_when_provider_is_vertex(self) -> None:
        """
        Validation du modèle Pydantic : si LLM_PROVIDER=vertex et
        GCP_PROJECT_ID est None/vide, Settings doit lever une ValidationError.
        """
        from pydantic import ValidationError  # noqa: PLC0415

        from app.core.config import Settings  # noqa: PLC0415

        with pytest.raises(ValidationError, match="GCP_PROJECT_ID"):
            Settings(
                DATABASE_URL="postgresql+psycopg2://test:test@localhost/test",
                JWT_SECRET_KEY="test-secret-key-longue-pour-validation",
                LLM_PROVIDER="vertex",
                MISTRAL_API_KEY=None,
                GCP_PROJECT_ID=None,  # type: ignore[arg-type]
            )

    def test_settings_default_values_are_sane(self) -> None:
        """
        Les valeurs par défaut doivent être cohérentes avec les spécifications
        techniques (JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, etc.).
        """
        from app.core.config import settings  # noqa: PLC0415

        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS > 0
        assert settings.CHROMA_PERSIST_DIR
        assert settings.APP_VERSION
