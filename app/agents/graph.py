"""
Graphe LangGraph compilé (singleton) pour l'assistant juridique multi-agents.
Référence : 03_contrats_api_chat.md §7
"""
import logging

from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    AgentState,
    droit_affaires_node,
    droit_travail_node,
    fiscalite_node,
    language_detection_node,
    retrieval_node,
    route_by_domain,
    supervisor_node,
    synthesis_node,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Construction du graphe
# =============================================================================
def build_graph() -> StateGraph:
    """Construit et compile le graphe LangGraph multi-agents."""
    workflow = StateGraph(AgentState)

    # --- Ajout des nœuds ---
    workflow.add_node("language_detection", language_detection_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("droit_travail_agent", droit_travail_node)
    workflow.add_node("fiscalite_agent", fiscalite_node)
    workflow.add_node("droit_affaires_agent", droit_affaires_node)
    workflow.add_node("synthesis", synthesis_node)

    # --- Point d'entrée ---
    workflow.set_entry_point("language_detection")

    # --- Flux principal ---
    # 1. Détection de langue
    workflow.add_edge("language_detection", "supervisor")

    # 2. Superviseur → Retrieval (toujours, pour charger le contexte avant le bon agent)
    workflow.add_edge("supervisor", "retrieval")

    # 3. Retrieval → Agent spécialisé (ou Synthesis si domaine non identifié)
    workflow.add_conditional_edges(
        "retrieval",
        route_by_domain,
        {
            "droit_travail": "droit_travail_agent",
            "fiscalite": "fiscalite_agent",
            "droit_affaires": "droit_affaires_agent",
            "synthesis": "synthesis",
        },
    )

    # 4. Agents spécialisés → Synthesis
    workflow.add_edge("droit_travail_agent", "synthesis")
    workflow.add_edge("fiscalite_agent", "synthesis")
    workflow.add_edge("droit_affaires_agent", "synthesis")

    # 5. Synthesis → END
    workflow.add_edge("synthesis", END)

    logger.info("Graphe LangGraph compilé avec succès.")
    return workflow.compile()


# =============================================================================
# Singleton : graphe compilé (chargé une seule fois au démarrage de l'app)
# =============================================================================
compiled_graph = build_graph()
