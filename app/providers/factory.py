"""
Factory de fournisseur LLM — sélectionne l'implémentation concrète
en fonction de la variable d'environnement LLM_PROVIDER.

Référence : 05_guide_switch_provider_mistral_vertex.md §6.

Usage :
    from app.providers.factory import get_llm_provider
    provider = get_llm_provider()
    answer = provider.generate(system_prompt=..., user_prompt=...)
"""

from functools import lru_cache

from app.providers.base import LLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """
    Point d'entrée UNIQUE utilisé par tout le reste de l'application
    (nœuds LangGraph, embedding ChromaDB, etc.).

    Le fournisseur réel est déterminé par la variable LLM_PROVIDER dans .env :
      - "mistral" (défaut) : MistralProvider  — disponible immédiatement en dev
      - "vertex"           : VertexAIProvider  — à activer dès validation de l'accès GCP

    lru_cache(maxsize=1) garantit l'instanciation unique du client (singleton),
    ce qui est important pour la réutilisation des connexions HTTP et évite
    de relire les credentials à chaque appel.

    L'import du SDK concret est effectué à l'intérieur de la fonction (import
    différé) afin qu'un seul des deux SDK ait besoin d'être installé/configuré
    selon l'environnement.
    """
    from app.core.config import settings

    provider_name: str = settings.LLM_PROVIDER.lower()

    if provider_name == "mistral":
        from app.providers.mistral import MistralProvider
        return MistralProvider()

    if provider_name == "vertex":
        from app.providers.vertex import VertexAIProvider
        return VertexAIProvider()

    raise ValueError(
        f"LLM_PROVIDER='{provider_name}' inconnu. "
        "Valeurs acceptées : 'mistral', 'vertex'."
    )
