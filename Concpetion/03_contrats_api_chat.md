### Fichier : 03_contrats_api_chat.md

# Contrats d'API — Chat Multi-Agents (Visiteurs & Utilisateurs connectés)

Base URL : `/api/v1`

---

## 1. Chat éphémère — Visiteurs — `POST /api/v1/chat/visitor`

Aucune authentification requise. Aucune écriture en PostgreSQL. L'historique de conversation est géré côté client (renvoyé à chaque appel) ou en cache mémoire/Redis à courte durée de vie via `session_id`.

### Request Body

```json
{
  "session_id": "b6f1e2a0-1234-4a5b-9c6d-abcdef123456",
  "message": "Inona ny fe-potoana fampandrenesana raha mametra-pialana ny mpiasa ?",
  "language": "mg",
  "history": [
    { "role": "user", "content": "Manao ahoana" },
    { "role": "assistant", "content": "Manao ahoana, ahoana no azoko manampy anao momba ny lalàna malagasy ?" }
  ]
}
```

> `session_id` : généré côté client au premier échange (UUID v4) et réutilisé pour la durée de la session. `history` : facultatif, permet au client de renvoyer le contexte court sans dépendre d'un stockage serveur. `language` : facultatif, `"mg"` | `"fr"` | `"en"` — si omis, la langue est **détectée automatiquement** à partir du texte de `message` par le nœud `language_detection` du graphe LangGraph (voir §7).

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "session_id": "b6f1e2a0-1234-4a5b-9c6d-abcdef123456",
    "language": "mg",
    "answer": "Any Madagasikara, ny fe-potoana fampandrenesana dia miovaova arakaraka ny sokajin'asa sy ny fahanterana ao amin'ny asa, araka ny Kaody momba ny asa (Lalàna laharana faha-2003-044)...",
    "agent_source": "droit_travail_agent",
    "sources": [
      {
        "code": "Code du travail malgache",
        "article": "Article 66",
        "excerpt_summary": "Délais de préavis selon la catégorie professionnelle."
      }
    ],
    "persisted": false
  }
}
```

> Le champ `language` renvoyé confirme la langue effectivement utilisée pour générer `answer` (utile côté client pour l'affichage/la synthèse vocale). Les métadonnées de `sources` (code, article) restent dans leur langue d'origine (le corpus légal reste non traduit), seul le champ `excerpt_summary` peut être reformulé dans la langue cible si nécessaire.

### Réponse erreur — `400 Bad Request` (message vide)

```json
{
  "status": "error",
  "error": {
    "code": "EMPTY_MESSAGE",
    "message": "Le champ 'message' ne peut pas être vide."
  }
}
```

### Réponse erreur — `429 Too Many Requests` (rate-limit visiteur)

```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Trop de requêtes pour une session visiteur. Veuillez patienter ou vous connecter."
  }
}
```

### Réponse erreur — `500 Internal Server Error` (échec du graphe d'agents)

```json
{
  "status": "error",
  "error": {
    "code": "AGENT_PIPELINE_FAILURE",
    "message": "Une erreur est survenue lors du traitement de votre question. Veuillez réessayer."
  }
}
```

---

## 2. Création d'une conversation persistante — `POST /api/v1/chat/conversations`

**Auth requise.** Crée une conversation vide, rattachée à l'utilisateur.

### Request Body

```json
{
  "title": "Question sur mon licenciement"
}
```

> `title` est facultatif ; s'il est omis, il sera généré automatiquement à partir du premier message envoyé.

### Réponse succès — `201 Created`

```json
{
  "status": "success",
  "data": {
    "id": "9a8b7c6d-5e4f-3a2b-1c0d-9876543210ef",
    "title": "Question sur mon licenciement",
    "created_at": "2026-07-07T09:00:00Z"
  }
}
```

### Réponse erreur — `401 Unauthorized`

```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Vous devez être connecté pour créer une conversation persistante."
  }
}
```

---

## 3. Envoyer un message dans une conversation — `POST /api/v1/chat/conversations/{conversation_id}/messages`

**Auth requise.** Le message et la réponse sont persistés en base.

### Request Body

```json
{
  "message": "Mon employeur peut-il me licencier sans préavis pour faute grave ?"
}
```

### Réponse succès — `201 Created`

```json
{
  "status": "success",
  "data": {
    "user_message": {
      "id": "1111aaaa-2222-bbbb-3333-cccc44445555",
      "role": "user",
      "content": "Mon employeur peut-il me licencier sans préavis pour faute grave ?",
      "created_at": "2026-07-07T09:05:00Z"
    },
    "assistant_message": {
      "id": "6666dddd-7777-eeee-8888-ffff99990000",
      "role": "assistant",
      "content": "Oui, en cas de faute grave dûment caractérisée, l'employeur peut procéder à un licenciement sans préavis ni indemnité de préavis, sous réserve du respect de la procédure disciplinaire prévue par le Code du travail...",
      "agent_source": "droit_travail_agent",
      "sources": [
        {
          "code": "Code du travail malgache",
          "article": "Article 71",
          "excerpt_summary": "Licenciement pour faute grave, absence de préavis."
        }
      ],
      "created_at": "2026-07-07T09:05:03Z"
    },
    "conversation_id": "9a8b7c6d-5e4f-3a2b-1c0d-9876543210ef"
  }
}
```

### Réponse erreur — `404 Not Found` (conversation inexistante ou n'appartenant pas à l'utilisateur)

```json
{
  "status": "error",
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "Conversation introuvable ou accès non autorisé."
  }
}
```

### Réponse erreur — `422 Unprocessable Entity`

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Le champ 'message' est requis."
  }
}
```

