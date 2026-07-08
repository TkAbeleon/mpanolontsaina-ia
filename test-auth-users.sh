#!/bin/bash

# Script de test pour les endpoints Authentification et Utilisateurs
# Base URL: http://localhost:8000

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Test Authentification et Utilisateurs"
echo "=========================================="

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Vérifie que le serveur est en ligne
echo -e "\n${YELLOW}[0/10] Vérification du serveur...${NC}"
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" | grep -q "200"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Le serveur n'est pas en cours d'exécution sur $BASE_URL !${NC}"
    echo "   Lancez-le avec: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi
echo -e "${GREEN}✓ Serveur en ligne${NC}"

# Test 1: Inscription
echo -e "\n${YELLOW}[1/10] Test Inscription...${NC}"
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "test.user@example.mg",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "preferred_language": "fr"
    }')

echo "$REGISTER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REGISTER_RESPONSE"

if echo "$REGISTER_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Inscription réussie${NC}"
else
    if echo "$REGISTER_RESPONSE" | grep -q "EMAIL_ALREADY_EXISTS"; then
        echo -e "${YELLOW}⚠ Utilisateur déjà existant, on continue...${NC}"
    else
        echo -e "${RED}❌ Inscription échouée${NC}"
        exit 1
    fi
fi

# Test 2: Connexion
echo -e "\n${YELLOW}[2/10] Test Connexion...${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "test.user@example.mg",
        "password": "TestPassword123!"
    }')

echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('access_token', ''))
except:
    print('')
")
REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('refresh_token', ''))
except:
    print('')
")

if [ -z "$ACCESS_TOKEN" ]; then
    echo -e "${RED}❌ Connexion échouée (pas de access token)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Connexion réussie${NC}"
echo "  Access Token: ${ACCESS_TOKEN:0:30}..."

# Test 3: Voir son profil
echo -e "\n${YELLOW}[3/10] Test Récupération Profil...${NC}"
PROFILE_RESPONSE=$(curl -s -X GET "$BASE_URL/api/v1/users/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN")

echo "$PROFILE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$PROFILE_RESPONSE"

if echo "$PROFILE_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Profil récupéré avec succès${NC}"
else
    echo -e "${RED}❌ Échec récupération profil${NC}"
fi

# Test 4: Mettre à jour le profil
echo -e "\n${YELLOW}[4/10] Test Mise à jour Profil...${NC}"
UPDATE_RESPONSE=$(curl -s -X PATCH "$BASE_URL/api/v1/users/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "full_name": "Test User Updated"
    }')

echo "$UPDATE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$UPDATE_RESPONSE"

if echo "$UPDATE_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Profil mis à jour avec succès${NC}"
else
    echo -e "${RED}❌ Échec mise à jour profil${NC}"
fi

# Test 5: Rafraîchir le token
echo -e "\n${YELLOW}[5/10] Test Rafraîchissement Token...${NC}"
REFRESH_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")

echo "$REFRESH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REFRESH_RESPONSE"

NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('access_token', ''))
except:
    print('')
")

if [ -z "$NEW_ACCESS_TOKEN" ]; then
    echo -e "${RED}❌ Échec rafraîchissement token${NC}"
else
    ACCESS_TOKEN="$NEW_ACCESS_TOKEN"
    echo -e "${GREEN}✓ Token rafraîchi avec succès${NC}"
fi

# Test 6: Déconnexion
echo -e "\n${YELLOW}[6/10] Test Déconnexion...${NC}"
LOGOUT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/logout" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")

echo "$LOGOUT_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGOUT_RESPONSE"

if echo "$LOGOUT_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Déconnexion réussie${NC}"
else
    echo -e "${RED}❌ Échec déconnexion${NC}"
fi

# Test 7: Reconnexion pour la suppression
echo -e "\n${YELLOW}[7/10] Reconnexion pour suppression...${NC}"
LOGIN2_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "test.user@example.mg",
        "password": "TestPassword123!"
    }')

ACCESS_TOKEN2=$(echo "$LOGIN2_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('access_token', ''))
except:
    print('')
")
REFRESH_TOKEN2=$(echo "$LOGIN2_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('data', {}).get('refresh_token', ''))
except:
    print('')
")

if [ -z "$ACCESS_TOKEN2" ]; then
    echo -e "${RED}❌ Reconnexion échouée${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Reconnexion réussie${NC}"

# Test 8: Suppression du compte
echo -e "\n${YELLOW}[8/10] Test Suppression Compte (anonymisation)...${NC}"
DELETE_RESPONSE=$(curl -s -X DELETE "$BASE_URL/api/v1/users/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN2" \
    -H "Content-Type: application/json" \
    -d '{
        "password": "TestPassword123!",
        "deletion_strategy": "anonymize",
        "confirmation": "SUPPRIMER MON COMPTE"
    }')

echo "$DELETE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DELETE_RESPONSE"

if echo "$DELETE_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Compte anonymisé avec succès${NC}"
else
    echo -e "${RED}❌ Échec suppression compte${NC}"
fi

# Nettoyage: Créer à nouveau l'utilisateur pour les prochains tests
echo -e "\n${YELLOW}[9/10] Ré-création utilisateur pour futurs tests...${NC}"
curl -s -X POST "$BASE_URL/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "email": "test.user@example.mg",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "preferred_language": "fr"
    }' > /dev/null 2>&1

echo -e "\n${GREEN}=========================================="
echo "✅ Tests terminés !"
echo "==========================================${NC}"
echo -e "\nServeur toujours disponible sur: $BASE_URL"
echo "Swagger UI: $BASE_URL/api/docs"
echo "Redoc: $BASE_URL/api/redoc"
