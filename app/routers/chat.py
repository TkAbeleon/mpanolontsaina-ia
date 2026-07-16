"""
Router de chat multi-agents : chat visiteur, conversations persistantes.
Référence : 03_contrats_api_chat.md
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.graph import compiled_graph
from app.agents.nodes import AgentState
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Conversation, Message, User
from app.providers.n8n_client import N8nClient
from app.rag.chroma_client import COLLECTIONS, add_documents_to_collection, get_collection_info
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


# =============================================================================
# Utilitaires internes
# =============================================================================
def _build_source_refs(retrieved_context: Optional[List[dict]]) -> tuple[List[SourceReference], List[dict]]:
    """Transforme le contexte RAG en SourceReference (pour la réponse) et en liste de dicts (pour la DB)."""
    source_refs: List[SourceReference] = []
    sources_data: List[dict] = []
    if not retrieved_context:
        return source_refs, sources_data
    for ctx in retrieved_context:
        meta = ctx.get("metadata") or {}
        ref = SourceReference(
            code=meta.get("code"),
            article=meta.get("article"),
            excerpt_summary=meta.get("excerpt_summary"),
        )
        source_refs.append(ref)
        sources_data.append({
            "code": meta.get("code"),
            "article": meta.get("article"),
            "excerpt_summary": meta.get("excerpt_summary"),
        })
    return source_refs, sources_data


# =============================================================================
# Utilitaire de routage du backend de chat
# =============================================================================
async def _run_chat_backend(
    *,
    message: str,
    history: Optional[list] = None,
    language: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> tuple[str, Optional[str], List[SourceReference], str]:
    """Exécute la requête de chat via n8n ou via le pipeline local."""
    if settings.CHAT_BACKEND == "n8n":
        if not settings.N8N_WEBHOOK_URL:
            raise ValueError(
                "N8N_WEBHOOK_URL non configurée. Défini CHAT_BACKEND=local ou renseignez N8N_WEBHOOK_URL."
            )

        n8n_client = N8nClient(
            webhook_url=settings.N8N_WEBHOOK_URL,
            timeout=settings.N8N_REQUEST_TIMEOUT,
            auto_retry=settings.N8N_AUTO_RETRY,
        )

        n8n_response = await n8n_client.send_chat_request(
            message=message,
            language=language,
            session_id=session_id,
            history=history,
        )

        answer_text = n8n_response.get("output_message", "")
        agent_source = n8n_response.get("agent_source")
        sources_data = n8n_response.get("sources", [])

        source_refs = [
            SourceReference(
                code=src.get("code"),
                article=src.get("article"),
                excerpt_summary=src.get("excerpt_summary"),
            )
            for src in sources_data
            if isinstance(src, dict)
        ]

        return answer_text, agent_source, source_refs, language or "fr"

    initial_state: AgentState = {
        "question": message,
        "history": history or [],
        "user_id": user_id,
        "language": language,
        "domain": None,
        "retrieved_context": None,
        "final_answer": None,
        "agent_source": None,
    }

    final_state = await compiled_graph.ainvoke(initial_state)
    source_refs, _ = _build_source_refs(final_state.get("retrieved_context"))

    return (
        final_state.get("final_answer") or "",
        final_state.get("agent_source"),
        source_refs,
        final_state.get("language", "fr"),
    )


# =============================================================================
# POST /api/v1/chat/visitor
# =============================================================================
@router.post(
    "/visitor",
    status_code=status.HTTP_200_OK,
    summary="Chat éphémère visiteur (sans auth)",
    responses={
        200: {"description": "Réponse générée avec succès"},
        400: {"description": "Message vide"},
        429: {"description": "Trop de requêtes"},
        500: {"description": "Erreur interne du pipeline d'agents ou n8n"},
    },
)
async def visitor_chat(request: VisitorChatRequest):
    """
    Chat éphémère pour les visiteurs (pas d'authentification requise).
    Aucune persistance en PostgreSQL.
    
    Routage :
    - Si CHAT_BACKEND=n8n : interroge le webhook n8n (défaut)
    - Si CHAT_BACKEND=local : utilise le pipeline LangGraph local
    """
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_response(
                code="EMPTY_MESSAGE",
                message="Le champ 'message' ne peut pas être vide."
            ).model_dump()
        )

    session_id = request.session_id or uuid4()
    logger.info(
        "[visitor_chat] session=%s backend=%s lang=%s msg=%.80s",
        session_id,
        settings.CHAT_BACKEND,
        request.language,
        request.message,
    )

    try:
        answer_text, agent_source, source_refs, lang = await _run_chat_backend(
            message=request.message.strip(),
            history=request.history,
            language=request.language,
            session_id=str(session_id),
            user_id=None,
        )

        response_data = VisitorChatResponse(
            session_id=session_id,
            language=lang,
            answer=answer_text,
            agent_source=agent_source,
            sources=source_refs or None,
            persisted=False,
        )

        logger.info(
            "[visitor_chat] backend=%s ✓ session=%s lang=%s answer_len=%d",
            settings.CHAT_BACKEND,
            session_id,
            lang,
            len(answer_text),
        )

        return build_success_response(response_data.model_dump()).model_dump()

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "[visitor_chat] ✗ ERREUR (%s) : %s",
            settings.CHAT_BACKEND,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=build_error_response(
                code="AGENT_PIPELINE_FAILURE",
                message="Une erreur est survenue lors du traitement de votre question. Veuillez réessayer."
            ).model_dump()
        )


# =============================================================================
# POST /api/v1/chat/conversations
# =============================================================================
@router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Créer une conversation persistante",
    responses={
        201: {"description": "Conversation créée avec succès"},
        401: {"description": "Non autorisé"},
    },
)
def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée une nouvelle conversation persistante pour un utilisateur connecté."""
    new_conversation = Conversation(
        user_id=current_user.id,
        title=request.title,
    )
    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    logger.info("[create_conversation] user=%s conv=%s", current_user.id, new_conversation.id)

    response_data = CreateConversationResponse(
        id=new_conversation.id,
        title=new_conversation.title,
        created_at=new_conversation.created_at.isoformat(),
    )
    return build_success_response(response_data.model_dump()).model_dump()


# =============================================================================
# GET /api/v1/chat/conversations
# =============================================================================
@router.get(
    "/conversations",
    status_code=status.HTTP_200_OK,
    summary="Lister mes conversations",
    responses={
        200: {"description": "Conversations récupérées avec succès"},
        401: {"description": "Non autorisé"},
    },
)
def list_conversations(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste les conversations de l'utilisateur connecté (paginées)."""
    offset = (page - 1) * limit

    query = db.query(Conversation).filter(
        Conversation.user_id == current_user.id,
        Conversation.is_archived == False,
    ).order_by(Conversation.updated_at.desc())

    total = query.count()
    conversations = query.offset(offset).limit(limit).all()

    items = [
        {
            "id": str(conv.id),
            "title": conv.title,
            "updated_at": conv.updated_at.isoformat(),
        }
        for conv in conversations
    ]

    response_data = ConversationsListResponse(
        items=items,
        page=page,
        limit=limit,
        total=total,
    )
    return build_success_response(response_data.model_dump()).model_dump()


# =============================================================================
# GET /api/v1/chat/conversations/{conversation_id}
# =============================================================================
@router.get(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Détail d'une conversation et ses messages",
    responses={
        200: {"description": "Conversation récupérée avec succès"},
        401: {"description": "Non autorisé"},
        404: {"description": "Conversation introuvable"},
    },
)
def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère une conversation et tous ses messages."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error_response(
                code="CONVERSATION_NOT_FOUND",
                message="Conversation introuvable ou accès non autorisé."
            ).model_dump()
        )

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    message_responses = []
    for msg in messages:
        source_refs = []
        if msg.sources:
            for src in msg.sources:
                source_refs.append(SourceReference(
                    code=src.get("code"),
                    article=src.get("article"),
                    excerpt_summary=src.get("excerpt_summary"),
                ))
        message_responses.append(MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            agent_source=msg.agent_source,
            sources=source_refs,
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

    return build_success_response(response_data.model_dump()).model_dump()


# =============================================================================
# POST /api/v1/chat/conversations/{conversation_id}/messages
# =============================================================================
@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Envoyer un message dans une conversation (persisté)",
    responses={
        201: {"description": "Message envoyé et réponse générée"},
        401: {"description": "Non autorisé"},
        404: {"description": "Conversation introuvable"},
        422: {"description": "Erreur de validation"},
        500: {"description": "Erreur du pipeline IA"},
    },
)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Envoie un message dans une conversation et reçoit la réponse de l'assistant IA."""
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=build_error_response(
                code="VALIDATION_ERROR",
                message="Le champ 'message' est requis et ne peut pas être vide."
            ).model_dump()
        )

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error_response(
                code="CONVERSATION_NOT_FOUND",
                message="Conversation introuvable ou accès non autorisé."
            ).model_dump()
        )

    # Charge l'historique de la conversation
    history_msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    history_list = [{"role": m.role, "content": m.content} for m in history_msgs]

    logger.info(
        "[send_message] user=%s conv=%s lang=%s msg=%.80s",
        current_user.id, conversation_id, current_user.preferred_language, request.message
    )

    try:
        answer_text, agent_source, source_refs, lang = await _run_chat_backend(
            message=request.message.strip(),
            history=history_list,
            language=current_user.preferred_language,
            session_id=str(conversation_id),
            user_id=str(current_user.id),
        )

        now = datetime.now(timezone.utc)

        # Persistance : message utilisateur
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=request.message.strip(),
            language=lang,
            created_at=now,
        )
        db.add(user_msg)

        # Persistance : réponse assistant
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer_text,
            agent_source=agent_source,
            sources=[
                {
                    "code": src.code,
                    "article": src.article,
                    "excerpt_summary": src.excerpt_summary,
                }
                for src in source_refs
            ] if source_refs else None,
            language=lang,
            created_at=now,
        )
        db.add(assistant_msg)

        # Met à jour la conversation
        conversation.updated_at = now
        if not conversation.language:
            conversation.language = lang
        if not conversation.title:
            # Titre auto-généré depuis le premier message
            conversation.title = request.message.strip()[:100] + (
                "..." if len(request.message) > 100 else ""
            )

        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)

        logger.info(
            "[send_message] conv=%s backend=%s → agent=%s lang=%s answer_len=%d",
            conversation_id,
            settings.CHAT_BACKEND,
            agent_source,
            lang,
            len(assistant_msg.content),
        )

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

        return build_success_response(response_data.model_dump()).model_dump()

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("[send_message] ERREUR pipeline agents : %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=build_error_response(
                code="AGENT_PIPELINE_FAILURE",
                message="Une erreur est survenue lors du traitement de votre question. Veuillez réessayer."
            ).model_dump()
        )


