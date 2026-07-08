"""
Pydantic schemas pour la validation des requêtes et réponses API.
Organisation :
  - common.py : schémas génériques (réponses standardisées, erreurs)
  - auth.py : schémas pour l'authentification (register, login, refresh)
  - users.py : schémas pour la gestion des profils utilisateurs
  - chat.py : schémas pour le chat multi-agents
"""
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
)
from app.schemas.users import UserResponse, UserUpdateRequest, UserDeleteRequest
from app.schemas.chat import (
    VisitorChatRequest,
    VisitorChatResponse,
    CreateConversationRequest,
    CreateConversationResponse,
    SendMessageRequest,
    SendMessageResponse,
    ConversationResponse,
    ConversationsListResponse,
    MessageResponse,
)

__all__ = [
    # Common
    "ErrorResponse",
    "SuccessResponse",
    # Auth
    "RegisterRequest",
    "RegisterResponse",
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "LogoutRequest",
    # Users
    "UserResponse",
    "UserUpdateRequest",
    "UserDeleteRequest",
    # Chat
    "VisitorChatRequest",
    "VisitorChatResponse",
    "CreateConversationRequest",
    "CreateConversationResponse",
    "SendMessageRequest",
    "SendMessageResponse",
    "ConversationResponse",
    "ConversationsListResponse",
    "MessageResponse",
]
