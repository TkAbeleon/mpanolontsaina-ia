"""
Script de test et d'alimentation des collections ChromaDB.
Vérifie l'état des collections et ajoute des données de test si vides.
"""
import os
import sys

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/tsiky-ny-antsa/Project/AI-Orchestration-API/pandemx-286431ffde07.json"

# Ajoute le répertoire racine au PYTHONPATH
sys.path.insert(0, "/home/tsiky-ny-antsa/Project/AI-Orchestration-API")

from dotenv import load_dotenv
load_dotenv()

from app.rag.chroma_client import COLLECTIONS, get_collection_info, add_documents_to_collection


def check_and_seed_collections():
    print("=== ÉTAT DES COLLECTIONS CHROMADB ===\n")
    for domain, collection_name in COLLECTIONS.items():
        info = get_collection_info(collection_name)
        print(f"[{domain}] Collection '{collection_name}': {info['count']} documents — {info['status']}")

    print("\n=== ALIMENTATION DES COLLECTIONS VIDES ===\n")

    # --- Données de test : Droit du travail ---
    droit_travail_docs = [
        """Article 49 du Code du travail malgache : En cas de licenciement, le salarié a droit à un préavis dont la durée est fixée comme suit :
- Cadres et agents de maîtrise : 3 mois
- Employés et ouvriers qualifiés ayant plus de 5 ans d'ancienneté : 1 mois
- Employés et ouvriers qualifiés ayant moins de 5 ans d'ancienneté : 15 jours
- Manœuvres : 8 jours
Le préavis peut être remplacé par une indemnité compensatrice équivalente.""",

        """Article 50 du Code du travail malgache : L'indemnité de licenciement est due au salarié licencié ayant au moins 12 mois d'ancienneté.
Elle est calculée sur la base de la durée du service et du salaire moyen des 12 derniers mois.
Pour chaque année d'ancienneté, le salarié a droit à 1/12 du salaire mensuel moyen.""",

        """Article 90 du Code du travail malgache : Le salaire minimum national (SMIG) est fixé par décret.
Le paiement du salaire doit être effectué deux fois par mois si le salarié le demande.
Tout retard de paiement expose l'employeur à des pénalités.""",

        """Article 81 du Code du travail malgache : Les congés annuels payés sont de 2,5 jours ouvrables par mois de travail effectif,
soit 30 jours ouvrables (5 semaines) par an pour un salarié ayant un an d'ancienneté.
Le salarié a droit à des congés supplémentaires selon son ancienneté.""",

        """Loi n° 2003-044 du 28 juillet 2004 portant Code du travail malgache :
Article 1 : Les dispositions du présent code s'appliquent aux relations de travail entre employeurs et travailleurs exerçant leur activité professionnelle sur le territoire de Madagascar.
Article 5 : Sont considérés comme travailleurs au sens du présent code, toutes personnes qui s'engagent à mettre leur activité professionnelle contre rémunération.""",
    ]

    result = add_documents_to_collection(
        collection_name="droit_travail_mg",
        documents=droit_travail_docs,
        metadatas=[
            {"code": "Code du travail", "article": "Art. 49", "source": "Loi 2003-044"},
            {"code": "Code du travail", "article": "Art. 50", "source": "Loi 2003-044"},
            {"code": "Code du travail", "article": "Art. 90", "source": "Loi 2003-044"},
            {"code": "Code du travail", "article": "Art. 81", "source": "Loi 2003-044"},
            {"code": "Code du travail", "article": "Art. 1, 5", "source": "Loi 2003-044"},
        ],
        ids=["ct_art49", "ct_art50", "ct_art90", "ct_art81", "ct_art1_5"],
    )
    print(f"✓ droit_travail_mg : {result} documents au total")

    # --- Données de test : Fiscalité ---
    fiscalite_docs = [
        """Code général des impôts malgaches - Taxe sur la Valeur Ajoutée (TVA) :
Le taux normal de TVA à Madagascar est de 20%.
Les exportations sont exonérées de TVA.
Les produits alimentaires de base et les médicaments essentiels bénéficient d'un taux réduit ou d'une exonération.""",

        """Impôt sur les Revenus (IR) à Madagascar :
Les personnes physiques sont soumises à l'IR sur leurs revenus mondiaux si elles sont résidentes fiscales à Madagascar.
Le taux d'imposition varie de 5% à 20% selon les tranches de revenus.
Les entreprises sont soumises à l'Impôt sur les Revenus des Sociétés (IRS) au taux de 20%.""",
    ]

    result = add_documents_to_collection(
        collection_name="fiscalite_mg",
        documents=fiscalite_docs,
        metadatas=[
            {"code": "CGI", "article": "TVA", "source": "Code Général des Impôts"},
            {"code": "CGI", "article": "IR", "source": "Code Général des Impôts"},
        ],
        ids=["cgi_tva", "cgi_ir"],
    )
    print(f"✓ fiscalite_mg : {result} documents au total")

    # --- Données de test : Droit des affaires ---
    droit_affaires_docs = [
        """OHADA à Madagascar - Acte uniforme sur les sociétés commerciales (AUSC) :
Madagascar a adhéré à l'OHADA (Organisation pour l'Harmonisation en Afrique du Droit des Affaires).
Les formes de sociétés reconnues sont : SA, SARL, SNC, SCS.
Le capital minimum pour une SARL est de 200 000 Ariary.
La SA requiert un capital minimum de 10 000 000 Ariary.""",

        """Création d'entreprise à Madagascar - Guichet Unique :
Le Guichet Unique de Création d'Entreprises (GUCE) permet d'effectuer les formalités en un seul endroit.
Délai de création : 3 jours ouvrables pour les petites entreprises.
Documents requis : statuts, pièce d'identité des associés, adresse du siège social.""",
    ]

    result = add_documents_to_collection(
        collection_name="droit_affaires_mg",
        documents=droit_affaires_docs,
        metadatas=[
            {"code": "OHADA", "article": "AUSC", "source": "Acte Uniforme OHADA"},
            {"code": "GUCE", "article": "Création", "source": "Loi sur le GUCE"},
        ],
        ids=["ohada_ausc", "guce_creation"],
    )
    print(f"✓ droit_affaires_mg : {result} documents au total")

    print("\n=== VÉRIFICATION FINALE ===\n")
    for domain, collection_name in COLLECTIONS.items():
        info = get_collection_info(collection_name)
        status_icon = "✓" if info['count'] > 0 else "⚠"
        print(f"{status_icon} [{domain}] '{collection_name}': {info['count']} documents")


if __name__ == "__main__":
    check_and_seed_collections()
