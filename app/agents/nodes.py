"""
Nœuds du graphe LangGraph : détection de langue, superviseur, agents spécialisés, synthèse.
Références :
  - 03_contrats_api_chat.md §7
  - 04_guide_implementation_vertex_ai.md §3
  - 05_guide_switch_provider_mistral_vertex.md §7
"""
from typing import Any, List, Optional, TypedDict

from app.providers.factory import get_llm_provider
from app.rag.chroma_client import COLLECTIONS, query_collection


# =============================================================================
# Définition de l'état du graphe
# =============================================================================
class AgentState(TypedDict):
    """État partagé entre tous les nœuds du graphe LangGraph."""
    question: str
    history: List[dict]
    user_id: Optional[str]
    language: Optional[str]  # "mg" | "fr" | "en"
    domain: Optional[str]  # "droit_travail" | "fiscalite" | "droit_affaires" | None
    retrieved_context: Optional[List[dict]]
    final_answer: Optional[str]
    agent_source: Optional[str]


# =============================================================================
# Constantes
# =============================================================================
LANGUAGE_LABELS = {
    "mg": "malagasy (fiteny malagasy ofisialy)",
    "fr": "français",
    "en": "anglais",
}

DOMAINS = {
    "droit_travail": "droit du travail malgache",
    "fiscalite": "droit fiscal malgache",
    "droit_affaires": "droit des affaires malgache",
}


# =============================================================================
# Nœud 1 : Détection de langue
# =============================================================================
def language_detection_node(state: AgentState) -> AgentState:
    """
    Détecte la langue de la question si elle n'est pas déjà fournie.
    Si la langue est déjà présente dans l'état, ne fait rien.
    """
    if state.get("language") and state["language"] in ("mg", "fr", "en"):
        return state

    provider = get_llm_provider()
    system_prompt = """
    Tu es un détecteur de langue. Analyse le texte suivant et réponds
    UNIQUEMENT par un code parmi : mg, fr, en (aucun autre mot, aucune ponctuation).
    mg = malagasy, fr = français, en = anglais.
    """
    detected = provider.generate(
        system_prompt=system_prompt,
        user_prompt=state["question"],
        temperature=0.0,
        max_tokens=10,
    ).strip().lower()

    # Valeur par défaut si la détection échoue
    if detected not in ("mg", "fr", "en"):
        detected = "fr"

    return {**state, "language": detected}


# =============================================================================
# Nœud 2 : Superviseur (classification du domaine)
# =============================================================================
def supervisor_node(state: AgentState) -> AgentState:
    """
    Classifie la question dans un domaine juridique : droit_travail, fiscalite, droit_affaires, ou None.
    """
    provider = get_llm_provider()
    lang_label = LANGUAGE_LABELS[state["language"]]

    system_prompt = f"""
    Tu es un superviseur d'agents juridiques malgaches.
    Classifie la question de l'utilisateur dans l'un des domaines suivants :
    - droit_travail : questions sur le travail, les contrats, les licenciements, les salaires, etc.
    - fiscalite : questions sur les impôts, les taxes, la TVA, etc.
    - droit_affaires : questions sur les entreprises, les sociétés, les contrats commerciaux, etc.

    Réponds UNIQUEMENT par le nom du domaine (droit_travail, fiscalite, droit_affaires) ou "autre" si aucune catégorie ne correspond.
    Réponds en respectant la langue : {lang_label}.
    """

    domain = provider.generate(
        system_prompt=system_prompt,
        user_prompt=state["question"],
        temperature=0.0,
        max_tokens=20,
    ).strip().lower()

    # Validation du domaine
    if domain not in DOMAINS:
        domain = None

    return {**state, "domain": domain}


# =============================================================================
# Fonction de routage conditionnel (après le superviseur)
# =============================================================================
def route_by_domain(state: AgentState) -> str:
    """
    Détermine quel agent spécialisé appeler en fonction du domaine.
    Retourne le nom du nœud cible.
    """
    domain = state.get("domain")
    if domain == "droit_travail":
        return "droit_travail_agent"
    elif domain == "fiscalite":
        return "fiscalite_agent"
    elif domain == "droit_affaires":
        return "droit_affaires_agent"
    else:
        # Si pas de domaine spécifique, on va directement à la synthèse
        return "synthesis"


