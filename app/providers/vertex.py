"""
Implémentation du fournisseur LLM via le SDK Google Vertex AI (google-genai).
Fournisseur de production activé par LLM_PROVIDER=vertex.

Référence : 05_guide_switch_provider_mistral_vertex.md §5
            04_guide_implementation_vertex_ai.md §2
"""

import asyncio
from typing import List

from app.core.config import settings
from app.providers.base import LLMProvider


class VertexAIProvider(LLMProvider):
    """
    Adaptateur Vertex AI / Gemini implémentant l'interface LLMProvider.

    Pré-requis :
      - GCP_PROJECT_ID et GCP_LOCATION définis dans .env
      - Authentification : GOOGLE_APPLICATION_CREDENTIALS (chemin vers le JSON
        du compte de service) ou gcloud auth application-default login en local.

    Modèles utilisés (configurables via .env) :
      - Génération  : GEMINI_MODEL           (défaut : gemini-3-flash)
      - Embeddings  : GEMINI_EMBEDDING_MODEL  (défaut : text-multilingual-embedding-002)
    """

    def __init__(self) -> None:
        # Import différé : le SDK google-genai n'est requis qu'en mode vertex.
        from google import genai  # type: ignore[import]

        self._client = genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION,
        )
        self._chat_model: str = settings.GEMINI_MODEL
        self._embed_model: str = settings.GEMINI_EMBEDDING_MODEL

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
        Appelle l'API Gemini sur Vertex AI avec le prompt système fusionné
        au prompt utilisateur (format attendu par le SDK google-genai).
        """
        response = self._client.models.generate_content(
            model=self._chat_model,
            contents=[
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ],
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        # Le SDK peut renvoyer le texte dans `response.text` ou dans
        # `response.candidates[...].content.parts[...]`. Gérer les deux cas.
        text = getattr(response, "text", None)
        if text:
            return text

        candidates = getattr(response, "candidates", None) or []
        parts_texts = []
        for cand in candidates:
            try:
                parts = getattr(cand.content, "parts", None)
                if parts:
                    for p in parts:
                        t = getattr(p, "text", None)
                        if t:
                            parts_texts.append(t)
            except Exception:
                continue

        return "\n".join(parts_texts) if parts_texts else ""

    # ---------------------------------------------------------------------- #
    # Génération de texte — async (via asyncio.to_thread)
    # Le SDK google-genai n'expose pas encore de client async natif stable ;
    # on délègue au thread pool pour ne pas bloquer l'event loop.
    # ---------------------------------------------------------------------- #
    async def agenerate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Version async de generate() via asyncio.to_thread."""
        return await asyncio.to_thread(
            self.generate, system_prompt, user_prompt, temperature, max_tokens
        )

    # ---------------------------------------------------------------------- #
    # Génération d'embeddings — synchrone (RAG / ChromaDB multilingue)
    # ---------------------------------------------------------------------- #
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Génère les vecteurs d'embedding via text-multilingual-embedding-002,
        optimisé pour la recherche sémantique multilingue (mg / fr / en).

        ⚠️ Les espaces vectoriels Mistral et Vertex AI ne sont pas compatibles.
        Si les collections ChromaDB ont été indexées avec mistral-embed,
        il faut les ré-indexer entièrement après bascule vers vertex.
        (cf. 05_guide_switch_provider_mistral_vertex.md §8)
        """
        result = self._client.models.embed_content(
            model=self._embed_model,
            contents=texts,
        )
        return [e.values for e in result.embeddings]

    # ---------------------------------------------------------------------- #
    # Génération d'embeddings — async (via asyncio.to_thread)
    # ---------------------------------------------------------------------- #
    async def aembed(self, texts: List[str]) -> List[List[float]]:
        """Version async de embed() via asyncio.to_thread."""
        return await asyncio.to_thread(self.embed, texts)
