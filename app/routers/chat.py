"""
Router de chat multi-agents : chat visiteur, conversations persistentes.
Référence : 03_contrats_api_chat.md
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.graph import compiled_graph
from app.agents.nodes import AgentState
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Conversation, Message, User
from app.rag.chroma_client import COLLECTIONS, add_documents_to_collection
from app.schemas.chat import (
    ConversationResponse,
    ConversationsListResponse,
    CreateConversationRequest,
    CreateConversationResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    SourceReference,
    VisitorChatRequest,
    VisitorChatResponse,
)
from app.schemas.common import build_error_response, build_success_response

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


# =============================================================================
# POST /api/v1/chat/visitor
# =============================================================================
@router.post(
    "/visitor",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Réponse générée avec succès"},
        400: {"description": "Message vide"},
        429: {"description": "Trop de requêtes"},
        500: {"description": "Erreur interne du pipeline d'agents"},
    },
)
async def visitor_chat(
    request: VisitorChatRequest
):
    """Chat éphémère pour les visiteurs (pas d'authentification requise)."""
    if not request.message or len(request.message.strip()) == 0:
        return build_error_response(
            code="EMPTY_MESSAGE",
            message="Le champ 'message' ne peut pas être vide."
        ), status.HTTP_400_BAD_REQUEST

    # Génère un session_id si non fourni
    session_id = request.session_id or uuid4()

    try:
        # Prépare l'état initial pour le graphe
        initial_state: AgentState = {
            "question": request.message,
            "history": request.history or [],
            "user_id": None,
            "language": request.language,
            "domain": None,
            "retrieved_context": None,
            "final_answer": None,
            "agent_source": None,
        }

        # Exécute le graphe
        final_state = await compiled_graph.ainvoke(initial_state)

        # Transforme le contexte en sources
        sources: List[SourceReference] = []
        if final_state.get("retrieved_context"):
            for ctx in final_state["retrieved_context"]:
                meta = ctx.get("metadata", {})
                sources.append(SourceReference(
                    code=meta.get("code"),
                    article=meta.get("article"),
                    excerpt_summary=meta.get("excerpt_summary"),
                ))

        # Prépare la réponse
        response_data = VisitorChatResponse(
            session_id=session_id,
            language=final_state["language"],
            answer=final_state["final_answer"] or "",
            agent_source=final_state.get("agent_source"),
            sources=sources,
            persisted=False,
        )

        return build_success_response(response_data.model_dump())

    except Exception as e:
        return build_error_response(
            code="AGENT_PIPELINE_FAILURE",
            message="Une erreur est survenue lors du traitement de votre question. Veuillez réessayer."
        ), status.HTTP_500_INTERNAL_SERVER_ERROR


# =============================================================================
# POST /api/v1/chat/conversations
# =============================================================================
@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Conversation créée avec succès"},
        401: {"description": "Non autorisé"},
    },
)
def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée une nouvelle conversation persistante pour un utilisateur connecté."""
    new_conversation = Conversation(
        user_id=current_user.id,
        title=request.title,
    )
    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    response_data = CreateConversationResponse(
        id=new_conversation.id,
        title=new_conversation.title,
        created_at=new_conversation.created_at.isoformat(),
    )
    return build_success_response(response_data.model_dump())


# =============================================================================
# GET /api/v1/chat/conversations
# =============================================================================
@router.get(
    "/conversations",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Conversations récupérées avec succès"},
        401: {"description": "Non autorisé"},
    },
)
def list_conversations(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste les conversations de l'utilisateur connecté (pagination)."""
    # Calcule l'offset
    offset = (page - 1) * limit

    # Récupère les conversations
    query = db.query(Conversation).filter(
        Conversation.user_id == current_user.id,
        Conversation.is_archived == False
    ).order_by(Conversation.updated_at.desc())

    total = query.count()
    conversations = query.offset(offset).limit(limit).all()

    items = []
    for conv in conversations:
        items.append({
            "id": str(conv.id),
            "title": conv.title,
            "updated_at": conv.updated_at.isoformat(),
        })

    response_data = ConversationsListResponse(
        items=items,
        page=page,
        limit=limit,
        total=total,
    )
    return build_success_response(response_data.model_dump())


