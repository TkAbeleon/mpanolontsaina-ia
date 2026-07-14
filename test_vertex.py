import os
from google import genai
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Forcer l'utilisation du bon fichier de credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/tsiky-ny-antsa/Project/AI-Orchestration-API/pandemx-286431ffde07.json"

def test_vertex():
    project_id = os.getenv("GCP_PROJECT_ID", "pandemx")
    location = os.getenv("GCP_LOCATION", "europe-west1")
    model_name = os.getenv("GEMINI_MODEL", "publishers/google/models/gemini-2.5-flash")

    print(f"=== TEST VERTEX AI ===")
    print(f"Projet: {project_id}")
    print(f"Location: {location}")
    print(f"Modèle: {model_name}")
    print(f"Fichier credentials: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
    
    try:
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )
        
        response = client.models.generate_content(
            model=model_name,
            contents=["Bonjour, peux-tu dire 'Test réussi' ?"],
        )
        
        print("\n=== SUCCÈS ===")
        if hasattr(response, 'text'):
            print(f"Réponse: {response.text}")
        else:
            print(f"Réponse brute: {response}")
            
    except Exception as e:
        print("\n=== ERREUR ===")
        print(f"Type: {type(e).__name__}")
        print(f"Détails: {str(e)}")

if __name__ == "__main__":
    test_vertex()
