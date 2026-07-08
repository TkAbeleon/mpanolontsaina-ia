"""
Schémas génériques pour les réponses API standardisées.
Toutes les réponses API suivent le même format :
  - Succès : {"status": "success", "data": {...}}
  - Erreur : {"status": "error", "error": {"code": "...", "message": "..."}}
"""
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# =============================================================================
# Schémas de base
# =============================================================================
class SuccessResponse(BaseModel, Generic[T]):
    """Réponse API standardisée pour les cas de succès."""
    status: str = Field(default="success", description="Toujours 'success' pour les réponses positives")
    data: T = Field(..., description="Données de la réponse")


class ErrorDetail(BaseModel):
    """Détails de l'erreur dans une réponse API d'échec."""
    code: str = Field(..., description="Code d'erreur machine-readable (ex: 'EMAIL_ALREADY_EXISTS')")
    message: str = Field(..., description="Message d'erreur en langage naturel")
    fields: Optional[dict[str, Any]] = Field(default=None, description="Erreurs de validation par champ (si applicable)")


class ErrorResponse(BaseModel):
    """Réponse API standardisée pour les cas d'erreur."""
    status: str = Field(default="error", description="Toujours 'error' pour les réponses négatives")
    error: ErrorDetail = Field(..., description="Détails de l'erreur")


# =============================================================================
# Utilitaires pour construire les réponses
# =============================================================================
def build_success_response(data: Any) -> SuccessResponse[Any]:
    """Construit une réponse de succès standardisée."""
    return SuccessResponse(status="success", data=data)


def build_error_response(
    code: str,
    message: str,
    fields: Optional[dict[str, Any]] = None
) -> ErrorResponse:
    """Construit une réponse d'erreur standardisée."""
    return ErrorResponse(
        status="error",
        error=ErrorDetail(code=code, message=message, fields=fields)
    )
