# État du Projet - Assistant Juridique Malgache

## État actuel au 2026-07-14

- Backend FastAPI structuré et fonctionnel dans sa version de base.
- Authentification, gestion des utilisateurs, chat visiteur et conversations persistantes implémentés.
- Moteur LangGraph, RAG ChromaDB et abstraction du fournisseur LLM présents dans le code.
- La partie IA et la partie API sont globalement avancées, et la validation avec les services externes a été réalisée avec succès.
- Vérification Vertex AI réalisée localement via le venv du projet (.venv).
- Résultat du test Vertex : après activation du compte de service et vérification des modèles disponibles, le modèle `publishers/google/models/gemini-2.5-flash` est accessible et une génération de test a réussi (réponse `OK`).
- Réindexation ChromaDB finalisée avec succès pour les trois domaines : droit du travail, foncier et famille.
- Collections RAG disponibles : `droit_travail_mg`, `foncier_mg` et `famille_mg`.

## ✅ Ce qui est fait

### 1. Infra & Configuration
- FastAPI framework avec documentation Swagger/ReDoc
- Configuration via `.env` (gestion des secrets, providers)
- Base de données PostgreSQL avec SQLAlchemy ORM
- Gitignore complet (ne commit pas de secrets)

### 2. Authentification & Utilisateurs
- Inscription / Connexion / Déconnexion
- Gestion des tokens (JWT access + refresh)
- Mise à jour / Suppression de profil utilisateur
- Hashage des mots de passe avec bcrypt (direct, sans passlib)
- **Tests passing :** `test-auth-users.sh` fonctionne parfaitement !

### 3. Providers LLM
- Factory pattern pour switcher entre Mistral et Vertex
- Implémentation Mistral via httpx (pas de dépendance SDK)
- Implémentation Vertex via google-genai

### 4. LangGraph Multi-Agents
- Nœuds implémentés :
  - Language Detection
  - Supervisor (classification domaine)
  - Retrieval (RAG avec ChromaDB)
  - Agents spécialisés (Droit du Travail, Foncier, Famille)
  - Synthesis

## 🚧 Ce qui reste à faire

### 1. Fix des bugs courants
- **Router Chat :** les endpoints retournent des listes au lieu de dictionnaires
  ```python
  # Problème : la réponse est [data, status_code] au lieu de juste data
  return build_error_response(...), status.HTTP_500_INTERNAL_SERVER_ERROR
  # → devrait retourner juste la réponse, le code est géré par FastAPI
  ```

### 2. ChromaDB
- Collections RAG initialisées et peuplées pour les trois domaines demandés.
- Documents juridiques français indexés localement dans les collections ChromaDB.
- Vérification de la présence des chunks effectuée avec succès.

### 3. Vertex AI
- Donner les permissions IAM nécessaires au compte de service
- Vérifier la configuration du projet Google Cloud

### 4. Tests complets
- Corriger `test-chat.py` pour parser les bonnes réponses
- Ajouter des tests unitaires pour chaque module
- Ajouter des tests d'intégration end-to-end

### 5. Migrations Alembic
- Configurer Alembic pour les migrations de DB
- Générer la première migration

### 6. Déploiement
- Dockerfile pour containeriser l'app
- Configuration pour production (DEBUG=False, etc.)

## 📁 Structure du Projet (complète)
```
AI-Orchestration-API/
├── app/
│   ├── agents/          # LangGraph nodes & graph
│   ├── core/            # Config, security, dependencies
│   ├── db/              # Models, database setup
│   ├── providers/       # LLM providers (Mistral, Vertex)
│   ├── rag/             # ChromaDB integration
│   ├── routers/         # API endpoints (auth, users, chat)
│   ├── schemas/         # Pydantic models
│   └── main.py          # App entrypoint
├── Concpetion/          # Design docs (contrats API, architecture)
├── .env                 # Configuration (non commitée)
├── .gitignore
├── requirements.txt
├── README.md
├── test-auth-users.sh   # Auth test script (✅ works)
└── test-chat.py         # Chat test script (en cours de fix)
```

## 🎯 Prochaines Étapes Prioritaires
1. Corriger les endpoints du chat router (retourner des dict, pas des listes)
2. Vérifier et fixer le LangGraph flow
3. Tester le chat endpoint en mode visiteur et authentifié
