### Fichier : 05_guide_switch_provider_mistral_vertex.md

# Guide — Abstraction Fournisseur LLM (Mistral ↔ Vertex AI) via `.env`

## 1. Contexte et objectif

Vertex AI n'étant **pas encore disponible** (accès GCP en cours de provisionnement / validation), le développement doit pouvoir démarrer immédiatement avec **Mistral AI** comme fournisseur LLM de substitution, sans bloquer l'équipe.

Le code métier (nœuds LangGraph, retrieval ChromaDB) ne doit **jamais dépendre directement** d'un SDK propriétaire (`google-genai` ou `mistralai`). Il doit passer par une **interface d'abstraction commune** (`LLMProvider`), et le choix du fournisseur concret doit être **un simple paramètre de configuration** (`.env`), sans toucher au code métier ni au graphe LangGraph.

```
LLM_PROVIDER=mistral   # développement (Vertex AI non disponible)
LLM_PROVIDER=vertex    # production, une fois l'accès GCP validé
```

---

## 2. Principe d'architecture : le pattern Adapter

```
┌───────────────────────────┐
│   Nœuds LangGraph          │   ← ne connaissent QUE l'interface LLMProvider
│  (supervisor, agents,      │
│   synthesis, retrieval)    │
└─────────────┬─────────────┘
              │ appelle
              ▼
┌───────────────────────────┐
│   LLMProvider (interface)  │   ← contrat abstrait, unique point d'entrée
│  .generate(...)             │
│  .embed(...)                 │
└─────────────┬─────────────┘
              │ implémenté par
      ┌───────┴────────┐
      ▼                ▼
┌───────────┐   ┌───────────────┐
│ MistralProvider │   │ VertexAIProvider │
│ (dev, dispo.  │   │ (prod, à activer│
│ immédiatement)│   │  dès accès GCP) │
└───────────┘   └───────────────┘
```

Le **factory** (`get_llm_provider()`) lit la variable d'environnement `LLM_PROVIDER` une seule fois au démarrage de l'application et instancie le bon adaptateur. Tout le reste du code (LangGraph, ChromaDB) est totalement agnostique du fournisseur réellement utilisé.

---

## 3. Interface commune `LLMProvider`

```python
# core/llm/base.py
from abc import ABC, abstractmethod
from typing import List



class LLMProvider(ABC):
    """Contrat commun que doit respecter tout fournisseur LLM (Vertex AI, Mistral, etc.)."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Génère une réponse texte à partir d'un prompt système + utilisateur."""
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Retourne les vecteurs d'embedding pour une liste de textes (usage RAG/ChromaDB)."""
        raise NotImplementedError
```

---

## 4. Implémentation Mistral (fournisseur de développement)

```python
# core/llm/mistral_provider.py
import os
from mistralai import Mistral
from core.llm.base import LLMProvider



class MistralProvider(LLMProvider):
    def __init__(self):
        self._client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self._chat_model = os.environ.get("MISTRAL_CHAT_MODEL", "mistral-large-latest")
        self._embed_model = os.environ.get("MISTRAL_EMBED_MODEL", "mistral-embed")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        response = self._client.chat.complete(
            model=self._chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def embed(self, texts):
        result = self._client.embeddings.create(
            model=self._embed_model,
            inputs=texts,
        )
        return [item.embedding for item in result.data]
```

---

## 5. Implémentation Vertex AI (fournisseur de production, à activer plus tard)

```python
# core/llm/vertex_provider.py
import os
from google import genai
from core.llm.base import LLMProvider



class VertexAIProvider(LLMProvider):
    def __init__(self):
        self._client = genai.Client(
            vertexai=True,
            project=os.environ["GCP_PROJECT_ID"],
            location=os.environ.get("GCP_LOCATION", "europe-west1"),
        )
        self._chat_model = os.environ.get("GEMINI_MODEL", "gemini-3-flash")
        self._embed_model = os.environ.get("GEMINI_EMBEDDING_MODEL", "text-multilingual-embedding-002")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        response = self._client.models.generate_content(
            model=self._chat_model,
            contents=[{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return response.text

    def embed(self, texts):
        result = self._client.models.embed_content(model=self._embed_model, contents=texts)
        return [e.values for e in result.embeddings]
```

---

## 6. Factory — le switch simple via `.env`

