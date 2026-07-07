### Fichier : 04_guide_implementation_vertex_ai.md

# Guide d'implémentation — IA via Google Vertex AI (Gemini)

> Périmètre : ce guide couvre l'intégration concrète de **Vertex AI** (plateforme Google Cloud, désormais regroupée sous *Gemini Enterprise Agent Platform*) comme moteur LLM des agents LangGraph, la génération d'embeddings pour ChromaDB, et la gestion native du **support trilingue MG/FR/EN**.
>
> ⚠️ Les noms de modèles évoluent rapidement chez Google (la famille Gemini 3 a récemment remplacé Gemini 2.5 en disponibilité générale). Avant mise en production, vérifier systématiquement la page officielle des modèles (`docs.cloud.google.com/vertex-ai/generative-ai/docs/models`) pour confirmer l'identifiant exact et la date de retrait (*deprecation*) du modèle choisi.

---

## 1. Pré-requis Google Cloud

1. **Créer un projet Google Cloud** dédié (ex. `assistant-juridique-mg-prod`).
2. **Activer les API** nécessaires :
   ```bash
   gcloud services enable aiplatform.googleapis.com
   gcloud services enable compute.googleapis.com
   ```
3. **Choisir une région** supportant Gemini (ex. `us-central1` ou `europe-west1` — vérifier la disponibilité multi-région, aucune région n'existe physiquement à Madagascar : privilégier la région la plus proche en termes de latence réseau, généralement `europe-west1` ou `europe-west4` pour l'Afrique/Europe).
4. **Créer un compte de service** dédié au backend FastAPI avec le rôle IAM minimal :
   - `roles/aiplatform.user` (appel des modèles Gemini)
   - Pas de rôle `Owner`/`Editor` en production.
5. **Authentification** : privilégier **Workload Identity Federation** (pas de clé JSON stockée en dur) si le backend tourne sur GKE/Cloud Run. En développement local, utiliser `gcloud auth application-default login` ou une clé de compte de service montée en variable d'environnement `GOOGLE_APPLICATION_CREDENTIALS`.

---

## 2. Installation et configuration côté FastAPI

### 2.1. Dépendances

```bash
pip install google-genai langgraph langchain-google-vertexai chromadb fastapi
```

### 2.2. Client Vertex AI (SDK `google-genai`)

```python
# core/vertex_client.py
import os
from google import genai

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
LOCATION = os.environ.get("GCP_LOCATION", "europe-west1")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

# Modèles utilisés (à ajuster selon la disponibilité au moment du déploiement) :
GENERATION_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash")       # génération de réponses
EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "text-multilingual-embedding-002")  # RAG
```

> Utiliser des **variables d'environnement** pour le nom du modèle (jamais en dur dans le code métier) afin de pouvoir basculer de version sans redéploiement complet (cf. recommandation Google Cloud d'utiliser un mécanisme de configuration distante pour ce paramètre).

---

## 3. Intégration dans les nœuds LangGraph

### 3.1. Nœud de détection de langue (`language_detection_node`)

Le malgache étant sous-représenté dans les librairies classiques de détection de langue (`langdetect`, `fasttext`), la détection est déléguée **au modèle Gemini lui-même**, qui gère nativement le malgache, le français et l'anglais.

```python
# agents/nodes/language_detection.py
from core.vertex_client import client, GENERATION_MODEL

SYSTEM_PROMPT_LANG_DETECT = """
Tu es un détecteur de langue. Analyse le texte suivant et réponds
UNIQUEMENT par un code parmi : mg, fr, en (aucun autre mot, aucune ponctuation).
mg = malagasy, fr = français, en = anglais.
"""

def detect_language_via_llm(question: str) -> str:
    response = client.models.generate_content(
        model=GENERATION_MODEL,
        contents=[
            {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT_LANG_DETECT}\n\nTexte : {question}"}]}
        ],
        config={"temperature": 0, "max_output_tokens": 5},
    )
    lang = response.text.strip().lower()
    return lang if lang in ("mg", "fr", "en") else "fr"  # repli par défaut
```

### 3.2. Nœud agent spécialisé (ex. droit du travail)

Le prompt système **impose explicitement la langue de réponse** (`state["language"]`) et le domaine juridique.

```python
# agents/nodes/droit_travail.py
from core.vertex_client import client, GENERATION_MODEL

LANGUAGE_LABELS = {
    "mg": "malagasy (fiteny malagasy ofisialy)",
    "fr": "français",
    "en": "anglais",
}

def droit_travail_node(state: AgentState) -> AgentState:
    lang_label = LANGUAGE_LABELS[state["language"]]

    system_prompt = f"""
    Tu es un agent juridique spécialisé en DROIT DU TRAVAIL MALGACHE.
    Réponds impérativement en {lang_label}, même si les extraits de loi
    fournis en contexte sont rédigés en français.
    Cite précisément les articles de loi utilisés.
    Ne donne jamais de conseil hors du cadre légal malgache.

    Contexte juridique (extraits de loi) :
    {state.get("retrieved_context", "Aucun contexte disponible.")}
    """

    response = client.models.generate_content(
        model=GENERATION_MODEL,
        contents=[
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\nQuestion : {state['question']}"}]}
        ],
        config={"temperature": 0.2, "max_output_tokens": 1024},
    )

    return {
        **state,
        "final_answer": response.text,
        "agent_source": "droit_travail_agent",
    }
```

