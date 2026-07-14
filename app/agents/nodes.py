"""
Nœuds du graphe LangGraph : détection de langue, superviseur, agents spécialisés, synthèse.
Références :
  - 03_contrats_api_chat.md §7
  - 04_guide_implementation_vertex_ai.md §3
  - 05_guide_switch_provider_mistral_vertex.md §7
"""
import logging
from typing import Any, List, Optional, TypedDict

from app.providers.factory import get_llm_provider
from app.rag.chroma_client import COLLECTIONS, query_collection

logger = logging.getLogger(__name__)


# =============================================================================
# Définition de l'état du graphe
# =============================================================================
class AgentState(TypedDict):
    """État partagé entre tous les nœuds du graphe LangGraph."""
    question: str
    history: List[dict]
    user_id: Optional[str]
    language: Optional[str]          # "mg" | "fr" | "en"
    domain: Optional[str]            # "droit_travail" | "fiscalite" | "droit_affaires" | None
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
async def language_detection_node(state: AgentState) -> AgentState:
    """
    Détecte la langue de la question si elle n'est pas déjà fournie.
    Utilise le LLM via agenerate() pour ne pas bloquer l'event loop.
    """
    if state.get("language") and state["language"] in ("mg", "fr", "en"):
        return state

    provider = get_llm_provider()
    system_prompt = (
        "Tu es un détecteur de langue. Analyse le texte suivant et réponds "
        "UNIQUEMENT par un code parmi : mg, fr, en (aucun autre mot, aucune ponctuation). "
        "mg = malagasy, fr = français, en = anglais."
    )

    try:
        detected = await provider.agenerate(
            system_prompt=system_prompt,
            user_prompt=state["question"],
            temperature=0.0,
            max_tokens=10,
        )
        detected = detected.strip().lower()
    except Exception as exc:
        logger.warning("Échec détection de langue : %s — repli sur 'fr'", exc)
        detected = "fr"

    if detected not in ("mg", "fr", "en"):
        detected = "fr"

    logger.debug("Langue détectée : %s", detected)
    return {**state, "language": detected}


# =============================================================================
# Nœud 2 : Superviseur (classification du domaine)
# =============================================================================
async def supervisor_node(state: AgentState) -> AgentState:
    """
    Classifie la question dans un domaine juridique via le LLM.
    Utilise agenerate() pour ne pas bloquer l'event loop.
    """
    provider = get_llm_provider()
    lang = state.get("language", "fr")
    lang_label = LANGUAGE_LABELS.get(lang, "français")

    system_prompt = (
        "Tu es un superviseur d'agents juridiques malgaches.\n"
        "Classifie la question de l'utilisateur dans l'un des domaines suivants :\n"
        "- droit_travail : travail, contrats de travail, licenciements, salaires, préavis, congés, syndicats\n"
        "- fiscalite : impôts, taxes, TVA, déclarations fiscales, exonérations\n"
        "- droit_affaires : entreprises, sociétés, contrats commerciaux, OHADA, création d'entreprise\n\n"
        "Réponds UNIQUEMENT par le nom du domaine exact "
        "(droit_travail, fiscalite, droit_affaires) ou 'autre' si aucune catégorie ne correspond.\n"
        f"Réponds toujours en {lang_label}."
    )

    try:
        domain = await provider.agenerate(
            system_prompt=system_prompt,
            user_prompt=state["question"],
            temperature=0.0,
            max_tokens=20,
        )
        domain = domain.strip().lower()
        # Nettoyer les réponses potentiellement verboses
        for key in DOMAINS:
            if key in domain:
                domain = key
                break
        else:
            domain = None
    except Exception as exc:
        logger.warning("Échec classification du domaine : %s", exc)
        domain = None

    if domain not in DOMAINS:
        domain = None

    logger.debug("Domaine classifié : %s", domain)
    return {**state, "domain": domain}


# =============================================================================
# Fonction de routage conditionnel (après le retrieval)
# =============================================================================
def route_by_domain(state: AgentState) -> str:
    """
    Détermine quel agent spécialisé appeler en fonction du domaine.
    Retourne le nom du nœud cible.
    """
    domain = state.get("domain")
    if domain == "droit_travail":
        return "droit_travail"
    elif domain == "fiscalite":
        return "fiscalite"
    elif domain == "droit_affaires":
        return "droit_affaires"
    else:
        # Si pas de domaine spécifique, on va directement à la synthèse générale
        return "synthesis"


# =============================================================================
# Nœud 3 : Récupération (RAG ChromaDB)
# =============================================================================
async def retrieval_node(state: AgentState) -> AgentState:
    """
    Récupère les documents juridiques pertinents depuis ChromaDB.
    Robuste aux collections vides ou inexistantes.
    """
    domain = state.get("domain")
    if not domain or domain not in COLLECTIONS:
        logger.debug("Aucun domaine → pas de retrieval ChromaDB.")
        return {**state, "retrieved_context": []}

    collection_name = COLLECTIONS[domain]
    logger.debug("Retrieval dans collection '%s' pour la question : %s", collection_name, state["question"][:80])

    try:
        results = query_collection(
            collection_name=collection_name,
            query_texts=[state["question"]],
            n_results=5,
        )
    except Exception as exc:
        logger.warning("Échec retrieval ChromaDB (collection=%s) : %s", collection_name, exc)
        return {**state, "retrieved_context": []}

    # Transforme les résultats en contexte structuré
    context = []
    docs = results.get("documents", [[]])[0] if results else []
    metadatas = results.get("metadatas", [[]])[0] if results else []

    for i, doc in enumerate(docs):
        if not doc:
            continue
        metadata = metadatas[i] if i < len(metadatas) else {}
        context.append({
            "content": doc,
            "metadata": metadata or {},
        })

    logger.debug("Retrieval : %d documents récupérés depuis '%s'.", len(context), collection_name)
    return {**state, "retrieved_context": context}


