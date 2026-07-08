"""
Dépendances FastAPI pour l'injection de dépendances (session DB, utilisateur courant, etc.).
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.db.models import User

# =============================================================================
# Sécurité : récupération de l'utilisateur courant via JWT
# =============================================================================
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dépendance FastAPI pour récupérer l'utilisateur actuellement connecté via JWT.
    Lève une HTTPException 401 si le token est absent ou invalide.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token d'accès manquant ou invalide",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials or not credentials.credentials:
        raise credentials_exception

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise credentials_exception

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active == True, User.is_deleted == False).first()
    if not user:
        raise credentials_exception

    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dépendance FastAPI pour récupérer l'utilisateur courant (optionnel).
    Retourne None si pas de token ou token invalide, au lieu de lever une exception.
    """
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None
