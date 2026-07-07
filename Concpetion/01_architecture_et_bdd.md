### Fichier : 01_architecture_et_bdd.md

# Architecture Backend — Assistant Juridique Malgache Multi-Agents

## 1. Vue d'ensemble

Le système repose sur 4 briques principales qui collaborent selon un flux clair et découplé :

| Brique | Rôle |
|---|---|
| **FastAPI** | Point d'entrée HTTP, authentification, orchestration des appels métier, sérialisation des réponses |
| **PostgreSQL** | Persistance relationnelle : comptes utilisateurs, conversations, messages, métadonnées |
| **LangGraph** | Orchestration multi-agents (routage, collaboration, synthèse de la réponse juridique) |
| **ChromaDB** | Base vectorielle RAG : textes de loi malgaches (Code du travail, Code général des impôts, jurisprudence, etc.) |

FastAPI ne "sait" pas raisonner juridiquement : il délègue systématiquement la logique de réponse à un **graphe LangGraph compilé**, injecté comme une dépendance de service (pattern *Service Layer*). PostgreSQL et ChromaDB sont deux bases de données distinctes avec des responsabilités différentes :
- PostgreSQL = **état applicatif** (qui a dit quoi, quand, à qui).
- ChromaDB = **connaissance juridique** (corpus de textes de loi, embeddings, récupération sémantique).

## 2. Schéma d'architecture (flux logique)

```
┌─────────────┐        HTTPS/JSON        ┌──────────────────────────┐
│   Client    │ ───────────────────────► │        FastAPI            │
│ (Web/Mobile)│ ◄─────────────────────── │  (Routers + Middlewares)  │
└─────────────┘                          └────────────┬─────────────┘
                                                        │
                     ┌──────────────────────────────────┼───────────────────────────────┐
                     │                                  │                               │
                     ▼                                  ▼                               ▼
           ┌──────────────────┐              ┌───────────────────┐            ┌──────────────────┐
           │  Auth Service      │              │  Chat Service      │            │  In-Memory /       │
           │  (JWT, bcrypt)     │              │  (Controller Chat) │            │  Redis Cache        │
           └────────┬───────────┘              └─────────┬───────────┘            │  (sessions visiteurs)│
                    │                                    │                        └──────────────────┘
                    ▼                                    ▼
          ┌───────────────────┐             ┌─────────────────────────────┐
          │   PostgreSQL        │             │   LangGraph (graphe compilé)  │
          │  (users, conv,      │◄────────────│   Nœud Superviseur/Router     │
          │   messages)         │  persist    │   → Agents spécialisés        │
          └───────────────────┘  si connecté  │   → Nœud Agrégateur/Synthèse  │
                                              └───────────────┬───────────────┘
                                                              │ retrieval
                                                              ▼
                                                    ┌────────────────────┐
                                                    │      ChromaDB       │
                                                    │  (collections RAG)  │
                                                    │  - droit_travail    │
                                                    │  - fiscalite        │
                                                    │  - jurisprudence    │
                                                    └────────────────────┘
```

## 3. Détail du flux d'une requête de chat

1. Le client envoie un message via `POST /api/v1/chat/...` (endpoint visiteur ou utilisateur connecté).
2. Le middleware d'authentification FastAPI détermine si la requête porte un JWT valide → utilisateur connecté, sinon → visiteur (un `session_id` UUID temporaire est généré ou réutilisé).
3. Le **contrôleur Chat** construit un objet `AgentState` (dictionnaire typé, ex. `TypedDict` LangGraph) contenant : la question, l'historique pertinent, l'identité de l'utilisateur (ou None), le domaine juridique présumé.
4. Le contrôleur invoque le **graphe LangGraph compilé** (`graph.invoke(state)` ou `graph.astream(state)` pour du streaming).
5. À l'intérieur du graphe :
   - Le **nœud Superviseur** classifie l'intention (droit du travail, fiscalité, droit des affaires, etc.) et route conditionnellement (`add_conditional_edges`) vers le ou les agents spécialisés pertinents.
   - Chaque **agent spécialisé** interroge **ChromaDB** (via un nœud de retrieval, `collection.query(query_texts=[...], n_results=k)`) pour récupérer les extraits de loi pertinents, puis génère une réponse contextualisée (LLM + contexte RAG).
   - Un **nœud Agrégateur/Synthèse** fusionne les contributions des agents en une réponse finale unique, avec ses sources citées.
6. Le contrôleur FastAPI reçoit l'état final du graphe :
   - Si utilisateur connecté → persistance du message utilisateur + de la réponse assistant dans PostgreSQL (table `messages`).
   - Si visiteur → aucune écriture en base ; réponse simplement renvoyée au client, éventuellement mise en cache mémoire/Redis avec TTL court pour permettre la continuité de la conversation le temps de la session.