# =============================================================================
# Nœud 4 : Agent spécialisé - Droit du travail
# =============================================================================
async def droit_travail_node(state: AgentState) -> AgentState:
    """Agent spécialisé en droit du travail malgache."""
    return await _specialized_agent_node(
        state=state,
        domain="droit_travail",
        agent_name="droit_travail_agent",
    )


# =============================================================================
# Nœud 5 : Agent spécialisé - Fiscalité
# =============================================================================
async def fiscalite_node(state: AgentState) -> AgentState:
    """Agent spécialisé en droit fiscal malgache."""
    return await _specialized_agent_node(
        state=state,
        domain="fiscalite",
        agent_name="fiscalite_agent",
    )


# =============================================================================
# Nœud 6 : Agent spécialisé - Droit des affaires
# =============================================================================
async def droit_affaires_node(state: AgentState) -> AgentState:
    """Agent spécialisé en droit des affaires malgache."""
    return await _specialized_agent_node(
        state=state,
        domain="droit_affaires",
        agent_name="droit_affaires_agent",
    )


# =============================================================================
# Fonction utilitaire pour les agents spécialisés
# =============================================================================
async def _specialized_agent_node(state: AgentState, domain: str, agent_name: str) -> AgentState:
    """
    Génère une réponse juridique spécialisée en utilisant le contexte RAG et la langue cible.
    Utilise agenerate() pour ne pas bloquer l'event loop.
    """
    provider = get_llm_provider()
    lang = state.get("language", "fr")
    lang_label = LANGUAGE_LABELS.get(lang, "français")
    domain_label = DOMAINS.get(domain, "droit général malgache")

    # Construit le contexte depuis les documents récupérés
    context_str = ""
    retrieved = state.get("retrieved_context") or []
    if retrieved:
        context_parts = []
        for ctx in retrieved:
            ctx_content = ctx.get("content", "").strip()
            if not ctx_content:
                continue
            ctx_meta = ctx.get("metadata", {}) or {}
            code = ctx_meta.get("code", "")
            article = ctx_meta.get("article", "")
            header = f"[{code} — {article}]\n" if (code or article) else ""
            context_parts.append(f"{header}{ctx_content}")
        context_str = "\n\n---\n\n".join(context_parts)

    no_context_msg = "Aucun contexte spécifique disponible. Réponds d'après tes connaissances générales du droit malgache."
    system_prompt = (
        f"Tu es un expert juridique spécialisé en {domain_label}.\n"
        f"Réponds IMPÉRATIVEMENT en {lang_label}, même si les extraits de loi "
        "fournis en contexte sont rédigés en français.\n\n"
        "Règles :\n"
        "1. Cite précisément les articles de loi utilisés (si disponibles dans le contexte)\n"
        "2. Ne donne jamais de conseil hors du cadre légal malgache\n"
        "3. Si tu n'as pas assez d'informations, dis-le clairement\n"
        "4. Sois clair, précis et structuré dans ta réponse\n\n"
        f"Contexte juridique disponible :\n{context_str if context_str else no_context_msg}"
    )

    logger.debug("Agent '%s' génère une réponse en '%s'.", agent_name, lang)
    try:
        answer = await provider.agenerate(
            system_prompt=system_prompt,
            user_prompt=state["question"],
            temperature=0.2,
            max_tokens=1500,
        )
    except Exception as exc:
        logger.error("Échec de la génération LLM (%s) : %s", agent_name, exc)
        answer = "Une erreur est survenue lors de la génération de la réponse."

    return {
        **state,
        "final_answer": answer,
        "agent_source": agent_name,
    }


# =============================================================================
# Nœud 7 : Synthèse (réponse générique si aucun agent spécialisé n'a répondu)
# =============================================================================
async def synthesis_node(state: AgentState) -> AgentState:
    """
    Si un agent spécialisé a déjà répondu, on retourne directement sa réponse.
    Sinon, on génère une réponse générique via le LLM.
    """
    # Si on a déjà une réponse d'un agent spécialisé, on la retourne sans modification.
    if state.get("final_answer"):
        logger.debug("Synthesis : réponse déjà produite par '%s', passthrough.", state.get("agent_source"))
        return state

    # Aucun agent spécialisé n'a répondu → réponse générale
    provider = get_llm_provider()
    lang = state.get("language", "fr")
    lang_label = LANGUAGE_LABELS.get(lang, "français")

    system_prompt = (
        f"Tu es un assistant juridique malgache généraliste.\n"
        f"Réponds en {lang_label}.\n"
        "Si la question ne concerne pas un domaine juridique précis ou si tu ne peux pas y répondre "
        "avec certitude, dis-le clairement et invite l'utilisateur à préciser sa question.\n"
        "Tu peux aussi orienter l'utilisateur vers le bon service ou professionnel juridique."
    )

    try:
        answer = await provider.agenerate(
            system_prompt=system_prompt,
            user_prompt=state["question"],
            temperature=0.3,
            max_tokens=800,
        )
    except Exception as exc:
        logger.error("Échec de la synthèse générale : %s", exc)
        answer = "Je suis désolé, une erreur est survenue. Veuillez réessayer."

    return {
        **state,
        "final_answer": answer,
        "agent_source": "general_agent",
    }