# =============================================================================
# DELETE /api/v1/chat/conversations/{conversation_id}
# =============================================================================
@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Supprimer une conversation",
    responses={
        200: {"description": "Conversation supprimée avec succès"},
        401: {"description": "Non autorisé"},
        404: {"description": "Conversation introuvable"},
    },
)
def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime une conversation et tous ses messages (cascade)."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_error_response(
                code="CONVERSATION_NOT_FOUND",
                message="Conversation introuvable ou accès non autorisé."
            ).model_dump()
        )

    db.delete(conversation)
    db.commit()
    logger.info("[delete_conversation] user=%s conv=%s supprimée.", current_user.id, conversation_id)
    return build_success_response({"message": "Conversation supprimée avec succès."}).model_dump()


# =============================================================================
# GET /api/v1/chat/rag/status — Debug : état des collections ChromaDB
# =============================================================================
@router.get(
    "/rag/status",
    status_code=status.HTTP_200_OK,
    summary="Statut des collections RAG ChromaDB (debug)",
    include_in_schema=True,
    tags=["Debug"],
)
def rag_status():
    """
    Retourne le statut et le nombre de documents dans chaque collection ChromaDB.
    Utile pour diagnostiquer les problèmes de retrieval RAG.
    """
    info = {name: get_collection_info(col) for name, col in COLLECTIONS.items()}
    return build_success_response(info).model_dump()


# =============================================================================
# POST /api/v1/chat/admin/seed-chroma — Ajout de documents ChromaDB
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
    """Ajoute des documents à une collection ChromaDB (développement seulement)."""
    if collection_name not in COLLECTIONS.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=build_error_response(
                code="INVALID_COLLECTION",
                message=f"Collection invalide. Collections disponibles : {list(COLLECTIONS.values())}"
            ).model_dump()
        )

    count = add_documents_to_collection(
        collection_name=collection_name,
        documents=documents,
        metadatas=metadatas,
    )
    return build_success_response({
        "message": f"Documents ajoutés à la collection '{collection_name}'.",
        "total_documents": count,
    }).model_dump()