---

## 4. Lister mes conversations — `GET /api/v1/chat/conversations`

**Auth requise.** Supporte pagination via `?page=1&limit=20`.

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "9a8b7c6d-5e4f-3a2b-1c0d-9876543210ef",
        "title": "Question sur mon licenciement",
        "updated_at": "2026-07-07T09:05:03Z"
      }
    ],
    "page": 1,
    "limit": 20,
    "total": 1
  }
}
```

### Réponse erreur — `401 Unauthorized`

```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Token d'accès manquant ou invalide."
  }
}
```

---

## 5. Récupérer une conversation avec ses messages — `GET /api/v1/chat/conversations/{conversation_id}`

**Auth requise.**

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "id": "9a8b7c6d-5e4f-3a2b-1c0d-9876543210ef",
    "title": "Question sur mon licenciement",
    "messages": [
      {
        "id": "1111aaaa-2222-bbbb-3333-cccc44445555",
        "role": "user",
        "content": "Mon employeur peut-il me licencier sans préavis pour faute grave ?",
        "created_at": "2026-07-07T09:05:00Z"
      },
      {
        "id": "6666dddd-7777-eeee-8888-ffff99990000",
        "role": "assistant",
        "content": "Oui, en cas de faute grave dûment caractérisée...",
        "agent_source": "droit_travail_agent",
        "created_at": "2026-07-07T09:05:03Z"
      }
    ]
  }
}
```

### Réponse erreur — `404 Not Found`

```json
{
  "status": "error",
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "Conversation introuvable ou accès non autorisé."
  }
}
```

---

## 6. Supprimer une conversation — `DELETE /api/v1/chat/conversations/{conversation_id}`

