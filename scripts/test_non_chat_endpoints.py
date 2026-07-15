#!/usr/bin/env python3
"""Script de test des endpoints non-chat de l’API.

Il interroge l’instance distante et vérifie que les routes principales
répondent avec un statut HTTP valide, sans tester le chat.
"""

import sys
from typing import List, Tuple

import requests

BASE_URL = "http://api.mpanolontsaina-ia.duckdns.org"

TESTS: List[Tuple[str, str, dict]] = [
    ("GET", "/health", {}),
    ("GET", "/api/docs", {}),
    ("GET", "/api/openapi.json", {}),
    ("GET", "/api/redoc", {}),
    ("POST", "/api/v1/auth/register", {"email": "demo@example.com", "password": "Secret123!", "full_name": "Demo"}),
    ("POST", "/api/v1/auth/login", {"email": "demo@example.com", "password": "Secret123!"}),
    ("POST", "/api/v1/auth/refresh", {}),
    ("POST", "/api/v1/auth/logout", {}),
    ("GET", "/api/v1/users/me", {}),
    ("PATCH", "/api/v1/users/me", {"full_name": "Demo Updated"}),
]


def run() -> None:
    for method, path, payload in TESTS:
        url = BASE_URL + path
        try:
            if method == "GET":
                response = requests.get(url, timeout=15)
            elif method == "POST":
                response = requests.post(url, json=payload, timeout=15)
            elif method == "PATCH":
                response = requests.patch(url, json=payload, timeout=15)
            else:
                response = requests.request(method, url, timeout=15)
        except requests.RequestException as exc:
            print(f"{method} {path} -> ERROR {exc}")
            continue

        print(f"{method} {path} -> {response.status_code}")
        if response.text:
            print(response.text[:250].replace("\n", " "))
        print("---")


if __name__ == "__main__":
    run()
