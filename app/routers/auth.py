"""
Router d'authentification : register, login, refresh, logout.
Référence : 02_contrats_api_auth_users.md
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.db.models import RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.schemas.common import build_error_response, build_success_response

router = APIRouter(prefix="/api/v1/auth", tags=["Authentification"])


# =============================================================================
# POST /api/v1/auth/register
# =============================================================================
@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Inscription réussie"},
        409: {"description": "Email déjà utilisé"},
        422: {"description": "Erreur de validation"},
    },
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Inscription d'un nouvel utilisateur."""
    # Vérifie que l'email n'existe pas déjà
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_error_response(
                code="EMAIL_ALREADY_EXISTS",
                message="Un compte existe déjà avec cet email."
            ).model_dump()
        )

    # Crée le nouvel utilisateur
    hashed_pwd = hash_password(request.password)
    new_user = User(
        email=request.email,
        hashed_password=hashed_pwd,
        full_name=request.full_name,
        preferred_language=request.preferred_language,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Prépare la réponse
    response_data = RegisterResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        preferred_language=new_user.preferred_language,
        is_active=new_user.is_active,
        created_at=new_user.created_at.isoformat(),
    )

    return build_success_response(response_data.model_dump())


# =============================================================================
# POST /api/v1/auth/login
# =============================================================================
@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Connexion réussie"},
        401: {"description": "Identifiants invalides"},
        403: {"description": "Compte désactivé ou supprimé"},
    },
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Connexion d'un utilisateur existant."""
    # Récupère l'utilisateur par email
    user = db.query(User).filter(User.email == request.email).first()

    # Vérifie les credentials
    if not user or not verify_password(request.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_error_response(
                code="INVALID_CREDENTIALS",
                message="Email ou mot de passe incorrect."
            ).model_dump()
        )

    # Vérifie si le compte est actif
    if not user.is_active or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_error_response(
                code="ACCOUNT_DISABLED",
                message="Ce compte a été désactivé ou supprimé."
            ).model_dump()
        )

    # Génère les tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_uuid, refresh_token_str = create_refresh_token()

    # Stocke le refresh token dans la DB
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_refresh_token = RefreshToken(
        id=refresh_token_uuid,
        user_id=user.id,
        token_hash=hash_password(refresh_token_str),
        expires_at=expires_at,
    )
    db.add(db_refresh_token)
    db.commit()

    # Prépare la réponse
    response_data = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
    )

    return build_success_response(response_data.model_dump())


# =============================================================================
# POST /api/v1/auth/refresh
# =============================================================================
@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Token rafraîchi avec succès"},
        401: {"description": "Refresh token invalide ou expiré"},
    },
)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Rafraîchit un access token à l'aide d'un refresh token valide."""
    # Récupère le refresh token depuis la DB
    try:
        token_uuid = UUID(request.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_error_response(
                code="REFRESH_TOKEN_INVALID",
                message="Le refresh token est invalide, expiré ou déjà révoqué."
            ).model_dump()
        )

    db_token = db.query(RefreshToken).filter(
        RefreshToken.id == token_uuid,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > datetime.now(timezone.utc)
    ).first()

    if not db_token or not verify_password(request.refresh_token, db_token.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_error_response(
                code="REFRESH_TOKEN_INVALID",
                message="Le refresh token est invalide, expiré ou déjà révoqué."
            ).model_dump()
        )

    # Génère un nouveau access token
    new_access_token = create_access_token(data={"sub": str(db_token.user_id)})

    response_data = RefreshTokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return build_success_response(response_data.model_dump())


# =============================================================================
# POST /api/v1/auth/logout
# =============================================================================
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Déconnexion réussie"},
        401: {"description": "Non autorisé"},
    },
)
def logout(
    request: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Révoque un refresh token (déconnexion)."""
    try:
        token_uuid = UUID(request.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_error_response(
                code="UNAUTHORIZED",
                message="Token d'accès manquant ou invalide."
            ).model_dump()
        )

    # Récupère et révoque le token
    db_token = db.query(RefreshToken).filter(
        RefreshToken.id == token_uuid,
        RefreshToken.user_id == current_user.id
    ).first()

    if db_token:
        db_token.revoked = True
        db.commit()

    return build_success_response({"message": "Déconnexion réussie."})
