"""
Point d'entrée principal de l'API FastAPI — Assistant Juridique Malgache.

Responsabilités :
  - Initialise la connexion à la base de données au démarrage (lifespan).
  - Importe les modèles SQLAlchemy avant create_all pour garantir
    l'enregistrement des tables dans Base.metadata.
  - Monte les routeurs de l'API sous le préfixe /api/v1.
  - Expose l'endpoint /health pour les health-checks (load balancer, K8s, etc.).
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import settings
from app.db.database import check_db_connection, create_all_tables
from app.schemas.common import build_error_response

# Configuration du logging pour toute l'application
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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

    logger.info(
        "=== Assistant Juridique Malgache démarré | provider=%s | debug=%s ===",
        settings.LLM_PROVIDER,
        settings.DEBUG,
    )

    yield

    # --- Shutdown ---
    logger.info("=== Assistant Juridique Malgache arrêté ===")


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
# Custom Exception Handlers
# --------------------------------------------------------------------------- #
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Gère les exceptions HTTPException en renvoyant une réponse standardisée
    avec le format {status: "error", error: {...}}.
    """
    # Si le détail est déjà une réponse d'erreur standardisée (dict), on l'utilise
    if isinstance(exc.detail, dict):
        return JSONResponse(content=exc.detail, status_code=exc.status_code)
    # Sinon, on construit une réponse d'erreur standardisée
    return JSONResponse(
        content=build_error_response(
            code=f"HTTP_{exc.status_code}",
            message=exc.detail if isinstance(exc.detail, str) else "Erreur inattendue"
        ).model_dump(),
        status_code=exc.status_code
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """
    Gère les exceptions de validation Pydantic en renvoyant une réponse
    standardisée avec les détails des champs invalides.
    """
    errors = [
        {
            "loc": err["loc"],
            "msg": err["msg"],
            "type": err["type"]
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        content=build_error_response(
            code="VALIDATION_ERROR",
            message="Erreur de validation des données fournies.",
            fields=errors
        ).model_dump(),
        status_code=422
    )



# --------------------------------------------------------------------------- #
# Middlewares
# --------------------------------------------------------------------------- #
# CORS ouvert pour le développement local et les appels front-end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
