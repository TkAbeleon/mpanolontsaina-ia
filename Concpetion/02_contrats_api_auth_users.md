### Fichier : 02_contrats_api_auth_users.md

# Contrats d'API — Authentification & Gestion des Utilisateurs

Base URL : `/api/v1`
Authentification : JWT Bearer Token (`Authorization: Bearer <access_token>`), avec refresh token stocké côté client (httpOnly cookie recommandé).

---

## 1. Inscription — `POST /api/v1/auth/register`

Crée un nouveau compte utilisateur.

### Request Body

```json
{
  "email": "hery.rakoto@example.mg",
  "password": "MotDePasse!2024",
  "full_name": "Hery Rakoto",
  "preferred_language": "mg"
}
```

> `preferred_language` : facultatif, accepte `"mg"` (malagasy), `"fr"` (français) ou `"en"` (anglais). Valeur par défaut : `"fr"`. Utilisé pour pré-remplir la langue de réponse de l'agent sur les nouvelles conversations.

### Réponse succès — `201 Created`

```json
{
  "status": "success",
  "data": {
    "id": "3f1a9c2e-8b4d-4e2a-9f3a-1234567890ab",
    "email": "hery.rakoto@example.mg",
    "full_name": "Hery Rakoto",
    "preferred_language": "mg",
    "is_active": true,
    "created_at": "2026-07-07T10:15:00Z"
  }
}
```

### Réponse erreur — `409 Conflict` (email déjà utilisé)

```json
{
  "status": "error",
  "error": {
    "code": "EMAIL_ALREADY_EXISTS",
    "message": "Un compte existe déjà avec cet email."
  }
}
```

### Réponse erreur — `422 Unprocessable Entity` (validation)

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Le mot de passe doit contenir au moins 8 caractères.",
    "fields": {
      "password": "Trop court (minimum 8 caractères)."
    }
  }
}
```

---

## 2. Connexion — `POST /api/v1/auth/login`

### Request Body

```json
{
  "email": "hery.rakoto@example.mg",
  "password": "MotDePasse!2024"
}
```

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "d3b07384-d9a0-4f1a-9c2e-8b4d4e2a9f3a",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "3f1a9c2e-8b4d-4e2a-9f3a-1234567890ab",
      "email": "hery.rakoto@example.mg",
      "full_name": "Hery Rakoto"
    }
  }
}
```

### Réponse erreur — `401 Unauthorized`

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email ou mot de passe incorrect."
  }
}
```

### Réponse erreur — `403 Forbidden` (compte désactivé/supprimé)

```json
{
  "status": "error",
  "error": {
    "code": "ACCOUNT_DISABLED",
    "message": "Ce compte a été désactivé ou supprimé."
  }
}
```

---

## 3. Rafraîchissement de token — `POST /api/v1/auth/refresh`

### Request Body

```json
{
  "refresh_token": "d3b07384-d9a0-4f1a-9c2e-8b4d4e2a9f3a"
}
```

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

### Réponse erreur — `401 Unauthorized` (token expiré ou révoqué)

```json
{
  "status": "error",
  "error": {
    "code": "REFRESH_TOKEN_INVALID",
    "message": "Le refresh token est invalide, expiré ou déjà révoqué."
  }
}
```

---

## 4. Déconnexion — `POST /api/v1/auth/logout`

**Auth requise.** Révoque le refresh token courant.

### Request Body

```json
{
  "refresh_token": "d3b07384-d9a0-4f1a-9c2e-8b4d4e2a9f3a"
}
```

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "message": "Déconnexion réussie."
  }
}
```

### Réponse erreur — `401 Unauthorized`

```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Token d'accès manquant ou invalide."
  }
}
```

---

## 5. Consulter mon profil — `GET /api/v1/users/me`

**Auth requise.**

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "id": "3f1a9c2e-8b4d-4e2a-9f3a-1234567890ab",
    "email": "hery.rakoto@example.mg",
    "full_name": "Hery Rakoto",
    "is_active": true,
    "created_at": "2026-07-07T10:15:00Z"
  }
}
```

### Réponse erreur — `401 Unauthorized`

```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Token d'accès manquant ou invalide."
  }
}
```

---

## 6. Mettre à jour mon profil — `PATCH /api/v1/users/me`

**Auth requise.**

### Request Body

```json
{
  "full_name": "Hery A. Rakoto",
  "password": "NouveauMotDePasse!2025",
  "preferred_language": "fr"
}
```

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "id": "3f1a9c2e-8b4d-4e2a-9f3a-1234567890ab",
    "email": "hery.rakoto@example.mg",
    "full_name": "Hery A. Rakoto",
    "updated_at": "2026-07-07T11:00:00Z"
  }
}
```

### Réponse erreur — `400 Bad Request`

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_PAYLOAD",
    "message": "Aucun champ modifiable fourni."
  }
}
```

---

## 7. Suppression du compte (Droit à l'oubli) — `DELETE /api/v1/users/me`

**Auth requise.** Nécessite une reconfirmation du mot de passe pour des raisons de sécurité, ainsi que le choix explicite de la stratégie de suppression.

### Request Body

```json
{
  "password": "MotDePasse!2024",
  "deletion_strategy": "hard_delete",
  "confirmation": "SUPPRIMER MON COMPTE"
}
```

> `deletion_strategy` accepte `"hard_delete"` (suppression physique et définitive de toutes les données) ou `"anonymize"` (anonymisation totale : conservation d'un historique statistique totalement dissocié de l'identité).

### Réponse succès — `200 OK`

```json
{
  "status": "success",
  "data": {
    "message": "Votre compte et toutes vos données associées ont été supprimés définitivement.",
    "deletion_strategy": "hard_delete",
    "deleted_at": "2026-07-07T12:00:00Z"
  }
}
```

### Réponse erreur — `401 Unauthorized` (mot de passe incorrect)

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_PASSWORD",
    "message": "Le mot de passe fourni est incorrect."
  }
}
```

### Réponse erreur — `400 Bad Request` (confirmation manquante/incorrecte)

```json
{
  "status": "error",
  "error": {
    "code": "CONFIRMATION_REQUIRED",
    "message": "Le texte de confirmation ne correspond pas à celui attendu."
  }
}
```

### Réponse erreur — `404 Not Found`

```json
{
  "status": "error",
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "Utilisateur introuvable ou déjà supprimé."
  }
}
```
