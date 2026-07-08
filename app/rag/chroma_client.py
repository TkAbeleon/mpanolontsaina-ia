"""
Client ChromaDB pour la recherche sémantique RAG.
Références :
  - 01_architecture_et_bdd.md §7
  - 04_guide_implementation_vertex_ai.md §3.3
  - 05_guide_switch_provider_mistral_vertex.md §8
"""
from typing import Any, List, Optional

import chromadb
from chromadb import Collection
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.core.config import settings
from app.providers.factory import get_llm_provider


# =============================================================================
# Embedding function qui utilise notre abstraction LLMProvider
# =============================================================================
class SwitchableEmbeddingFunction(EmbeddingFunction[Documents]):
    """Fonction d'embedding qui délègue au LLMProvider actif (Mistral ou Vertex)."""
    def __call__(self, input: Documents) -> Embeddings:
        provider = get_llm_provider()
        return provider.embed(list(input))


# =============================================================================
# Client ChromaDB singleton
# =============================================================================
_chroma_client: Optional[chromadb.Client] = None
_collections: dict[str, Collection] = {}


def get_chroma_client() -> chromadb.Client:
    """Récupère ou crée le client ChromaDB (singleton)."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_or_create_collection(name: str) -> Collection:
    """Récupère ou crée une collection ChromaDB avec la fonction d'embedding switchable."""
    global _collections
    if name in _collections:
        return _collections[name]

    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=name,
        embedding_function=SwitchableEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    _collections[name] = collection
    return collection


# =============================================================================
# Fonctions utilitaires
# =============================================================================
def query_collection(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 5,
    where: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Interroge une collection ChromaDB.
    Retourne les résultats avec les documents, métadonnées et distances.
    """
    collection = get_or_create_collection(collection_name)
    results = collection.query(
        query_texts=query_texts,
        n_results=n_results,
        where=where,
    )
    return results


def add_documents_to_collection(
    collection_name: str,
    documents: List[str],
    metadatas: Optional[List[dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
) -> None:
    """Ajoute des documents à une collection ChromaDB."""
    collection = get_or_create_collection(collection_name)
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )


# =============================================================================
# Noms des collections prédéfinies
# =============================================================================
COLLECTIONS = {
    "droit_travail": "droit_travail_mg",
    "fiscalite": "fiscalite_mg",
    "droit_affaires": "droit_affaires_mg",
    "jurisprudence": "jurisprudence_mg",
}
