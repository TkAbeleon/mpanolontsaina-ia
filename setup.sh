#!/bin/bash

# Script d'installation pour Assistant Juridique Malgache
# Pour Linux et macOS

echo "=========================================="
echo "Assistant Juridique Malgache - Installation"
echo "=========================================="

# Vérifie si Python 3.11+ est disponible
echo -e "\n[1/4] Vérification de Python..."
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v $cmd >/dev/null 2>&1; then
        version=$($cmd --version | awk '{print $2}')
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_CMD=$cmd
            echo "✓ Python $version trouvé"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "\n❌ Erreur : Python 3.11 ou supérieur est requis !"
    echo "   Téléchargez-le depuis https://www.python.org/"
    exit 1
fi

# Crée l'environnement virtuel
echo -e "\n[2/4] Création de l'environnement virtuel..."
if [ ! -d ".venv" ]; then
    if ! $PYTHON_CMD -m venv .venv 2>/tmp/venv-error.log; then
        echo "⚠️ Le module python3-venv est manquant ou la création du venv a échoué."
        if command -v apt-get >/dev/null 2>&1; then
            echo "   Tentative d'installation de python3-venv via apt-get..."
            sudo apt-get update && sudo apt-get install -y python3-venv
            $PYTHON_CMD -m venv .venv
        else
            echo "❌ Impossible d'installer python3-venv automatiquement sur ce système."
            cat /tmp/venv-error.log >&2
            exit 1
        fi
    fi
    echo "✓ Environnement virtuel .venv créé"
else
    echo "ℹ Environnement virtuel .venv existe déjà"
fi

# Active l'environnement virtuel et installe les dépendances
echo -e "\n[3/4] Installation des dépendances..."
if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ ! -f ".venv/bin/activate" ]; then
        echo "❌ Le virtualenv n'a pas été créé correctement."
        exit 1
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "❌ OS non supporté pour ce script"
    exit 1
fi

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo "✓ Dépendances installées"

# Copie le fichier .env.example vers .env si nécessaire
echo -e "\n[4/4] Configuration de l'environnement..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✓ Fichier .env créé depuis .env.example"
    echo -e "\n⚠️ IMPORTANT : Modifiez le fichier .env avec vos vraies valeurs !"
    echo "   Variables à configurer :"
    echo "   - DATABASE_URL"
    echo "   - JWT_SECRET_KEY"
    echo "   - LLM_PROVIDER"
    echo "   - MISTRAL_API_KEY ou GCP_PROJECT_ID"
else
    echo "ℹ Fichier .env existe déjà"
fi

# Affiche les instructions finales
echo -e "\n=========================================="
echo "✅ Installation terminée !"
echo "=========================================="
echo -e "\nPour lancer le serveur :"
echo "   source .venv/bin/activate  # Active l'environnement"
echo "   uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"
echo -e "\nDocumentation API disponible sur :"
echo "   http://localhost:8080/api/docs"
echo "   http://localhost:8080/api/redoc"
echo -e "\nHealth check : http://localhost:8080/health"
echo "=========================================="
