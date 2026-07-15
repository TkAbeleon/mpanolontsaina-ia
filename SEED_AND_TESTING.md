# Seed et tests des endpoints non-chat

## Seed de démonstration

Le script [scripts/seed_demo.py](scripts/seed_demo.py) crée un utilisateur de test et une conversation associée dans la base de données locale.

### Exécution

```bash
./.venv/bin/python scripts/seed_demo.py
```

## Test des endpoints non-chat

Le script [scripts/test_non_chat_endpoints.py](scripts/test_non_chat_endpoints.py) interroge l’instance distante et vérifie les endpoints non-chat principaux.

### Exécution

```bash
./.venv/bin/python scripts/test_non_chat_endpoints.py
```

## Notes

- Les routes de chat ne sont pas testées ici.
- Le script d’API ne fait pas de requêtes authentifiées ; il vérifie surtout la disponibilité des routes et les réponses HTTP attendues.
