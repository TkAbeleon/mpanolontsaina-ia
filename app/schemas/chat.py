"""
Schémas Pydantic pour le chat multi-agents (03_contrats_api_chat.md).
"""
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Requêtes
# =============================================================================
class VisitorChatRequest(BaseModel):
    """Corps de requête pour le chat visiteur POST /api/v1/chat/visitor."""
    session_id: Optional[UUID] = Field(default=None, description="Identifiant de session (UUID, généré côté client)")
    message: str = Field(..., min_length=1, description="Message de l'utilisateur", examples=["Inona ny fe-potoana fampandrenesana raha mametra-pialana ny mpiasa?"])
    language: Optional[str] = Field(default=None, pattern="^(mg|fr|en)$", description="Langue de la réponse (si omis, détectée automatiquement)")
    history: Optional[List[dict]] = Field(default=None, description="Historique de la conversation (liste de messages {role, content})")


class CreateConversationRequest(BaseModel):
    """Corps de requête pour créer une conversation POST /api/v1/chat/conversations."""
    title: Optional[str] = Field(default=None, description="Titre de la conversation (généré automatiquement si omis)")


class SendMessageRequest(BaseModel):
    """Corps de requête pour envoyer un message dans une conversation POST /api/v1/chat/conversations/{id}/messages."""
    message: str = Field(..., min_length=1, description="Message de l'utilisateur")


# =============================================================================
# Réponses
# =============================================================================
class SourceReference(BaseModel):
    """Référence à une source juridique utilisée pour générer la réponse."""
    code: Optional[str] = Field(default=None, description="Code ou texte de loi (ex: 'Code du travail malgache')")
    article: Optional[str] = Field(default=None, description="Numéro d'article")
    excerpt_summary: Optional[str] = Field(default=None, description="Résumé de l'extrait utilisé")


class VisitorChatResponse(BaseModel):
    """Réponse au chat visiteur."""
    session_id: UUID = Field(..., description="Identifiant de session")
    language: str = Field(..., description="Langue de la réponse (mg, fr, en)")
    answer: str = Field(..., description="Réponse de l'assistant juridique")
    agent_source: Optional[str] = Field(default=None, description="Agent spécialisé qui a généré la réponse")
    sources: Optional[List[SourceReference]] = Field(default=None, description="Sources juridiques utilisées")
    persisted: bool = Field(default=False, description="Toujours false pour le chat visiteur")


class CreateConversationResponse(BaseModel):
    """Réponse à la création de conversation."""
    id: UUID = Field(..., description="Identifiant de la conversation")
    title: Optional[str] = Field(default=None, description="Titre de la conversation")
    created_at: str = Field(..., description="Date de création (ISO 8601)")


class MessageResponse(BaseModel):
    """Réponse avec les informations d'un message."""
    id: UUID = Field(..., description="Identifiant du message")
    role: str = Field(..., description="Rôle du message ('user' ou 'assistant')")
    content: str = Field(..., description="Contenu du message")
    agent_source: Optional[str] = Field(default=None, description="Agent spécialisé (pour les messages assistant)")
    sources: Optional[List[SourceReference]] = Field(default=None, description="Sources utilisées (pour les messages assistant)")
    language: str = Field(..., description="Langue du message")
    created_at: str = Field(..., description="Date de création (ISO 8601)")


class SendMessageResponse(BaseModel):
    """Réponse à l'envoi d'un message dans une conversation."""
    user_message: MessageResponse = Field(..., description="Message de l'utilisateur persisté")
    assistant_message: MessageResponse = Field(..., description="Réponse de l'assistant")
    conversation_id: UUID = Field(..., description="Identifiant de la conversation")


class ConversationResponse(BaseModel):
    """Réponse avec les détails d'une conversation et ses messages."""
    id: UUID = Field(..., description="Identifiant de la conversation")
    title: Optional[str] = Field(default=None, description="Titre de la conversation")
    language: Optional[str] = Field(default=None, description="Langue dominante de la conversation")
    created_at: str = Field(..., description="Date de création (ISO 8601)")
    updated_at: str = Field(..., description="Dernière mise à jour (ISO 8601)")
    messages: List[MessageResponse] = Field(..., description="Liste des messages de la conversation")


class ConversationsListResponse(BaseModel):
    """Réponse avec la liste paginée des conversations."""
    items: List[dict] = Field(..., description="Liste des conversations (sans les messages)")
    page: int = Field(default=1, description="Numéro de page")
    limit: int = Field(default=20, description="Nombre d'éléments par page")
    total: int = Field(..., description="Nombre total de conversations")
