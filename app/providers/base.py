"""
Interface abstraite commune à tous les fournisseurs LLM.
Les nœuds LangGraph et le reste du code métier ne connaissent QUE cette interface.

Contrat défini dans 05_guide_switch_provider_mistral_vertex.md §3.
"""

from abc import ABC, abstractmethod
from typing import List


class LLMProvider(ABC):
    """
    Contrat commun que doit respecter tout fournisseur LLM (Vertex AI, Mistral, etc.).
    Toute implémentation concrète doit hériter de cette classe et implémenter
    les deux méthodes ci-dessous.
    """

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Génère une réponse texte à partir d'un prompt système et d'un prompt utilisateur.

        Args:
            system_prompt: Instructions de rôle / contexte envoyées au modèle.
            user_prompt: Question ou instruction de l'utilisateur.
            temperature: Créativité du modèle (0 = déterministe, 1 = créatif).
            max_tokens: Nombre maximum de tokens générés dans la réponse.

        Returns:
            La réponse textuelle produite par le modèle LLM.
        """
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Retourne les vecteurs d'embedding pour une liste de textes.
        Utilisé pour l'indexation et la recherche sémantique dans ChromaDB (RAG).

        Args:
            texts: Liste de chaînes à encoder.

        Returns:
            Liste de vecteurs flottants, un par texte d'entrée.
        """
        raise NotImplementedError