**Auth requise.**

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "message": "Conversation supprimée avec succès."
  }
}
```

### Réponse erreur — `404 Not Found`

```json
{
  "status": "error",
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "Conversation introuvable ou accès non autorisé."
  }
}
```

---

## 7. Déclenchement de LangGraph dans le contrôleur FastAPI

Le graphe est compilé **une seule fois** au démarrage de l'application (dans un module `agents/graph.py`), puis injecté comme singleton via les dépendances FastAPI (`Depends`). Les contrôleurs ne connaissent jamais les détails internes du graphe : ils manipulent uniquement un état d'entrée et récupèrent un état de sortie.

```python
# agents/graph.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    question: str
    history: List[dict]
    user_id: Optional[str]
    language: Optional[str]         # "mg" | "fr" | "en" — fourni par le client ou détecté
    domain: Optional[str]
    retrieved_context: Optional[list]
    final_answer: Optional[str]
    agent_source: Optional[str]

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("language_detection", language_detection_node)  # NOUVEAU : détecte mg/fr/en si non fourni
    workflow.add_node("supervisor", supervisor_node)          # Classification de l'intention
    workflow.add_node("droit_travail_agent", droit_travail_node)
    workflow.add_node("fiscalite_agent", fiscalite_node)
    workflow.add_node("retrieval", retrieval_node)             # Requête ChromaDB
    workflow.add_node("synthesis", synthesis_node)             # Fusion / réponse finale, rédigée dans `language`

    workflow.set_entry_point("language_detection")
    workflow.add_edge("language_detection", "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_by_domain,  # fonction de routage -> retourne le nom du nœud cible
        {
            "droit_travail": "droit_travail_agent",
            "fiscalite": "fiscalite_agent",
        },
    )
    workflow.add_edge("droit_travail_agent", "retrieval")
    workflow.add_edge("fiscalite_agent", "retrieval")
    workflow.add_edge("retrieval", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow.compile()

compiled_graph = build_graph()


def language_detection_node(state: AgentState) -> AgentState:
    """Si le client n'a pas fourni de langue, on la déduit via le LLM (voir guide Vertex AI §3)."""
    if state.get("language"):
        return state  # préférence explicite du client/utilisateur : prioritaire
    detected = detect_language_via_llm(state["question"])  # retourne "mg" | "fr" | "en"
    return {**state, "language": detected}
```

```python
# controllers/chat_controller.py
from fastapi import APIRouter, Depends
from agents.graph import compiled_graph, AgentState

router = APIRouter()

@router.post("/chat/visitor")
async def chat_visitor(payload: VisitorChatRequest):
    state: AgentState = {
        "question": payload.message,
        "history": payload.history or [],
        "user_id": None,
        "domain": None,
        "retrieved_context": None,
        "final_answer": None,
        "agent_source": None,
    }
    # Point d'invocation du graphe LangGraph :
    result_state = await compiled_graph.ainvoke(state)

    # Aucune persistance PostgreSQL ici (chat éphémère)
    return build_success_response(result_state)


@router.post("/chat/conversations/{conversation_id}/messages")
async def chat_persistent(
    conversation_id: str,
    payload: PersistentChatRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db_session),
):
    conversation = await get_owned_conversation(db, conversation_id, current_user.id)

    state: AgentState = {
        "question": payload.message,
        "history": await load_recent_messages(db, conversation_id),
        "user_id": str(current_user.id),
        "domain": None,
        "retrieved_context": None,
        "final_answer": None,
        "agent_source": None,
    }
    # Point d'invocation du graphe LangGraph :
    result_state = await compiled_graph.ainvoke(state)

    # Persistance : message utilisateur + réponse assistant
    user_msg = await save_message(db, conversation_id, role="user", content=payload.message)
    assistant_msg = await save_message(
        db,
        conversation_id,
        role="assistant",
        content=result_state["final_answer"],
        agent_source=result_state["agent_source"],
        sources=result_state.get("retrieved_context"),
    )

    return build_success_response({
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "conversation_id": conversation_id,
    })
```

### Points clés d'intégration

- Le **nœud `retrieval`** appelle ChromaDB via son client Python : `collection.query(query_texts=[question], n_results=5)`, en sélectionnant la collection correspondant au `domain` déterminé par le superviseur.
- L'invocation `ainvoke` (asynchrone) est préférée à `invoke` pour ne pas bloquer la boucle d'événements FastAPI. Pour les réponses en streaming (UX progressive côté client), `compiled_graph.astream(state)` peut être exposé via un endpoint `StreamingResponse` (Server-Sent Events).
- Le graphe est **stateless entre les requêtes** : toute la mémoire conversationnelle nécessaire (historique) est reconstruite à chaque appel, soit depuis PostgreSQL (utilisateur connecté), soit depuis le payload/cache (visiteur).

## 8. Résolution de la langue (priorité)

Pour chaque requête de chat, la langue effective de réponse est résolue selon l'ordre de priorité suivant :

1. **`language` explicite dans le payload de la requête** (sélecteur de langue dans l'UI, ou changement ponctuel demandé par l'utilisateur en cours de conversation) → toujours prioritaire.
2. **`preferred_language` du profil utilisateur** (utilisateurs connectés uniquement) → appliqué si aucune langue n'est fournie dans la requête.
3. **Détection automatique** par le nœud `language_detection` à partir du texte de la question → utilisée en dernier recours (visiteurs sans préférence, ou première requête d'un utilisateur connecté n'ayant pas encore défini de préférence).

Cette résolution est effectuée **côté contrôleur FastAPI**, avant construction de l'`AgentState`, afin que le graphe LangGraph reçoive toujours une valeur de `language` déjà déterminée (le nœud `language_detection` ne fait alors qu'un passthrough si la valeur est déjà renseignée). Voir le guide `04_guide_implementation_vertex_ai.md` pour le détail technique de la détection automatique via Gemini sur Vertex AI.
