"""
Schémas Pydantic pour la gestion des utilisateurs (02_contrats_api_auth_users.md).
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Requêtes
# =============================================================================
class UserUpdateRequest(BaseModel):
    """Corps de requête pour mettre à jour le profil PATCH /api/v1/users/me."""
    full_name: Optional[str] = Field(default=None, description="Nouveau nom complet", examples=["Hery A. Rakoto"])
    password: Optional[str] = Field(default=None, min_length=8, description="Nouveau mot de passe (minimum 8 caractères)")
    preferred_language: Optional[str] = Field(default=None, pattern="^(mg|fr|en)$", description="Nouvelle langue préférée")


class UserDeleteRequest(BaseModel):
    """Corps de requête pour supprimer le compte DELETE /api/v1/users/me."""
    password: str = Field(..., description="Mot de passe actuel pour confirmation")
    deletion_strategy: str = Field(..., pattern="^(hard_delete|anonymize)$", description="Stratégie de suppression")
    confirmation: str = Field(..., description="Doit être 'SUPPRIMER MON COMPTE' pour confirmer")


# =============================================================================
# Réponses
# =============================================================================
class UserResponse(BaseModel):
    """Réponse avec les informations du profil utilisateur."""
    id: UUID = Field(..., description="Identifiant unique de l'utilisateur")
    email: str = Field(..., description="Email de l'utilisateur")
    full_name: Optional[str] = Field(default=None, description="Nom complet")
    preferred_language: str = Field(..., description="Langue préférée (mg, fr, en)")
    is_active: bool = Field(..., description="Compte actif ou non")
    created_at: str = Field(..., description="Date de création (ISO 8601)")
    updated_at: str = Field(..., description="Dernière mise à jour (ISO 8601)")
