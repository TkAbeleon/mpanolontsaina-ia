# Intégration N8N — Chat Backend Switch

## 📋 Vue d'ensemble

Le projet supporte désormais un **switch configurable** pour le backend de chat visiteur :
- **N8N** (défaut) : Interroge un webhook n8n externe pour la réponse
- **Local** : Utilise le pipeline LangGraph local (agents + RAG)

L'historique de conversation est **géré indépendamment par n8n** — aucune persistance côté backend.

---

## ⚙️ Configuration

### Variables d'environnement (`.env`)

```env
# Backend de chat : "n8n" (défaut) ou "local"
CHAT_BACKEND=n8n

# URL du webhook n8n (obligatoire si CHAT_BACKEND=n8n)
N8N_WEBHOOK_URL=https://rtsikynyantsa-jerymotro-pipeline.hf.space/webhook/bb146751-e667-451f-9cc2-89549549657e

# Timeout en secondes pour les appels n8n
N8N_REQUEST_TIMEOUT=30

# Retry automatique en cas d'erreur réseau
N8N_AUTO_RETRY=True
```

### Changer le backend au runtime

```bash
# Mode N8N
export CHAT_BACKEND=n8n
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080

# Mode Local (LangGraph)
export CHAT_BACKEND=local
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## 🔌 Architecture N8N

### Webhook requis

Le webhook n8n doit accepter une requête POST avec la structure :

```json
{
  "message": "Question juridique",
  "language": "fr",
  "session_id": "uuid-v4",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

### Réponse attendue

Le webhook doit retourner :

```json
{
  "output_message": "Réponse de l'IA",
  "agent_source": "nom_de_l_agent",
  "sources": [
    {
      "code": "Code du travail",
      "article": "130",
      "excerpt_summary": "..."
    }
  ]
}
```

### Gestion de l'historique

- **N8N garde l'historique** dans sa propre logique de workflow
- Le backend FastAPI ne fait **que transmettre** la requête et la réponse
- **Aucune persistance en PostgreSQL** pour le chat visiteur

---

## 📁 Fichiers modifiés/créés

### Nouveaux fichiers

| Fichier | Description |
|---------|-------------|
| `app/providers/n8n_client.py` | Client HTTP pour appeler n8n (avec retry/timeout) |
| `N8N_INTEGRATION.md` | Documentation d'intégration (ce fichier) |

### Fichiers modifiés

| Fichier | Changements |
|---------|------------|
| `.env` | Ajout variables `CHAT_BACKEND`, `N8N_WEBHOOK_URL`, etc. |
| `app/core/config.py` | Ajout variables Pydantic pour N8N |
| `app/routers/chat.py` | Ajout switch n8n/local dans `/api/v1/chat/visitor` |

---

## 🧪 Tests

### Test N8N (Visitor Chat)

```bash
# Démarrer le serveur (défaut : CHAT_BACKEND=n8n)
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

```bash
curl -X POST "http://localhost:8080/api/v1/chat/visitor" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Bonjour, quelle est la durée minimale de congés payés à Madagascar?",
    "language": "fr"
  }'
```

**Réponse attendue** :
```json
{
  "status": "success",
  "data": {
    "session_id": "...",
    "language": "fr",
    "answer": "À Madagascar, le droit au congé payé est acquis après...",
    "agent_source": null,
    "sources": null,
    "persisted": false
  }
}
```

### Test Local (Backend LangGraph)

```bash
# Redémarrer avec le backend local
CHAT_BACKEND=local uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Même endpoint, même structure de requête/réponse — seul le backend change.

---

## 🔄 Flux de requête

### Mode N8N

```
Client → FastAPI /api/v1/chat/visitor
       → Validation VisitorChatRequest
       → N8nClient.send_chat_request()
       → HTTP POST au webhook n8n
       → n8n traite et retourne output_message
       → FastAPI construit VisitorChatResponse
       → Réponse au client (sans persistance DB)
```

### Mode Local

```
Client → FastAPI /api/v1/chat/visitor
       → Validation VisitorChatRequest
       → compiled_graph.ainvoke(AgentState)
       → LangGraph agents + RAG pipeline
       → FastAPI construit VisitorChatResponse
       → Réponse au client (sans persistance DB)
```

---

## ⚠️ Points importants

### Historique
- **N8N backend** : L'historique est géré **par n8n lui-même** (stockage interne, mémoire, ou autre)
- **Local backend** : L'historique est **transmis en paramètre** au pipeline LangGraph
- **Aucun stockage en PostgreSQL** pour le chat visiteur dans les deux cas

### Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `N8N_WEBHOOK_URL not configured` | N8N activé mais URL manquante | Définir `N8N_WEBHOOK_URL` dans `.env` |
| `n8n webhook failed after X attempts` | Webhook n8n indisponible | Vérifier l'URL et l'état du workflow n8n |
| Timeout 30s | Le webhook n8n est lent | Augmenter `N8N_REQUEST_TIMEOUT` |

---

## 🚀 Déploiement

### Production (N8N)

```bash
# .env
CHAT_BACKEND=n8n
N8N_WEBHOOK_URL=https://api.n8n.prod/webhook/...
N8N_REQUEST_TIMEOUT=30
N8N_AUTO_RETRY=True

# Lancer
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Production (Local)

```bash
# .env
CHAT_BACKEND=local
# N8N_WEBHOOK_URL non utilisée

# Lancer
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## 📊 Résumé des changements

| Aspect | Avant | Après |
|--------|-------|-------|
| Backend chat | Pipeline local seulement | N8N (défaut) + Local (option) |
| Historique visiteur | Transmis au pipeline | Géré par n8n ou paramètre |
| Configuration | Pas de switch | Env var `CHAT_BACKEND` |
| Dépendances | `fastapi`, `langgraph`, etc. | `aiohttp` ajouté pour n8n |

---

## 📞 Support

Pour des questions sur l'intégration n8n :
- Consulter [docs n8n](https://docs.n8n.io/)
- Vérifier les logs du workflow n8n
- Tester le webhook avec Postman ou curl
