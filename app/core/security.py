"""
Utilitaires de sécurité : hachage de mots de passe, génération et vérification JWT.
Référence : 02_contrats_api_auth_users.md
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4
import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """
    Hache un mot de passe en clair avec bcrypt.
    Tronque automatiquement à 72 octets comme recommandé par bcrypt.
    """
    # bcrypt ne supporte que 72 octets max
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie qu'un mot de passe en clair correspond à son hash.
    """
    plain_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Génère un JWT access token.
    Par défaut, valide pendant ACCESS_TOKEN_EXPIRE_MINUTES (60 minutes).
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Décode et vérifie un JWT access token.
    Retourne le payload si le token est valide, sinon None.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def create_refresh_token() -> tuple[UUID, str]:
    """
    Génère un refresh token (UUID).
    Retourne : (token_uuid, token_str)
    - token_uuid : UUID à stocker dans la base de données
    - token_str : chaîne de caractères à renvoyer au client
    """
    token = uuid4()
    return token, str(token)