# =============================================================================
# GET /api/v1/chat/conversations/{conversation_id}
# =============================================================================
@router.get(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Conversation récupérée avec succès"},
        401: {"description": "Non autorisé"},
        404: {"description": "Conversation introuvable"},
    },
)
def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère une conversation et ses messages."""
    # Vérifie que la conversation existe et appartient à l'utilisateur
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        return build_error_response(
            code="CONVERSATION_NOT_FOUND",
            message="Conversation introuvable ou accès non autorisé."
        ), status.HTTP_404_NOT_FOUND

    # Récupère les messages
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    # Transforme les messages en réponse
    message_responses = []
    for msg in messages:
        sources = []
        if msg.sources:
            for src in msg.sources:
                sources.append(SourceReference(
                    code=src.get("code"),
                    article=src.get("article"),
                    excerpt_summary=src.get("excerpt_summary"),
                ))
        message_responses.append(MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            agent_source=msg.agent_source,
            sources=sources,
            language=msg.language,
            created_at=msg.created_at.isoformat(),
        ))

    response_data = ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        language=conversation.language,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
        messages=message_responses,
    )

    return build_success_response(response_data.model_dump())


# =============================================================================
# POST /api/v1/chat/conversations/{conversation_id}/messages
# =============================================================================
@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Message envoyé et réponse générée"},
        401: {"description": "Non autorisé"},
        404: {"description": "Conversation introuvable"},
        422: {"description": "Erreur de validation"},
    },
)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Envoie un message dans une conversation et reçoit une réponse de l'assistant."""
    if not request.message or len(request.message.strip()) == 0:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="Le champ 'message' est requis."
        ), status.HTTP_422_UNPROCESSABLE_ENTITY

    # Vérifie la conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        return build_error_response(
            code="CONVERSATION_NOT_FOUND",
            message="Conversation introuvable ou accès non autorisé."
        ), status.HTTP_404_NOT_FOUND

    # Récupère l'historique des messages
    history = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    history_list = []
    for msg in history:
        history_list.append({
            "role": msg.role,
            "content": msg.content,
        })

    try:
        # Prépare l'état du graphe
        initial_state: AgentState = {
            "question": request.message,
            "history": history_list,
            "user_id": str(current_user.id),
            "language": current_user.preferred_language,
            "domain": None,
            "retrieved_context": None,
            "final_answer": None,
            "agent_source": None,
        }

        # Exécute le graphe
        final_state = await compiled_graph.ainvoke(initial_state)

        # Transforme le contexte en sources
        sources_data = []
        source_refs = []
        if final_state.get("retrieved_context"):
            for ctx in final_state["retrieved_context"]:
                meta = ctx.get("metadata", {})
                sources_data.append({
                    "code": meta.get("code"),
                    "article": meta.get("article"),
                    "excerpt_summary": meta.get("excerpt_summary"),
                })
                source_refs.append(SourceReference(
                    code=meta.get("code"),
                    article=meta.get("article"),
                    excerpt_summary=meta.get("excerpt_summary"),
                ))

        now = datetime.now(timezone.utc)
        lang = final_state["language"]

        # Sauvegarde le message utilisateur
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            language=lang,
            created_at=now,
        )
        db.add(user_msg)

        # Sauvegarde le message assistant
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_state["final_answer"] or "",
            agent_source=final_state.get("agent_source"),
            sources=sources_data,
            language=lang,
            created_at=now,
        )
        db.add(assistant_msg)

        # Met à jour la conversation
        conversation.updated_at = now
        if not conversation.language:
            conversation.language = lang
        # Génère un titre si absent (premier message)
        if not conversation.title:
            conversation.title = request.message[:100] + ("..." if len(request.message) > 100 else "")

        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        db.refresh(conversation)

        # Prépare la réponse
        response_data = SendMessageResponse(
            user_message=MessageResponse(
                id=user_msg.id,
                role=user_msg.role,
                content=user_msg.content,
                language=user_msg.language,
                created_at=user_msg.created_at.isoformat(),
            ),
            assistant_message=MessageResponse(
                id=assistant_msg.id,
                role=assistant_msg.role,
                content=assistant_msg.content,
                agent_source=assistant_msg.agent_source,
                sources=source_refs,
                language=assistant_msg.language,
                created_at=assistant_msg.created_at.isoformat(),
            ),
            conversation_id=conversation_id,
        )

        return build_success_response(response_data.model_dump())

    except Exception as e:
        db.rollback()
        return build_error_response(
            code="AGENT_PIPELINE_FAILURE",
            message="Une erreur est survenue lors du traitement de votre question. Veuillez réessayer."
        ), status.HTTP_500_INTERNAL_SERVER_ERROR


# =============================================================================
# DELETE /api/v1/chat/conversations/{conversation_id}
# =============================================================================
@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Conversation supprimée avec succès"},
        401: {"description": "Non autorisé"},
        404: {"description": "Conversation introuvable"},
    },
)
def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime une conversation (et ses messages en cascade)."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conversation:
        return build_error_response(
            code="CONVERSATION_NOT_FOUND",
            message="Conversation introuvable ou accès non autorisé."
        ), status.HTTP_404_NOT_FOUND

    db.delete(conversation)
    db.commit()

    return build_success_response({"message": "Conversation supprimée avec succès."})


# =============================================================================
# Endpoint de test pour ajouter des documents à ChromaDB (pour développement)
# =============================================================================
@router.post(
    "/admin/seed-chroma",
    include_in_schema=False,
    status_code=status.HTTP_200_OK,
)
def seed_chroma(
    collection_name: str,
    documents: List[str],
    metadatas: Optional[List[dict]] = None,
    current_user: User = Depends(get_current_user),
):
    """Ajoute des documents à une collection ChromaDB (pour développement seulement)."""
    # Vérifie que la collection est valide
    if collection_name not in COLLECTIONS.values():
        return build_error_response(
            code="INVALID_COLLECTION",
            message=f"Collection invalide. Collections disponibles : {list(COLLECTIONS.values())}"
        ), status.HTTP_400_BAD_REQUEST

    add_documents_to_collection(
        collection_name=collection_name,
        documents=documents,
        metadatas=metadatas,
    )
    return build_success_response({"message": f"Documents ajoutés à la collection {collection_name}."})
