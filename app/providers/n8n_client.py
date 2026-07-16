"""
Client HTTP pour invoquer le webhook n8n.
Gère les appels async avec timeout, retry automatique et logging.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class N8nClient:
    """Client pour envoyer des requêtes au webhook n8n."""

    def __init__(
        self,
        webhook_url: str,
        timeout: int = 30,
        auto_retry: bool = True,
        max_retries: int = 3,
    ):
        """
        Initialise le client n8n.
        
        Args:
            webhook_url: URL complète du webhook n8n
            timeout: Timeout en secondes pour chaque requête
            auto_retry: Active les retries automatiques en cas d'erreur réseau
            max_retries: Nombre maximum de retries
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.auto_retry = auto_retry
        self.max_retries = max_retries

    async def send_chat_request(
        self,
        message: str,
        language: Optional[str] = None,
        session_id: Optional[str] = None,
        history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Envoie une requête de chat au webhook n8n.
        
        Args:
            message: Message utilisateur
            language: Langue (mg, fr, en)
            session_id: Identifiant de session (UUID)
            history: Historique de conversation
            
        Returns:
            Réponse du webhook (dict avec output_message, agent_source, etc.)
            
        Raises:
            Exception: Si la requête échoue après tous les retries
        """
        payload = {
            "message": message,
            "language": language,
            "session_id": session_id,
            "history": history or [],
        }

        logger.info(
            "[n8n_client] Envoi requête vers %s (session=%s, lang=%s)",
            self.webhook_url,
            session_id,
            language,
        )

        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.info(
                                "[n8n_client] ✓ Réponse n8n reçue (status=%d, len=%d)",
                                resp.status,
                                len(json.dumps(data)),
                            )
                            return data
                        else:
                            error_text = await resp.text()
                            raise Exception(
                                f"n8n returned status {resp.status}: {error_text}"
                            )

            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    "[n8n_client] ⏱ Timeout après %ds (tentative %d/%d)",
                    self.timeout,
                    attempt + 1,
                    self.max_retries + 1,
                )
            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(
                    "[n8n_client] 🔌 Erreur réseau (tentative %d/%d): %s",
                    attempt + 1,
                    self.max_retries + 1,
                    str(e),
                )
            except Exception as e:
                last_error = e
                logger.error(
                    "[n8n_client] ✗ Erreur n8n: %s",
                    str(e),
                )

            attempt += 1
            if attempt <= self.max_retries and self.auto_retry:
                wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                logger.info("[n8n_client] Retry dans %ds...", wait_time)
                await asyncio.sleep(wait_time)
            elif attempt > self.max_retries:
                break

        # Tous les retries échoués
        raise Exception(
            f"n8n webhook failed after {self.max_retries + 1} attempts: {str(last_error)}"
        )
