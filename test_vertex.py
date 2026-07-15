import asyncio
import os
from app.providers.vertex import VertexAIProvider
from app.config import get_settings

settings = get_settings()

async def test():
    provider = VertexAIProvider(settings)
    system_prompt = (
        "You are a legal domain classifier for Malagasy law.\n"
        "Classify the user's question into exactly ONE of these domains:\n"
        "  - droit_travail : labor law, employment contracts, dismissal, salary, notice period, leave, unions\n"
        "  - fiscalite : taxes, VAT, tax declarations, tax exemptions\n"
        "  - droit_affaires : business law, companies, commercial contracts, OHADA, company creation\n\n"
        "IMPORTANT: Respond with ONLY the domain name exactly as written above (droit_travail, fiscalite, or droit_affaires). If none match, respond with ONLY the word: autre\n"
        "Do NOT write anything else. No explanation, no punctuation."
    )
    user_prompt = "Quelle est la durée du préavis en cas de licenciement à Madagascar?"
    
    print("Testing generate...")
    res = await provider.agenerate(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0, max_tokens=20)
    print(f"Result length: {len(res)}, repr: {repr(res)}")

asyncio.run(test())