7. La réponse JSON est retournée au client.

## 4. Schéma de base de données relationnelle (PostgreSQL)

Toutes les tables utilisent des clés primaires **UUID** (meilleure compatibilité distribuée, pas d'énumération d'IDs séquentiels exposés).

### 4.1. Table `users`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | Identifiant unique |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Email de connexion |
| `hashed_password` | VARCHAR(255) | NULLABLE | Mot de passe hashé (bcrypt/argon2). NULL après anonymisation |
| `full_name` | VARCHAR(255) | NULLABLE | Nom complet |
| `is_active` | BOOLEAN | DEFAULT true | Compte actif ou désactivé |
| `is_deleted` | BOOLEAN | DEFAULT false | Marqueur de suppression (soft delete) |
| `role` | VARCHAR(50) | DEFAULT 'user' | `user`, `admin` |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Date de création |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | Dernière mise à jour |
| `deleted_at` | TIMESTAMPTZ | NULLABLE | Date de suppression / anonymisation |

### 4.2. Table `refresh_tokens` (gestion des sessions d'authentification)

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant du token |
| `user_id` | UUID | FK → `users.id`, NOT NULL, ON DELETE CASCADE | Propriétaire |
| `token_hash` | VARCHAR(255) | NOT NULL | Hash du refresh token |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Expiration |
| `revoked` | BOOLEAN | DEFAULT false | Révoqué manuellement (logout) |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Création |

### 4.3. Table `conversations`

Une conversation n'existe **que pour les utilisateurs connectés** (le chat visiteur ne crée jamais de ligne ici).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant de la conversation |
| `user_id` | UUID | FK → `users.id`, NOT NULL, ON DELETE CASCADE | Propriétaire |
| `title` | VARCHAR(255) | NULLABLE | Titre auto-généré (résumé de la 1ère question) |
| `is_archived` | BOOLEAN | DEFAULT false | Archivage logique |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Création |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | Dernier message |

### 4.4. Table `messages`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | UUID | PK | Identifiant du message |
| `conversation_id` | UUID | FK → `conversations.id`, NOT NULL, ON DELETE CASCADE | Conversation parente |
| `role` | VARCHAR(20) | NOT NULL | `user`, `assistant`, `system` |
| `content` | TEXT | NOT NULL | Contenu du message |
| `agent_source` | VARCHAR(100) | NULLABLE | Agent LangGraph ayant produit la réponse (ex: `droit_travail_agent`) |
| `sources` | JSONB | NULLABLE | Extraits/citations juridiques utilisés (issus de ChromaDB) |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Horodatage |

### 4.5. Table `visitor_sessions` (optionnelle, stockage court terme hors Postgres recommandé)

> ⚠️ Recommandation : ne **pas** stocker les sessions visiteurs en PostgreSQL pour respecter la règle "non persistant". Utiliser un cache **Redis** avec TTL (ex: 30 minutes) sur la clé `session:{session_id}` contenant l'historique court de la conversation en mémoire. Cette table n'est décrite ici qu'à titre indicatif si aucune solution Redis n'est disponible et qu'un stockage technique minimal et auto-expirant est nécessaire :

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `session_id` | UUID | PK | Identifiant temporaire |
| `payload` | JSONB | NOT NULL | Historique conversationnel court |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Expiration (purge automatique par job CRON) |

## 5. Droit à l'oubli — stratégie retenue

Deux approches sont possibles ; la recommandation ci-dessous couvre les deux cas d'usage :

