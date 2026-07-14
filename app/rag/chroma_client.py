"""
Client ChromaDB pour la recherche sémantique RAG.
Références :
  - 01_architecture_et_bdd.md §7
  - 04_guide_implementation_vertex_ai.md §3.3
  - 05_guide_switch_provider_mistral_vertex.md §8
"""
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb import Collection
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.core.config import settings
from app.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


# =============================================================================
# Embedding function qui utilise notre abstraction LLMProvider
# =============================================================================
class SwitchableEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Fonction d'embedding qui délègue au LLMProvider actif (Mistral ou Vertex).
    Utilisée par ChromaDB pour indexer et requêter les documents.
    """

    def __call__(self, input: Documents) -> Embeddings:
        provider = get_llm_provider()
        docs = list(input)
        if not docs:
            return []

        # Vertex AI applique une limite stricte sur le nombre de tokens par requête.
        # On envoie les documents par petits lots pour éviter l'erreur 400.
        batch_size = 4
        all_embeddings: List[List[float]] = []
        for start in range(0, len(docs), batch_size):
            batch = docs[start:start + batch_size]
            try:
                all_embeddings.extend(provider.embed(batch))
            except Exception as exc:
                logger.error("Erreur lors de l'embedding du lot %d-%d : %s", start, start + batch_size, exc)
                raise
        return all_embeddings


# =============================================================================
# Client ChromaDB singleton
# =============================================================================
_chroma_client: Optional[chromadb.Client] = None
_collections: Dict[str, Collection] = {}


def get_chroma_client() -> chromadb.Client:
    """Récupère ou crée le client ChromaDB (singleton)."""
    global _chroma_client
    if _chroma_client is None:
        logger.info("Initialisation du client ChromaDB (path=%s)", settings.CHROMA_PERSIST_DIR)
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
    logger.debug("Collection ChromaDB '%s' prête (%d documents).", name, collection.count())
    return collection


# =============================================================================
# Fonctions utilitaires
# =============================================================================
def query_collection(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Interroge une collection ChromaDB.

    Retourne les résultats avec les documents, métadonnées et distances.
    Retourne un dict vide si la collection est vide ou si une erreur survient.
    """
    collection = get_or_create_collection(collection_name)

    # Vérifie que la collection contient des documents avant de requêter
    count = collection.count()
    if count == 0:
        logger.warning("La collection '%s' est vide. Aucun document RAG disponible.", collection_name)
        return {}

    # Ajuste n_results si la collection contient moins de documents que demandé
    actual_n = min(n_results, count)

    try:
        results = collection.query(
            query_texts=query_texts,
            n_results=actual_n,
            where=where,
        )
        return results
    except Exception as exc:
        logger.error("Erreur lors du query ChromaDB (collection=%s) : %s", collection_name, exc)
        return {}


def add_documents_to_collection(
    collection_name: str,
    documents: List[str],
    metadatas: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
) -> int:
    """
    Ajoute des documents à une collection ChromaDB.
    Retourne le nombre de documents dans la collection après l'ajout.
    """
    collection = get_or_create_collection(collection_name)
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    count = collection.count()
    logger.info("Ajout de %d documents à '%s'. Total : %d.", len(documents), collection_name, count)
    return count


def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """
    Retourne des informations de debug sur une collection ChromaDB.
    Utile pour diagnostiquer les problèmes RAG.
    """
    try:
        collection = get_or_create_collection(collection_name)
        count = collection.count()
        return {
            "name": collection_name,
            "count": count,
            "status": "ok" if count > 0 else "empty",
        }
    except Exception as exc:
        return {
            "name": collection_name,
            "count": 0,
            "status": "error",
            "error": str(exc),
        }


# =============================================================================
# Noms des collections prédéfinies
# =============================================================================
COLLECTIONS = {
    "droit_travail": "droit_travail_mg",
    "fiscalite": "fiscalite_mg",
    "droit_affaires": "droit_affaires_mg",
    "jurisprudence": "jurisprudence_mg",
    "foncier": "foncier_mg",
    "famille": "famille_mg",
}
