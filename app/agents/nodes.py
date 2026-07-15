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
    Détecte la langue de la question via le LLM.
    On vérifie toujours avec le LLM même si un paramètre language est fourni,
    car l'utilisateur peut envoyer une mauvaise valeur (ex: language='fr' mais écrit en malgache).
    """
    provider = get_llm_provider()
    system_prompt = (
        "You are a language detector. Analyze the following text and respond "
        "ONLY with one of these codes: mg, fr, en. No other words, no punctuation. "
        "mg = Malagasy, fr = French, en = English."
    )

    try:
        raw_lang = await provider.agenerate(
            system_prompt=system_prompt,
            user_prompt=state["question"],
            temperature=0.0,
            max_tokens=10,
        )
        raw_lang = raw_lang.strip().lower()
        
        if "mg" in raw_lang or "malagasy" in raw_lang:
            detected = "mg"
        elif "en" in raw_lang or "english" in raw_lang:
            detected = "en"
        elif "fr" in raw_lang or "french" in raw_lang:
            detected = "fr"
        else:
            detected = state.get("language") or "fr"
            
    except Exception as exc:
        logger.warning("Échec détection de langue : %s — repli sur le paramètre fourni", exc)
        detected = state.get("language") or "fr"

    logger.info("Langue détectée : %s (paramètre original: %s, brut: '%s')", detected, state.get("language"), raw_lang if 'raw_lang' in locals() else 'N/A')
    return {**state, "language": detected}


# =============================================================================
# Nœud 2 : Superviseur (classification du domaine)
# =============================================================================
async def supervisor_node(state: AgentState) -> AgentState:
    """
    Classifie la question dans un domaine juridique via le LLM.
    Utilise un prompt strict en anglais (langue neutre) pour garantir une réponse
    machine-readable quelle que soit la langue de l'utilisateur.
    """
    provider = get_llm_provider()

    # Prompt en anglais pour obtenir une réponse fiable indépendamment de la langue
    system_prompt = (
        "You are a legal domain classifier for Malagasy law.\n"
        "Classify the user's question into exactly ONE of these domains:\n"
        "  - droit_travail : labor law, employment contracts, dismissal, salary, notice period, leave, unions\n"
        "  - fiscalite : taxes, VAT, tax declarations, tax exemptions\n"
        "  - droit_affaires : business law, companies, commercial contracts, OHADA, company creation\n\n"
        "IMPORTANT: Respond with ONLY the domain name exactly as written above "
        "(droit_travail, fiscalite, or droit_affaires). "
        "If none match, respond with ONLY the word: autre\n"
        "Do NOT write anything else. No explanation, no punctuation."
    )

    try:
        raw = await provider.agenerate(
            system_prompt=system_prompt,
            user_prompt=state["question"],
            temperature=0.0,
            max_tokens=50,
        )
        raw = raw.strip().lower()
        
        # Heuristique robuste basée sur les mots-clés plutôt qu'une stricte égalité
        if "travail" in raw or "labor" in raw:
            domain = "droit_travail"
        elif "fiscal" in raw or "tax" in raw:
            domain = "fiscalite"
        elif "affaire" in raw or "business" in raw or "ohada" in raw:
            domain = "droit_affaires"
        else:
            domain = None
            
    except Exception as exc:
        logger.warning("Échec classification du domaine : %s", exc)
        domain = None

    if domain not in DOMAINS:
        domain = None

    logger.info("Domaine classifié : %s (réponse brute LLM: '%s')", domain, raw if 'raw' in dir() else 'N/A')
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

    # Construit le contexte depuis les documents récupérés (RAG)
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
            source = ctx_meta.get("source", "")
            header_parts = [p for p in [code, article, source] if p]
            header = f"[{' — '.join(header_parts)}]\n" if header_parts else ""
            context_parts.append(f"{header}{ctx_content}")
        context_str = "\n\n---\n\n".join(context_parts)
        logger.info("Agent '%s' utilise %d extrait(s) RAG depuis ChromaDB.", agent_name, len(context_parts))
    else:
        logger.info("Agent '%s' : aucun extrait RAG disponible, réponse sur connaissances générales.", agent_name)

    # Construit l'historique de conversation pour le contexte
    history = state.get("history") or []
    history_str = ""
    if history:
        history_lines = []
        for msg in history[-6:]:  # Limite aux 6 derniers échanges
            role = "Utilisateur" if msg.get("role") == "user" else "Assistant"
            history_lines.append(f"{role}: {msg.get('content', '')[:300]}")
        history_str = "\n".join(history_lines)

    no_context_msg = "Aucun extrait de loi spécifique disponible dans la base de données. Réponds d'après tes connaissances générales du droit malgache."
    system_prompt = (
        f"Tu es un expert juridique spécialisé en {domain_label}.\n"
        f"Réponds IMPÉRATIVEMENT en {lang_label}, même si les extraits de loi "
        "fournis en contexte sont rédigés en français.\n\n"
        "Règles :\n"
        "1. Cite précisément les articles de loi si disponibles dans le contexte RAG\n"
        "2. Ne donne jamais de conseil hors du cadre légal malgache\n"
        "3. Si tu n'as pas assez d'informations, dis-le clairement\n"
        "4. Sois clair, précis et structuré\n"
        "5. Tiens compte du contexte de la conversation précédente si disponible\n\n"
        + (f"Historique récent :\n{history_str}\n\n" if history_str else "")
        + f"Extraits juridiques (ChromaDB RAG) :\n{context_str if context_str else no_context_msg}"
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
