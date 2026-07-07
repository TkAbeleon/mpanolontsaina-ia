"""
Connexion PostgreSQL via SQLAlchemy 2.x.
Expose : engine, SessionLocal, Base, get_db (dépendance FastAPI).
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# --------------------------------------------------------------------------- #
# Moteur SQLAlchemy
# --------------------------------------------------------------------------- #
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          # vérifie la connexion avant chaque usage
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,         # log SQL brut en mode DEBUG
)

# --------------------------------------------------------------------------- #
# Fabrique de sessions
# --------------------------------------------------------------------------- #
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# --------------------------------------------------------------------------- #
# Base déclarative partagée par tous les modèles
# --------------------------------------------------------------------------- #
class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Dépendance FastAPI — injection de session dans les contrôleurs
# --------------------------------------------------------------------------- #
def get_db() -> Generator[Session, None, None]:
    """
    Générateur utilisé via `Depends(get_db)` dans les routes FastAPI.
    Garantit que la session est fermée après chaque requête, même en cas d'erreur.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Gestionnaire de contexte pour les scripts hors FastAPI (seeds, migrations…)
# --------------------------------------------------------------------------- #
@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def create_all_tables() -> None:
    """Crée toutes les tables définies dans les modèles (dev / tests uniquement)."""
    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    """Vérifie que la base de données est accessible. Utilisé par /health."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