- **Hard Delete** (suppression physique totale) : `DELETE FROM users WHERE id = :id` avec `ON DELETE CASCADE` sur `conversations`, `messages`, `refresh_tokens`. Simple, radical, conforme à une demande stricte d'effacement.
- **Soft Delete + anonymisation totale** (recommandé si des statistiques d'usage agrégées doivent être conservées à des fins d'amélioration du service) :
  - `email` → remplacé par une valeur anonymisée unique (ex: `deleted_<uuid>@anonymous.local`)
  - `hashed_password` → `NULL`
  - `full_name` → `"Utilisateur supprimé"`
  - `is_deleted` → `true`, `deleted_at` → `now()`
  - Contenu des `messages` liés → soit supprimé (`content = NULL`), soit conservé de façon totalement dissociée de toute identité (aucune table ne doit permettre de remonter à l'utilisateur).
  - Tous les `refresh_tokens` sont révoqués immédiatement.

Le choix entre les deux stratégies est exposé à l'utilisateur au moment de la suppression de compte (voir `02_contrats_api_auth_users.md`, endpoint `DELETE /api/v1/users/me`).

## 6. Support multilingue (Malagasy / Français / Anglais)

L'agent doit pouvoir **comprendre** une question posée dans n'importe laquelle des 3 langues (`mg`, `fr`, `en`) et **répondre dans la même langue** (ou dans une langue explicitement demandée par l'utilisateur), quel que soit le domaine juridique traité.

### 6.1. Principe retenu

Le multilinguisme n'est **pas géré par de la traduction statique de textes d'interface**, mais directement par le modèle LLM sous-jacent (via Vertex AI / Gemini, cf. `04_guide_implementation_vertex_ai.md`), qui est nativement multilingue. Le rôle de l'architecture applicative est de :
1. **Détecter/recevoir** la langue de la requête.
2. **Forcer explicitement** la langue de sortie dans le prompt système envoyé au modèle.
3. **Conserver la langue** utilisée pour la traçabilité (statistiques, préférences utilisateur, cohérence du fil de conversation).

### 6.2. Impact sur `AgentState` (LangGraph)

Un nouveau nœud **`language_detection`** est ajouté en tout début de graphe, avant le `supervisor` :

```python
class AgentState(TypedDict):
    question: str
    history: List[dict]
    user_id: Optional[str]
    language: Optional[str]        # "mg" | "fr" | "en" — NOUVEAU
    domain: Optional[str]
    retrieved_context: Optional[list]
    final_answer: Optional[str]
    agent_source: Optional[str]
```

- Si le client fournit explicitement `language` dans le payload (préférence utilisateur ou sélecteur d'interface), ce choix est **prioritaire** et aucune détection n'est effectuée.
- Sinon, le nœud `language_detection` déduit la langue à partir du texte de la question (détection automatique via le LLM lui-même ou une librairie légère de détection de langue, en tenant compte du fait que le malgache est sous-représenté dans les détecteurs classiques — voir `04_guide_implementation_vertex_ai.md` §3).
- La langue détectée/choisie est propagée à **tous les nœuds** du graphe (retrieval, agents spécialisés, synthèse) afin que la réponse finale soit rédigée dans cette langue, même si les textes de loi source (ChromaDB) sont eux majoritairement en français.

### 6.3. Impact sur la base de données

**Table `users`** — ajout d'une colonne :

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `preferred_language` | VARCHAR(5) | DEFAULT `'fr'` | Langue préférée (`mg`, `fr`, `en`) appliquée par défaut aux nouvelles conversations |

**Table `messages`** — ajout d'une colonne :

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `language` | VARCHAR(5) | NOT NULL, DEFAULT `'fr'` | Langue effective du message (détectée ou choisie) |

**Table `conversations`** — ajout d'une colonne facultative :

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `language` | VARCHAR(5) | NULLABLE | Langue dominante de la conversation, utile pour l'affichage du titre et le filtrage |

### 6.4. Organisation des collections ChromaDB face au multilinguisme

Le corpus juridique malgache (lois, jurisprudence) est très majoritairement rédigé **en français** (héritage du droit positif malgache). Deux stratégies sont possibles, non exclusives :

- **Stratégie A — retrieval en français, génération dans la langue cible** (recommandée en premier lieu) : la question de l'utilisateur (mg/en) est traduite en français uniquement pour l'étape de retrieval ChromaDB (le texte de loi lui-même n'est jamais traduit ni ré-indexé), puis la réponse finale est rédigée par le LLM directement dans la langue d'origine de la question, en citant les articles de loi (dont les titres/numéros restent inchangés).
- **Stratégie B — indexation d'embeddings multilingues** : utiliser un modèle d'embedding multilingue (ex. `text-multilingual-embedding-002` sur Vertex AI) permettant une recherche vectorielle directement à partir d'une question en malgache ou en anglais, sans étape de traduction intermédiaire. Cette approche est recommandée à moyen terme, une fois le corpus stabilisé.

## 7. Organisation des collections ChromaDB (RAG)

| Collection | Contenu |
|---|---|
| `droit_travail_mg` | Code du travail malgache, conventions collectives |
| `fiscalite_mg` | Code général des impôts, textes fiscaux |
| `droit_affaires_mg` | Droit des sociétés, OHADA (le cas échéant) |
| `jurisprudence_mg` | Décisions de justice pertinentes |

Chaque document est indexé avec des métadonnées (`article`, `code`, `date_publication`, `url_source`) permettant de reconstituer les citations dans le champ `sources` (JSONB) de la table `messages`.
