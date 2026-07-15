#!/usr/bin/env python3
"""Seed de démonstration pour la base de données locale.

Crée un utilisateur de test et une conversation associée afin de pouvoir
valider rapidement les endpoints auth/users sans dépendre d’un jeu de données vide.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import Base, engine
from app.db.models import Conversation, Message, User
from sqlalchemy.orm import Session


def run() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        existing = session.query(User).filter(User.email == "demo@example.com").first()
        if existing:
            print("Seed already present")
            return

        user = User(
            email="demo@example.com",
            hashed_password="demo-hash",
            full_name="Demo User",
            preferred_language="fr",
        )
        session.add(user)
        session.flush()

        conversation = Conversation(
            user_id=user.id,
            title="Conversation de démonstration",
            language="fr",
        )
        session.add(conversation)
        session.flush()

        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="Bonjour, ceci est un message de démo.",
            language="fr",
        )
        session.add(message)
        session.commit()
        print("Seed created for demo@example.com")


if __name__ == "__main__":
    run()