```python
# core/llm/factory.py
import os
from functools import lru_cache
from core.llm.base import LLMProvider



@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """
    Point d'entrée UNIQUE utilisé par tout le reste de l'application.
    Le fournisseur réel est déterminé par la variable d'environnement LLM_PROVIDER.
    """
    provider_name = os.environ.get("LLM_PROVIDER", "mistral").lower()

    if provider_name == "mistral":
        from core.llm.mistral_provider import MistralProvider
        return MistralProvider()

    if provider_name == "vertex":
        from core.llm.vertex_provider import VertexAIProvider
        return VertexAIProvider()

    raise ValueError(
        f"LLM_PROVIDER='{provider_name}' inconnu. Valeurs acceptées : 'mistral', 'vertex'."
    )
```

> `lru_cache(maxsize=1)` garantit une instanciation **unique** du client (singleton), important pour la réutilisation des connexions HTTP et pour éviter de relire les credentials à chaque appel. L'import du SDK concret (`mistralai` ou `google-genai`) est fait **à l'intérieur** de la fonction (import différé) afin qu'un seul des deux SDK ait réellement besoin d'être installé/configuré selon l'environnement.

### 6.1. Fichier `.env` — développement (Mistral)

```dotenv
# --- Choix du fournisseur LLM ---
LLM_PROVIDER=mistral

# --- Mistral AI (développement) ---
MISTRAL_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
MISTRAL_CHAT_MODEL=mistral-large-latest
MISTRAL_EMBED_MODEL=mistral-embed

# --- Vertex AI (non utilisé tant que LLM_PROVIDER != vertex, peut rester vide) ---
GCP_PROJECT_ID=
GCP_LOCATION=
GEMINI_MODEL=
GEMINI_EMBEDDING_MODEL=
```

### 6.2. Fichier `.env` — production (Vertex AI, une fois l'accès validé)

```dotenv
# --- Choix du fournisseur LLM ---
LLM_PROVIDER=vertex

# --- Vertex AI (production) ---
GCP_PROJECT_ID=assistant-juridique-mg-prod
GCP_LOCATION=europe-west1
GEMINI_MODEL=gemini-3-flash
GEMINI_EMBEDDING_MODEL=text-multilingual-embedding-002
GOOGLE_APPLICATION_CREDENTIALS=/secrets/vertex-sa.json

# --- Mistral (peut rester configuré comme fallback, voir §8) ---
MISTRAL_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
MISTRAL_CHAT_MODEL=mistral-large-latest
MISTRAL_EMBED_MODEL=mistral-embed
```

> **Aucune ligne de code métier ne change entre les deux environnements.** Seul le fichier `.env` (ou les variables d'environnement injectées par l'orchestrateur de déploiement — Docker Compose, Kubernetes ConfigMap/Secret, etc.) diffère.

---

## 7. Impact sur les nœuds LangGraph (code inchangé vis-à-vis du fournisseur)

Les nœuds n'appellent plus jamais directement `google-genai` ou `mistralai` : ils utilisent uniquement `get_llm_provider()`.

```python
# agents/nodes/droit_travail.py
from core.llm.factory import get_llm_provider

LANGUAGE_LABELS = {
    "mg": "malagasy (fiteny malagasy ofisialy)",
    "fr": "français",
    "en": "anglais",
}

def droit_travail_node(state: AgentState) -> AgentState:
    provider = get_llm_provider()  # Mistral en dev, Vertex AI en prod — transparent
    lang_label = LANGUAGE_LABELS[state["language"]]

    system_prompt = f"""
    Tu es un agent juridique spécialisé en DROIT DU TRAVAIL MALGACHE.
    Réponds impérativement en {lang_label}, même si les extraits de loi
    fournis en contexte sont rédigés en français.
    Cite précisément les articles de loi utilisés.

    Contexte juridique (extraits de loi) :
    {state.get("retrieved_context", "Aucun contexte disponible.")}
    """

    answer = provider.generate(
        system_prompt=system_prompt,
        user_prompt=state["question"],
        temperature=0.2,
        max_tokens=1024,
    )

    return {**state, "final_answer": answer, "agent_source": "droit_travail_agent"}
```

