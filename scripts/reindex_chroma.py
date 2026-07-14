#!/usr/bin/env python3
"""Réindexer les documents juridiques dans ChromaDB par domaine.

Usage:
    . .venv/bin/activate
    python scripts/reindex_chroma.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "Data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.chroma_client import get_chroma_client, get_or_create_collection

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pypdf est requis. Installez les dépendances du projet avec .venv") from exc


DOMAIN_FILES: dict[str, list[Tuple[str, str]]] = {
    "droit_travail": [
        ("Loi-n°-2024-014-Code-de-travail.doc.pdf", "droit_travail"),
    ],
    "foncier": [
        ("Madagascar - Code Foncier.pdf", "foncier"),
    ],
    "famille": [
        ("L-2007-022-Mariage-et-régimes-matrimoniaux.pdf", "famille"),
    ],
}

COLLECTION_NAMES = {
    "droit_travail": "droit_travail_mg",
    "foncier": "foncier_mg",
    "famille": "famille_mg",
}


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    texts: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        texts.append(text)
    return "\n\n".join(texts).strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks


def index_domain(domain: str, files: list[Tuple[str, str]]) -> int:
    collection_name = COLLECTION_NAMES[domain]
    client = get_chroma_client()
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = get_or_create_collection(collection_name)
    all_documents: List[str] = []
    all_metadatas: List[dict] = []
    all_ids: List[str] = []

    for filename, source_type in files:
        pdf_path = DATA_DIR / filename
        if not pdf_path.exists():
            print(f"[skip] fichier introuvable: {pdf_path}")
            continue

        raw_text = extract_text_from_pdf(pdf_path)
        chunks = chunk_text(raw_text)
        if not chunks:
            continue

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{domain}:{filename}:{idx}"
            all_documents.append(chunk)
            all_metadatas.append(
                {
                    "domain": domain,
                    "source_file": filename,
                    "source_type": source_type,
                    "language": "fr",
                }
            )
            all_ids.append(chunk_id)

    if all_documents:
        collection.add(documents=all_documents, metadatas=all_metadatas, ids=all_ids)

    print(f"[ok] {domain}: {len(all_documents)} chunks indexés dans {collection_name}")
    return len(all_documents)


def main() -> None:
    print(f"Réindexation ChromaDB depuis {DATA_DIR}")
    totals: dict[str, int] = {}
    for domain, files in DOMAIN_FILES.items():
        totals[domain] = index_domain(domain, files)

    print("Résumé:")
    for domain, count in totals.items():
        print(f"- {domain}: {count} chunks")


if __name__ == "__main__":
    main()
