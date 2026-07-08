"""
Schémas Pydantic pour l'authentification (02_contrats_api_auth_users.md).
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# Requêtes
# =============================================================================
class RegisterRequest(BaseModel):
    """Corps de requête pour l'inscription POST /api/v1/auth/register."""
    email: EmailStr = Field(..., description="Email de l'utilisateur", examples=["hery.rakoto@example.mg"])
    password: str = Field(..., min_length=8, description="Mot de passe (minimum 8 caractères)", examples=["MotDePasse!2024"])
    full_name: Optional[str] = Field(default=None, description="Nom complet de l'utilisateur", examples=["Hery Rakoto"])
    preferred_language: str = Field(default="fr", pattern="^(mg|fr|en)$", description="Langue préférée (mg, fr, en)", examples=["mg"])


class LoginRequest(BaseModel):
    """Corps de requête pour la connexion POST /api/v1/auth/login."""
    email: EmailStr = Field(..., description="Email de l'utilisateur", examples=["hery.rakoto@example.mg"])
    password: str = Field(..., description="Mot de passe", examples=["MotDePasse!2024"])


class RefreshTokenRequest(BaseModel):
    """Corps de requête pour rafraîchir le token POST /api/v1/auth/refresh."""
    refresh_token: str = Field(..., description="Refresh token valide")


class LogoutRequest(BaseModel):
    """Corps de requête pour la déconnexion POST /api/v1/auth/logout."""
    refresh_token: str = Field(..., description="Refresh token à révoquer")


# =============================================================================
# Réponses
# =============================================================================
class RegisterResponse(BaseModel):
    """Réponse à l'inscription réussie."""
    id: UUID = Field(..., description="Identifiant unique de l'utilisateur")
    email: str = Field(..., description="Email de l'utilisateur")
    full_name: Optional[str] = Field(default=None, description="Nom complet")
    preferred_language: str = Field(..., description="Langue préférée")
    is_active: bool = Field(default=True, description="Compte actif")
    created_at: str = Field(..., description="Date de création (ISO 8601)")


class LoginResponse(BaseModel):
    """Réponse à la connexion réussie."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Refresh token (UUID)")
    token_type: str = Field(default="bearer", description="Type de token (toujours 'bearer')")
    expires_in: int = Field(default=3600, description="Durée de validité de l'access token en secondes")
    user: dict = Field(..., description="Informations de l'utilisateur connecté")


class RefreshTokenResponse(BaseModel):
    """Réponse au rafraîchissement de token réussi."""
    access_token: str = Field(..., description="Nouveau JWT access token")
    token_type: str = Field(default="bearer", description="Type de token (toujours 'bearer')")
    expires_in: int = Field(default=3600, description="Durée de validité en secondes")
