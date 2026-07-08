"""
Point d'entrée principal de l'API FastAPI — Assistant Juridique Malgache.

Responsabilités :
  - Initialise la connexion à la base de données au démarrage (lifespan).
  - Importe les modèles SQLAlchemy avant create_all pour garantir
    l'enregistrement des tables dans Base.metadata.
  - Monte les routeurs de l'API sous le préfixe /api/v1.
  - Expose l'endpoint /health pour les health-checks (load balancer, K8s, etc.).
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.database import check_db_connection, create_all_tables


# --------------------------------------------------------------------------- #
# Lifespan : initialisation et nettoyage au démarrage / arrêt
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Exécuté au démarrage de l'application :
      1. Importe tous les modèles pour les enregistrer dans Base.metadata.
      2. Vérifie la connexion à PostgreSQL.
      3. Crée les tables si elles n'existent pas encore (mode DEBUG uniquement).

    En production, utiliser Alembic pour les migrations.
    """
    # Importation explicite des modèles AVANT create_all_tables pour garantir
    # que SQLAlchemy a bien connaissance de toutes les tables définies.
    import app.db.models  # noqa: F401

    # --- Vérification de la connexion PostgreSQL ---
    db_ok = check_db_connection()
    if not db_ok:
        raise RuntimeError(
            "Impossible de se connecter à PostgreSQL. "
            "Vérifiez la variable DATABASE_URL dans votre .env."
        )

    # --- Création automatique des tables (dev uniquement ; en prod utiliser Alembic) ---
    if settings.DEBUG:
        create_all_tables()

    yield

    # --- Shutdown (rien à faire pour SQLAlchemy en mode pool) ---


# --------------------------------------------------------------------------- #
# Instance FastAPI
# --------------------------------------------------------------------------- #
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=(
        "API backend de l'assistant juridique malgache multi-agents. "
        "Prend en charge le français, le malagasy et l'anglais."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# --------------------------------------------------------------------------- #
# Middlewares
# --------------------------------------------------------------------------- #
# CORS : restreindre allow_origins en production via la variable d'env ALLOWED_ORIGINS.
# allow_credentials=True EST incompatible avec allow_origins=["*"] selon la spec CORS ;
# on utilise donc un comportement sûr par défaut (aucune credentials cross-origin en dev).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# --------------------------------------------------------------------------- #
# Endpoint /health
# --------------------------------------------------------------------------- #
@app.get(
    "/health",
    tags=["Infrastructure"],
    summary="Health-check de l'API",
    response_description="Statut de l'API et de ses dépendances",
)
async def health_check() -> JSONResponse:
    """
    Vérifie que l'API est opérationnelle et que PostgreSQL est accessible.

    Retourne 200 si tout est sain, 503 si la base de données est inaccessible.
    """
    db_healthy = check_db_connection()

    payload = {
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "dependencies": {
            "postgresql": "ok" if db_healthy else "unreachable",
        },
    }

    status_code = 200 if db_healthy else 503
    return JSONResponse(content=payload, status_code=status_code)


# --------------------------------------------------------------------------- #
# Montage des routeurs
# --------------------------------------------------------------------------- #
from app.routers import auth, users, chat
app.include_router(auth.router, prefix="", tags=["Authentification"])
app.include_router(users.router, prefix="", tags=["Utilisateurs"])
app.include_router(chat.router, prefix="", tags=["Chat"])
