"""
Router de gestion des utilisateurs : profil, mise à jour, suppression.
Référence : 02_contrats_api_auth_users.md
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password
from app.db.database import get_db
from app.db.models import User
from app.schemas.common import build_error_response, build_success_response
from app.schemas.users import UserDeleteRequest, UserResponse, UserUpdateRequest

router = APIRouter(prefix="/api/v1/users", tags=["Utilisateurs"])


# =============================================================================
# GET /api/v1/users/me
# =============================================================================
@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Profil récupéré avec succès"},
        401: {"description": "Non autorisé"},
    },
)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """Récupère le profil de l'utilisateur actuellement connecté."""
    response_data = UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        preferred_language=current_user.preferred_language,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
    )
    return build_success_response(response_data.model_dump())


# =============================================================================
# PATCH /api/v1/users/me
# =============================================================================
@router.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Profil mis à jour avec succès"},
        400: {"description": "Aucun champ modifiable fourni"},
        401: {"description": "Non autorisé"},
    },
)
def update_my_profile(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Met à jour le profil de l'utilisateur connecté."""
    # Vérifie qu'au moins un champ est fourni
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_response(
                code="INVALID_PAYLOAD",
                message="Aucun champ modifiable fourni."
            ).model_dump()
        )

    # Applique les modifications
    if "full_name" in update_data:
        current_user.full_name = update_data["full_name"]
    if "password" in update_data:
        current_user.hashed_password = hash_password(update_data["password"])
    if "preferred_language" in update_data:
        current_user.preferred_language = update_data["preferred_language"]

    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)

    # Prépare la réponse
    response_data = UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        preferred_language=current_user.preferred_language,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
    )
    return build_success_response(response_data.model_dump())


# =============================================================================
# DELETE /api/v1/users/me
# =============================================================================
@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Compte supprimé avec succès"},
        400: {"description": "Confirmation incorrecte"},
        401: {"description": "Mot de passe incorrect ou non autorisé"},
        404: {"description": "Utilisateur introuvable"},
    },
)
def delete_my_account(
    request: UserDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime ou anonymise le compte de l'utilisateur connecté."""
    # Vérifie la confirmation
    if request.confirmation != "SUPPRIMER MON COMPTE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_response(
                code="CONFIRMATION_REQUIRED",
                message="Le texte de confirmation ne correspond pas à celui attendu."
            ).model_dump()
        )

    # Vérifie le mot de passe
    if not verify_password(request.password, current_user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_error_response(
                code="INVALID_PASSWORD",
                message="Le mot de passe fourni est incorrect."
            ).model_dump()
        )

    now = datetime.now(timezone.utc)

    if request.deletion_strategy == "hard_delete":
        # Suppression physique totale (ON DELETE CASCADE s'occupe des conversations, tokens, etc.)
        db.delete(current_user)
        db.commit()
        message = "Votre compte et toutes vos données associées ont été supprimés définitivement."
    else:  # anonymize
        # Anonymisation complète
        current_user.email = f"deleted_{current_user.id}@anonymous.local"
        current_user.hashed_password = None
        current_user.full_name = "Utilisateur supprimé"
        current_user.is_deleted = True
        current_user.deleted_at = now
        current_user.updated_at = now
        # Révoque tous les refresh tokens
        for token in current_user.refresh_tokens:
            token.revoked = True
        db.commit()
        message = "Votre compte a été anonymisé. Votre historique est conservé de façon dissociée."

    return build_success_response({
        "message": message,
        "deletion_strategy": request.deletion_strategy,
        "deleted_at": now.isoformat(),
    })
