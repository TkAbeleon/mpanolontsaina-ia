"""
Implémentation du fournisseur LLM via le SDK officiel Mistral AI.
Fournisseur par défaut en développement (LLM_PROVIDER=mistral).

Référence : 05_guide_switch_provider_mistral_vertex.md §4.
"""

from typing import List

from mistralai import Mistral

from app.core.config import settings
from app.providers.base import LLMProvider


class MistralProvider(LLMProvider):
    """
    Adaptateur Mistral AI implémentant l'interface LLMProvider.

    Modèles utilisés (configurables via .env) :
      - Génération  : MISTRAL_CHAT_MODEL  (défaut : mistral-large-latest)
      - Embeddings  : MISTRAL_EMBED_MODEL (défaut : mistral-embed)
    """

    def __init__(self) -> None:
        self._client = Mistral(api_key=settings.MISTRAL_API_KEY)
        self._chat_model: str = settings.MISTRAL_CHAT_MODEL
        self._embed_model: str = settings.MISTRAL_EMBED_MODEL

    # ---------------------------------------------------------------------- #
    # Génération de texte
    # ---------------------------------------------------------------------- #
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Appelle l'API de complétion de chat Mistral avec un message système
        et un message utilisateur, et retourne le contenu textuel de la réponse.
        """
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

    # ---------------------------------------------------------------------- #
    # Génération d'embeddings (RAG / ChromaDB)
    # ---------------------------------------------------------------------- #
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Génère les vecteurs d'embedding pour une liste de textes via l'API
        Mistral Embeddings. Utilisé par SwitchableEmbeddingFunction pour ChromaDB.

        Note : mistral-embed est un modèle généraliste ; les performances sur le
        malagasy sont moindres que text-multilingual-embedding-002 de Vertex AI
        (cf. 05_guide_switch_provider_mistral_vertex.md §9).
        """
        result = self._client.embeddings.create(
            model=self._embed_model,
            inputs=texts,
        )
        return [item.embedding for item in result.data]
