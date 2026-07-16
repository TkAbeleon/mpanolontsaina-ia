#!/usr/bin/env python3
"""Test du pipeline LangGraph complet avec logging détaillé."""
import asyncio
import logging
import os
import sys

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
)

# Désactiver les logs verbose d'autres libs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.DEBUG)

# Configuration
os.environ["CHAT_BACKEND"] = "local"
os.environ["LLM_PROVIDER"] = "vertex"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/tsiky-ny-antsa/Project/AI-Orchestration-API/pandemx-286431ffde07.json"
os.environ["GCP_PROJECT_ID"] = "pandemx"
os.environ["GCP_LOCATION"] = "europe-west1"
os.environ["GEMINI_MODEL"] = "publishers/google/models/gemini-2.5-flash"
os.environ["DATABASE_URL"] = "postgresql+psycopg2://jury_admin:vanellaAdmin123@136.119.107.131:5432/jury_db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["CHROMA_PERSIST_DIR"] = "./chroma_data"

logger = logging.getLogger(__name__)

print("\n" + "=" * 80)
print("TEST COMPLET DU PIPELINE LANGGRAPH AVEC VERTEX AI")
print("=" * 80)

try:
    logger.info("📥 Chargement du graphe compilé...")
    from app.agents.graph import compiled_graph
    from app.agents.nodes import AgentState
    logger.info("✓ Graphe chargé")
    
except Exception as e:
    logger.exception("❌ Erreur lors du chargement du graphe")
    sys.exit(1)

async def test_graph():
    """Teste le graphe complet."""
    logger.info("🚀 Exécution du graphe avec une question test...")
    
    initial_state: AgentState = {
        "question": "Quelle est la durée minimale de congés payés à Madagascar?",
        "history": [],
        "user_id": None,
        "language": "fr",
        "domain": None,
        "retrieved_context": None,
        "final_answer": None,
        "agent_source": None,
    }
    
    try:
        logger.info("📨 Envoi au graphe...")
        final_state = await compiled_graph.ainvoke(initial_state)
        logger.info("✓ Graphe exécuté avec succès")
        
        logger.info(f"   Answer: {final_state.get('final_answer', 'N/A')[:100]}...")
        logger.info(f"   Agent: {final_state.get('agent_source', 'N/A')}")
        logger.info(f"   Language: {final_state.get('language', 'N/A')}")
        
        return final_state
    except Exception as e:
        logger.exception("❌ Erreur lors de l'exécution du graphe")
        raise

try:
    result = asyncio.run(test_graph())
    print("\n" + "=" * 80)
    print("✓✓✓ TEST RÉUSSI !")
    print("=" * 80)
except Exception as e:
    print("\n" + "=" * 80)
    print(f"❌ TEST ÉCHOUÉ: {e}")
    print("=" * 80)
    sys.exit(1)
