# Assistant Juridique Malgache — API Backend

API REST multi-agents fournissant des réponses juridiques en **malagasy**, **français** et **anglais**, alimentée par un graphe **LangGraph**, une base vectorielle **ChromaDB** et un fournisseur LLM interchangeable (Mistral AI en développement, Google Vertex AI / Gemini en production).

---

## Table des matières

1. [Stack technique](#stack-technique)
2. [Architecture](#architecture)
3. [Prérequis](#prérequis)
4. [Installation locale](#installation-locale)
5. [Configuration](#configuration)
6. [Lancement du serveur](#lancement-du-serveur)
7. [Exécution des tests](#exécution-des-tests)
8. [Basculement entre les fournisseurs LLM](#basculement-entre-les-fournisseurs-llm)
9. [Endpoints disponibles](#endpoints-disponibles)
10. [Structure du projet](#structure-du-projet)

---

## Stack technique

| Composant | Bibliothèque / Service | Rôle |
|---|---|---|
| **Framework Web** | [FastAPI](https://fastapi.tiangolo.com/) ≥ 0.115 | Routage HTTP, validation automatique, documentation OpenAPI |
| **Base de données** | PostgreSQL + [SQLAlchemy](https://docs.sqlalchemy.org/) 2.x + [Alembic](https://alembic.sqlalchemy.org/) | Persistance relationnelle (utilisateurs, conversations, messages) |
| **ORM** | SQLAlchemy 2.x (style `Mapped` / `mapped_column`) | Modèles déclaratifs, sessions, relations |
| **Orchestration IA** | [LangGraph](https://langchain-ai.github.io/langgraph/) | Graphe d'agents : Superviseur → Agents spécialisés → Synthèse |
| **Base vectorielle RAG** | [ChromaDB](https://www.trychroma.com/) | Corpus juridique malgache — retrieval sémantique multilingue |
| **Fournisseur LLM (dev)** | [mistralai](https://docs.mistral.ai/) | Génération de texte et embeddings (disponible immédiatement) |
| **Fournisseur LLM (prod)** | [google-genai](https://cloud.google.com/vertex-ai) / Vertex AI | Gemini — meilleur support du malagasy et embeddings multilingues |
| **Validation / Config** | [Pydantic](https://docs.pydantic.dev/) v2 + [Pydantic-Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Validation des données, chargement typé des variables d'environnement |
| **Authentification** | JWT (`python-jose`) + bcrypt (`passlib`) | Access token + refresh token, hash des mots de passe |
| **Serveur ASGI** | [Uvicorn](https://www.uvicorn.org/) | Serveur de production ASGI |
| **Tests** | [pytest](https://docs.pytest.org/) + `httpx` + `FastAPI TestClient` | Tests unitaires et de validation d'architecture |

---

## Architecture

```
Client (Web / Mobile)
        │ HTTPS/JSON
        ▼
    FastAPI (routers, middlewares JWT)
        │
        ├── Auth Service  ──────────────────► PostgreSQL
        │   (JWT, bcrypt, refresh tokens)
        │
        └── Chat Service ──► LangGraph (graphe compilé, singleton)
                                │
                                ├── language_detection_node  ──► LLMProvider.generate()
                                ├── supervisor_node           ──► LLMProvider.generate()
                                ├── retrieval_node            ──► ChromaDB.query()
                                ├── droit_travail_agent       ──► LLMProvider.generate()
                                ├── fiscalite_agent           ──► LLMProvider.generate()
                                └── synthesis_node            ──► LLMProvider.generate()
                                        │
                                        ▼
                              PostgreSQL (si utilisateur connecté)
```

### Pattern Factory — abstraction du fournisseur LLM

Le code métier (nœuds LangGraph, RAG) ne dépend **jamais** directement d'un SDK propriétaire. Il passe par l'interface `LLMProvider` :

```
LLMProvider (app/providers/base.py)
    .generate(system_prompt, user_prompt, temperature, max_tokens) -> str
    .embed(texts) -> List[List[float]]
        │
        ├── MistralProvider  (app/providers/mistral.py)   ← LLM_PROVIDER=mistral
        └── VertexAIProvider (app/providers/vertex.py)    ← LLM_PROVIDER=vertex
```

Le **factory singleton** (`app/providers/factory.py`) lit `LLM_PROVIDER` dans `.env` une seule fois au démarrage et instancie le bon adaptateur. Aucune ligne de code métier ne change lors du basculement de fournisseur.

---

## Prérequis

- **Python** 3.11 ou supérieur
- **PostgreSQL** 14 ou supérieur (instance locale, Docker, ou service managé)
- **pip** (ou **pipx** pour les outils globaux)
- Compte [Mistral AI](https://console.mistral.ai/) (développement) **ou** projet [Google Cloud](https://console.cloud.google.com/) avec Vertex AI activé (production)

---

## Installation locale

### 1. Cloner le dépôt

```bash
git clone https://github.com/votre-org/assistant-juridique-mg.git
cd assistant-juridique-mg
```

### 2. Créer et activer un environnement virtuel

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurer l'environnement

```bash
cp .env.example .env
# Éditez .env et renseignez au minimum :
#   DATABASE_URL, JWT_SECRET_KEY, LLM_PROVIDER, MISTRAL_API_KEY
```

### 5. Préparer la base de données

```bash
# Option A — Création automatique des tables (mode DEBUG=true dans .env)
# Mettez DEBUG=true dans .env, les tables sont créées au démarrage du serveur.
# Utile uniquement en développement ; ne convient pas à la production.

# Option B — Migrations Alembic (recommandé en équipe / CI)
# Initialisez Alembic si ce n'est pas déjà fait :
alembic init alembic
# Puis appliquez les migrations :
alembic upgrade head
```

> **Note** : le scaffolding Alembic (`alembic/env.py`, `alembic.ini`, répertoire `alembic/versions/`) n'est pas inclus dans ce dépôt de démarrage. Lancez `alembic init alembic` pour l'initialiser, puis configurez `env.py` pour importer `Base` depuis `app.db.database`.

---

## Configuration

Toutes les options sont documentées dans [`.env.example`](.env.example).

| Variable | Obligatoire | Description |
|---|---|---|
| `DATABASE_URL` | ✅ Toujours | URL de connexion PostgreSQL |
| `JWT_SECRET_KEY` | ✅ Toujours | Clé secrète de signature JWT |
| `LLM_PROVIDER` | ✅ Toujours | `mistral` (dev) ou `vertex` (prod) |
| `MISTRAL_API_KEY` | ✅ Si `mistral` | Clé API Mistral AI |
| `GCP_PROJECT_ID` | ✅ Si `vertex` | Identifiant projet Google Cloud |
| `GCP_LOCATION` | Si `vertex` | Région Vertex AI (défaut : `europe-west1`) |
| `GEMINI_MODEL` | Si `vertex` | Modèle de génération (défaut : `gemini-3-flash`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Si `vertex` hors GKE | Chemin vers le JSON du compte de service |
| `DEBUG` | Non | `true` = logs SQL + création auto des tables |

---

## Lancement du serveur

### Développement (rechargement automatique)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

L'API sera disponible sur :
- **Documentation Swagger** : http://localhost:8080/api/docs
- **Documentation ReDoc** : http://localhost:8080/api/redoc
- **Health check** : http://localhost:8080/health

---

## Exécution des tests

### Installation des dépendances de test

```bash
pip install pytest pytest-asyncio httpx
```

### Lancer tous les tests

```bash
pytest tests/ -v
```

### Lancer uniquement les tests de validation d'architecture

```bash
pytest tests/test_validation.py -v
```

### Avec couverture de code

```bash
pip install pytest-cov
pytest tests/ --cov=app --cov-report=term-missing
```

---

## Basculement entre les fournisseurs LLM

Le changement de fournisseur LLM se fait **exclusivement via `.env`**, sans modification du code.

### Passer en mode développement (Mistral AI)

```dotenv
LLM_PROVIDER=mistral
MISTRAL_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MISTRAL_CHAT_MODEL=mistral-large-latest
MISTRAL_EMBED_MODEL=mistral-embed
```

### Passer en mode production (Vertex AI / Gemini)

```dotenv
LLM_PROVIDER=vertex
GCP_PROJECT_ID=assistant-juridique-mg-prod
GCP_LOCATION=europe-west1
GEMINI_MODEL=gemini-3-flash
GEMINI_EMBEDDING_MODEL=text-multilingual-embedding-002
GOOGLE_APPLICATION_CREDENTIALS=/secrets/vertex-sa.json
```

> ⚠️ **Important** : les espaces vectoriels de `mistral-embed` et `text-multilingual-embedding-002` sont incompatibles. Si ChromaDB a été indexé avec Mistral, il faut **ré-indexer entièrement** les collections après bascule vers Vertex AI.

### Checklist de bascule

1. Mettre à jour les variables Vertex AI dans `.env`.
2. Changer `LLM_PROVIDER=mistral` → `LLM_PROVIDER=vertex`.
3. Ré-indexer les collections ChromaDB avec les nouveaux embeddings.
4. Rejouer le golden dataset trilingue (mg / fr / en) pour valider la qualité.
5. Redémarrer le serveur — **aucune modification de code requise**.

---

## Endpoints disponibles

### Actuellement implémentés

| Méthode | Chemin | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | Non | Health-check API + PostgreSQL |
| `GET` | `/api/docs` | Non | Documentation Swagger interactive |
| `GET` | `/api/redoc` | Non | Documentation ReDoc |
| `GET` | `/api/openapi.json` | Non | Schéma OpenAPI brut |

### Planifiés (routeurs non encore montés dans `app/main.py`)

> Les contrats complets sont définis dans `02_contrats_api_auth_users.md` et `03_contrats_api_chat.md`.
> Pour activer ces routes, décommentez le bloc `include_router` dans `app/main.py`.

| Méthode | Chemin | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Non | Inscription |
| `POST` | `/api/v1/auth/login` | Non | Connexion (retourne access + refresh token) |
| `POST` | `/api/v1/auth/refresh` | Non | Rafraîchissement de l'access token |
| `POST` | `/api/v1/auth/logout` | JWT | Révocation du refresh token |
| `GET` | `/api/v1/users/me` | JWT | Profil de l'utilisateur connecté |
| `PATCH` | `/api/v1/users/me` | JWT | Mise à jour du profil |
| `DELETE` | `/api/v1/users/me` | JWT | Suppression / anonymisation du compte |
| `POST` | `/api/v1/chat/visitor` | Non | Chat éphémère (visiteur) |
| `POST` | `/api/v1/chat/conversations` | JWT | Créer une conversation persistante |
| `GET` | `/api/v1/chat/conversations` | JWT | Lister mes conversations |
| `GET` | `/api/v1/chat/conversations/{id}` | JWT | Détail d'une conversation + messages |
| `POST` | `/api/v1/chat/conversations/{id}/messages` | JWT | Envoyer un message (persisté) |
| `DELETE` | `/api/v1/chat/conversations/{id}` | JWT | Supprimer une conversation |

---

## Structure du projet

```
assistant-juridique-mg/
├── app/
│   ├── __init__.py
│   ├── main.py                    # Point d'entrée FastAPI, lifespan, CORS, /health
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py              # Pydantic-Settings (variables d'environnement)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py            # Engine, SessionLocal, Base, get_db()
│   │   └── models.py              # Modèles SQLAlchemy : User, RefreshToken, Conversation, Message
│   └── providers/
│       ├── __init__.py
│       ├── base.py                # Interface abstraite LLMProvider
│       ├── mistral.py             # Implémentation Mistral AI
│       ├── vertex.py              # Implémentation Vertex AI / Gemini
│       └── factory.py             # Factory singleton get_llm_provider()
├── tests/
│   ├── __init__.py
│   └── test_validation.py         # Tests de validation d'architecture (pytest)
├── .env.example                   # Template de configuration (à copier en .env)
├── .gitignore
├── README.md
└── requirements.txt
```
