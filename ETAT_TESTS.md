# État des tests de l’API

## Date
2026-07-15

## Résultats des tests effectués

URL de production testée : https://api.mpanolontsaina-ia.duckdns.org

### 1. Santé de l’API
- Endpoint : `/health`
- Résultat : **200 OK**
- Observation : l’API répond correctement et signale un état sain.

### 2. Documentation de l’API
- Endpoints : `/api/docs`, `/api/redoc`, `/api/openapi.json`
- Résultat : **200 OK** pour les trois endpoints.
- Observation : la documentation Swagger/ReDoc et le schéma OpenAPI sont accessibles.

### 3. Endpoints non-chat
- Routes testées : auth et utilisateurs (hors chat)
- Résultats observés :
  - `POST /api/v1/auth/register` → **422**
  - `POST /api/v1/auth/login` → **422**
  - `POST /api/v1/auth/refresh` → **422**
  - `POST /api/v1/auth/logout` → **401**
  - `GET /api/v1/users/me` → **401**
  - `PATCH /api/v1/users/me` → **401**
- Observation : les endpoints répondent correctement selon le contexte métier attendu (validation des données, auth requise).

### 4. Seed de démonstration
- Script : `scripts/seed_demo.py`
- Résultat : exécution réussie, un utilisateur de démonstration a été créé si absent.

### 5. Script de test automatisé
- Script : `scripts/test_non_chat_endpoints.py`
- Résultat : exécution réussie, avec sortie des codes HTTP pour les endpoints non-chat.

## Conclusion
L’API semble bien opérationnelle sur les endpoints non-chat testés. Le chat n’a pas été inclus dans ces vérifications.