# =============================================================================
# Nœud 3 : Récupération (RAG)
# =============================================================================
def retrieval_node(state: AgentState) -> AgentState:
    """
    Récupère les documents juridiques pertinents depuis ChromaDB en fonction du domaine.
    """
    domain = state.get("domain")
    if not domain or domain not in COLLECTIONS:
        return {**state, "retrieved_context": []}

    collection_name = COLLECTIONS[domain]
    results = query_collection(
        collection_name=collection_name,
        query_texts=[state["question"]],
        n_results=5,
    )

    # Transforme les résultats en contexte structuré
    context = []
    for i, doc in enumerate(results.get("documents", [[]])[0]):
        metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}
        context.append({
            "content": doc,
            "metadata": metadata,
        })

    return {**state, "retrieved_context": context}


# =============================================================================
# Nœud 4 : Agent spécialisé - Droit du travail
# =============================================================================
def droit_travail_node(state: AgentState) -> AgentState:
    """Agent spécialisé en droit du travail malgache."""
    return _specialized_agent_node(
        state=state,
        domain="droit_travail",
        agent_name="droit_travail_agent",
    )


# =============================================================================
# Nœud 5 : Agent spécialisé - Fiscalité
# =============================================================================
def fiscalite_node(state: AgentState) -> AgentState:
    """Agent spécialisé en droit fiscal malgache."""
    return _specialized_agent_node(
        state=state,
        domain="fiscalite",
        agent_name="fiscalite_agent",
    )


# =============================================================================
# Nœud 6 : Agent spécialisé - Droit des affaires
# =============================================================================
def droit_affaires_node(state: AgentState) -> AgentState:
    """Agent spécialisé en droit des affaires malgache."""
    return _specialized_agent_node(
        state=state,
        domain="droit_affaires",
        agent_name="droit_affaires_agent",
    )


# =============================================================================
# Fonction utilitaire pour les agents spécialisés
# =============================================================================
def _specialized_agent_node(state: AgentState, domain: str, agent_name: str) -> AgentState:
    """
    Fonction générique pour les agents spécialisés.
    Génère une réponse en utilisant le contexte RAG et la langue cible.
    """
    provider = get_llm_provider()
    lang = state["language"]
    lang_label = LANGUAGE_LABELS[lang]
    domain_label = DOMAINS.get(domain, "droit général")

    # Construit le contexte depuis les documents récupérés
    context_str = ""
    if state.get("retrieved_context"):
        context_parts = []
        for ctx in state["retrieved_context"]:
            ctx_content = ctx.get("content", "")
            ctx_meta = ctx.get("metadata", {})
            if ctx_meta:
                code = ctx_meta.get("code", "")
                article = ctx_meta.get("article", "")
                if code or article:
                    context_parts.append(f"[{code} - Article {article}]\n{ctx_content}")
                else:
                    context_parts.append(ctx_content)
            else:
                context_parts.append(ctx_content)
        context_str = "\n\n".join(context_parts)

    system_prompt = f"""
    Tu es un expert juridique spécialisé en {domain_label}.
    Réponds IMPÉRATIVEMENT en {lang_label}, même si les extraits de loi fournis en contexte sont rédigés en français.
    
    Règles :
    1. Cite précisément les articles de loi utilisés (si disponibles dans le contexte)
    2. Ne donne jamais de conseil hors du cadre légal malgache
    3. Si tu n'as pas assez d'informations, dis-le clairement
    4. Sois clair, précis et structuré dans tes réponses
    
    Contexte juridique :
    {context_str if context_str else "Aucun contexte spécifique disponible."}
    """

    answer = provider.generate(
        system_prompt=system_prompt,
        user_prompt=state["question"],
        temperature=0.2,
        max_tokens=1024,
    )

    return {
        **state,
        "final_answer": answer,
        "agent_source": agent_name,
    }


# =============================================================================
# Nœud 7 : Synthèse
# =============================================================================
def synthesis_node(state: AgentState) -> AgentState:
    """
    Synthétise la réponse finale. Si un agent spécialisé a déjà répondu,
    on retourne directement sa réponse. Sinon, on génère une réponse générique.
    """
    # Si on a déjà une réponse, on la garde
    if state.get("final_answer"):
        return state

    # Sinon, réponse générique
    provider = get_llm_provider()
    lang = state["language"]
    lang_label = LANGUAGE_LABELS[lang]

    system_prompt = f"""
    Tu es un assistant juridique malgache.
    Réponds en {lang_label} en indiquant que cette question concerne un domaine juridique non spécifique
    ou que tu ne peux pas répondre avec certitude sans plus de précisions.
    Invite l'utilisateur à préciser sa question.
    """

    answer = provider.generate(
        system_prompt=system_prompt,
        user_prompt=state["question"],
        temperature=0.3,
        max_tokens=512,
    )

    return {
        **state,
        "final_answer": answer,
        "agent_source": "general_agent",
    }
