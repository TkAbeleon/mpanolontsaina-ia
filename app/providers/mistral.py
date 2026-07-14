"""
Implémentation du fournisseur LLM via le SDK officiel Mistral AI.
Fournisseur par défaut en développement (LLM_PROVIDER=mistral).

Référence : 05_guide_switch_provider_mistral_vertex.md §4.
"""

from typing import List

import httpx

from app.core.config import settings
from app.providers.base import LLMProvider


class MistralProvider(LLMProvider):
    """
    Adaptateur Mistral AI implémentant l'interface LLMProvider.

    Modèles utilisés (configurables via .env) :
      - Génération  : MISTRAL_CHAT_MODEL  (défaut : mistral-large-latest)
      - Embeddings  : MISTRAL_EMBED_MODEL (défaut : mistral-embed)

    Utilise httpx en mode synchrone et async pour ne pas bloquer l'event loop.
    """

    def __init__(self) -> None:
        self._api_key = settings.MISTRAL_API_KEY
        self._base_url = "https://api.mistral.ai/v1"
        self._chat_model: str = settings.MISTRAL_CHAT_MODEL
        self._embed_model: str = settings.MISTRAL_EMBED_MODEL

    def _chat_payload(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> dict:
        """Construit le payload pour l'API de complétion de chat."""
        return {
            "model": self._chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    def _embed_payload(self, texts: List[str]) -> dict:
        """Construit le payload pour l'API d'embeddings."""
        return {
            "model": self._embed_model,
            "input": texts,
        }

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # ---------------------------------------------------------------------- #
    # Génération de texte — synchrone
    # ---------------------------------------------------------------------- #
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Appelle l'API de complétion de chat Mistral (synchrone).
        """
        url = f"{self._base_url}/chat/completions"
        payload = self._chat_payload(system_prompt, user_prompt, temperature, max_tokens)
        with httpx.Client(timeout=90.0) as client:
            response = client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    # ---------------------------------------------------------------------- #
    # Génération de texte — async native (httpx.AsyncClient)
    # ---------------------------------------------------------------------- #
    async def agenerate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Appelle l'API de complétion de chat Mistral de façon asynchrone.
        Utilise httpx.AsyncClient pour ne pas bloquer l'event loop FastAPI/LangGraph.
        """
        url = f"{self._base_url}/chat/completions"
        payload = self._chat_payload(system_prompt, user_prompt, temperature, max_tokens)
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    # ---------------------------------------------------------------------- #
    # Génération d'embeddings — synchrone
    # ---------------------------------------------------------------------- #
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Génère les vecteurs d'embedding (synchrone).
        Utilisé par SwitchableEmbeddingFunction pour ChromaDB.

        Note : mistral-embed est un modèle généraliste ; les performances sur le
        malagasy sont moindres que text-multilingual-embedding-002 de Vertex AI
        (cf. 05_guide_switch_provider_mistral_vertex.md §9).
        """
        url = f"{self._base_url}/embeddings"
        payload = self._embed_payload(texts)
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    # ---------------------------------------------------------------------- #
    # Génération d'embeddings — async native
    # ---------------------------------------------------------------------- #
    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """
        Génère les vecteurs d'embedding de façon asynchrone.
        """
        url = f"{self._base_url}/embeddings"
        payload = self._embed_payload(texts)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=self._headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