> **Bonne pratique multilingue** : ne jamais mélanger dans le même prompt système des instructions en plusieurs langues de façon incohérente. Le prompt de contrôle (système) peut rester en français en interne, seule la **consigne de langue de sortie** doit être sans ambiguïté (`Réponds impérativement en malagasy`).

### 3.3. Génération d'embeddings pour ChromaDB (RAG multilingue)

Pour permettre une recherche vectorielle correcte même si la question est posée en malgache ou en anglais alors que le corpus légal est en français, utiliser un modèle d'**embedding multilingue** de Vertex AI plutôt que le modèle par défaut de ChromaDB.

```python
# rag/embeddings.py
from core.vertex_client import client, EMBEDDING_MODEL
from chromadb import Documents, EmbeddingFunction, Embeddings

class VertexMultilingualEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=input,
        )
        return [e.values for e in result.embeddings]
```

```python
# rag/chroma_setup.py
import chromadb
from rag.embeddings import VertexMultilingualEmbeddingFunction

chroma_client = chromadb.PersistentClient(path="./chroma_data")

collection = chroma_client.get_or_create_collection(
    name="droit_travail_mg",
    embedding_function=VertexMultilingualEmbeddingFunction(),
    metadata={"hnsw:space": "cosine"},
)
```

> Le **texte source indexé reste en français** (langue du corpus légal officiel). C'est l'usage d'un embedding multilingue qui permet à une question posée en malgache ou en anglais d'être rapprochée sémantiquement des bons articles de loi français, sans avoir à traduire ni ré-indexer le corpus.

### 3.4. Nœud de synthèse (agrégation multi-agents)

```python
# agents/nodes/synthesis.py
def synthesis_node(state: AgentState) -> AgentState:
    # Si un seul agent a répondu, on peut court-circuiter la synthèse.
    if state.get("final_answer"):
        return state

    # Cas multi-agents (plusieurs domaines déclenchés) : fusionner les contributions
    # en un seul appel Gemini, toujours dans state["language"].
    ...
    return state
```

---

## 4. Paramétrage recommandé des appels Gemini

| Paramètre | Valeur recommandée | Justification |
|---|---|---|
| `temperature` | `0.1` – `0.3` | Réponses juridiques factuelles, faible créativité souhaitée |
| `max_output_tokens` | `1024` – `2048` | Réponses détaillées mais bornées (coût/latence) |
| `top_p` | valeur par défaut du modèle | Suffisant pour un cas d'usage factuel |
| Sécurité (`safety_settings`) | seuils par défaut de Vertex AI, ajustés si besoin | Éviter le sur-filtrage de contenus juridiques sensibles (ex. violences conjugales en droit pénal) tout en gardant la modération active |

---

## 5. Observabilité, coûts et fiabilité

- **Logging structuré** : journaliser (sans données personnelles sensibles) le modèle utilisé, le nombre de tokens, la langue détectée/utilisée, et l'agent déclenché — utile pour le debug et le suivi de coûts par langue/domaine.
- **Gestion des quotas** : Vertex AI applique des quotas par région/projet ; prévoir une stratégie de repli (retry avec backoff exponentiel) en cas de `429 Resource Exhausted`.
- **Cache de réponses fréquentes** : pour les questions juridiques génériques et récurrentes (FAQ), envisager un cache applicatif (Redis) clé par `(question_normalisée, langue, domaine)` afin de réduire les coûts d'appel au modèle.
- **Suivi des dépréciations de modèles** : Google annonce des dates de retrait de modèles (ex. bascule Gemini 2.x → Gemini 3.x). Le nom de modèle doit rester **configurable sans redéploiement** (variable d'environnement ou Remote Config) pour anticiper ces migrations.
- **Évaluation qualité multilingue** : mettre en place un jeu de test (golden dataset) de questions juridiques en malgache, français et anglais avec réponses de référence, rejoué à chaque changement de modèle ou de prompt système, pour détecter toute régression de qualité — en particulier sur le malagasy, langue moins richement représentée dans les données d'entraînement des LLM généralistes.

---

## 6. Résumé du flux technique complet

```
Requête utilisateur (mg/fr/en)
        │
        ▼
FastAPI (résolution de langue : payload > préférence utilisateur > détection)
        │
        ▼
LangGraph.ainvoke(state)
        │
        ├─► language_detection_node ── (si nécessaire) ──► Vertex AI Gemini (classification langue)
        │
        ├─► supervisor_node ── (classification du domaine juridique) ──► Vertex AI Gemini
        │
        ├─► retrieval_node ── embeddings de la question ──► Vertex AI Embedding API ──► ChromaDB.query()
        │
        ├─► agent(s) spécialisé(s) ── génération contextualisée dans la langue cible ──► Vertex AI Gemini
        │
        └─► synthesis_node ── réponse finale unifiée ──► retour à FastAPI
        │
        ▼
Persistance conditionnelle (PostgreSQL si connecté) + réponse JSON au client
```