```python
# agents/nodes/language_detection.py
from core.llm.factory import get_llm_provider

SYSTEM_PROMPT_LANG_DETECT = (
    "Tu es un détecteur de langue. Réponds UNIQUEMENT par un code parmi : "
    "mg, fr, en (aucun autre mot). mg = malagasy, fr = français, en = anglais."
)

def language_detection_node(state: AgentState) -> AgentState:
    if state.get("language"):
        return state
    provider = get_llm_provider()
    lang = provider.generate(
        system_prompt=SYSTEM_PROMPT_LANG_DETECT,
        user_prompt=state["question"],
        temperature=0,
        max_tokens=5,
    ).strip().lower()
    return {**state, "language": lang if lang in ("mg", "fr", "en") else "fr"}
```

---

## 8. Impact sur l'embedding function ChromaDB (même logique de switch)

```python
# rag/embeddings.py
from chromadb import Documents, EmbeddingFunction, Embeddings
from core.llm.factory import get_llm_provider



class SwitchableEmbeddingFunction(EmbeddingFunction):
    """Délègue la génération d'embeddings au fournisseur actif (Mistral ou Vertex AI)."""

    def __call__(self, input: Documents) -> Embeddings:
        provider = get_llm_provider()
        return provider.embed(list(input))
```

```python
# rag/chroma_setup.py
import chromadb
from rag.embeddings import SwitchableEmbeddingFunction

chroma_client = chromadb.PersistentClient(path="./chroma_data")

collection = chroma_client.get_or_create_collection(
    name="droit_travail_mg",
    embedding_function=SwitchableEmbeddingFunction(),
    metadata={"hnsw:space": "cosine"},
)
```

> ⚠️ **Point d'attention important** : les espaces vectoriels de `mistral-embed` et `text-multilingual-embedding-002` ne sont **pas compatibles entre eux** (dimensions et distributions différentes). Si le corpus ChromaDB a été indexé avec Mistral en développement, il faudra **ré-indexer entièrement** les collections après bascule vers Vertex AI en production (script de ré-ingestion à prévoir, ne jamais mélanger les deux embeddings dans une même collection).

---

## 9. Limites connues de Mistral pour ce cas d'usage (à garder en tête en dev)

| Aspect                           | Mistral (dev)                                                                                                                                                                                                     | Vertex AI / Gemini (cible prod)                                                                                                       |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Français                        | Très bon (langue forte de Mistral, éditeur français)                                                                                                                                                           | Très bon                                                                                                                             |
| Anglais                          | Très bon                                                                                                                                                                                                         | Très bon                                                                                                                             |
| **Malagasy**               | Support**plus faible et moins prévisible** (langue peu représentée dans le corpus d'entraînement) — à valider empiriquement avec le golden dataset (cf. `04_guide_implementation_vertex_ai.md` §5) | Meilleur support relatif du malagasy, à re-valider également mais généralement plus robuste sur les langues à faibles ressources |
| Embeddings multilingues dédiés | `mistral-embed` (généraliste, pas spécifiquement optimisé multilingue)                                                                                                                                      | `text-multilingual-embedding-002` (conçu pour le multilingue)                                                                      |
| Disponibilité                   | Immédiate                                                                                                                                                                                                        | En attente de validation de l'accès GCP                                                                                              |

**Recommandation** : pendant la phase de développement sous Mistral, prévoir un jeu de tests spécifique aux questions en malagasy et documenter les écarts de qualité observés. Ces écarts sont **attendus** et ne doivent pas être interprétés comme un bug applicatif — ils disparaîtront ou s'atténueront lors de la bascule vers Vertex AI via le simple changement de `LLM_PROVIDER=vertex` dans le `.env`.

---

## 10. Checklist de bascule Mistral → Vertex AI (jour J)

1. Obtenir et valider l'accès au projet GCP (cf. `04_guide_implementation_vertex_ai.md` §1).
2. Renseigner les variables `GCP_PROJECT_ID`, `GCP_LOCATION`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `GOOGLE_APPLICATION_CREDENTIALS` dans le `.env` de l'environnement cible.
3. Changer uniquement `LLM_PROVIDER=mistral` → `LLM_PROVIDER=vertex`.
4. **Ré-indexer** les collections ChromaDB avec le nouvel embedding (les vecteurs Mistral et Vertex AI ne sont pas interchangeables — voir §8).
5. Rejouer le golden dataset multilingue (mg/fr/en) pour valider la qualité des réponses avant mise en production définitive.
6. Aucune modification du code des nœuds LangGraph, des contrôleurs FastAPI ni des contrats d'API n'est nécessaire : l'abstraction `LLMProvider` absorbe entièrement le changement de fournisseur.

