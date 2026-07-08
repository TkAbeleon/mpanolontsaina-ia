"""
Module RAG : ChromaDB et embeddings pour la recherche sémantique juridique.
"""
from app.rag.chroma_client import (
    get_chroma_client,
    get_or_create_collection,
    query_collection,
    add_documents_to_collection,
)

__all__ = [
    "get_chroma_client",
    "get_or_create_collection",
    "query_collection",
    "add_documents_to_collection",
]
