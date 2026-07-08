#!/usr/bin/env python3
"""
Script de test pour vérifier la connexion à Vertex AI et le LLMProvider.
"""
import sys
import os

# Ajouter le dossier racine au path Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.providers.factory import get_llm_provider

def test_vertex_connection():
    """Teste la connexion à Vertex AI et la génération de texte."""
    print("=" * 60)
    print("Test de connexion à Vertex AI")
    print("=" * 60)

    try:
        # Récupérer le provider Vertex
        provider = get_llm_provider()
        print(f"✅ Provider chargé : {type(provider).__name__}")

        # Tester la génération de texte
        print("\nTest de génération de texte...")
        system_prompt = "Tu es un assistant juridique malgache. Réponds en français."
        user_prompt = "Bonjour, peux-tu me dire ce qu'est le droit du travail malgache en 2 phrases ?"

        response = provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=200
        )

        print(f"✅ Réponse reçue :\n{response}")

        # Tester les embeddings
        print("\nTest de génération d'embeddings...")
        texts = ["Bonjour", "Hello", "Manao ahoana"]
        embeddings = provider.embed(texts)
        print(f"✅ Embeddings générés : {len(embeddings)} vecteurs, dimension {len(embeddings[0])}")

        print("\n" + "=" * 60)
        print("🎉 Tous les tests ont réussi ! Vertex AI fonctionne !")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Erreur : {type(e).__name__} - {e}")
        import traceback
        print("\n" + traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    test_vertex_connection()
