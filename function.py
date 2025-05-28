"""
title: OpenRouter Stats & Cost tracking
author: Hristo Karamanliev
author_url: https://github.com/karamanliev
version: 1.0.0
"""

import logging
import time
from typing import Dict, Optional, Callable
import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Filter:
    class Valves(BaseModel):
        openrouter_api_key: str = Field(
            default="", description="API key for OpenRouter API"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.start_time = None

    async def inlet(self, body: Dict) -> Dict:
        body["usage"] = {"include": True}

        self.start_time = time.time()
        return body

    async def outlet(
        self,
        body: Dict,
        __event_emitter__: Optional[Callable] = None,
    ) -> Dict:
        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": "Computing total costs...", "done": False},
            }
        )

        usage = body.get("messages", [{}])[-1].get("usage", {})
        total_tokens = usage.get("total_tokens", 0)

        cost = usage.get("cost", 0)

        end_time = time.time()
        elapsed_time = end_time - self.start_time
        tokens_per_sec = total_tokens / elapsed_time

        # Fetch remaining credits if API key provided
        remaining: Optional[float] = None
        key = self.valves.openrouter_api_key
        if key and key != "ENTER_KEY":
            try:
                r = requests.get(
                    "https://openrouter.ai/api/v1/credits",
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=5,
                )
                r.raise_for_status()
                data = r.json().get("data", {})
                remaining = float(data.get("total_credits", 0)) - float(
                    data.get("total_usage", 0)
                )
                total = float(data.get("total_credits", 0))
            except Exception as exc:
                logger.warning("Credits lookup failed – %s", exc)

        stats = (
            f"🪙 {total_tokens} Tokens | "
            f"⏱️ {elapsed_time:.2f} s | "
            f"⚡ {tokens_per_sec:.2f} T/s"
        )

        if cost is not 0:
            stats += f" | 💸 ${cost:.7f}"

        if remaining is not None:
            stats += f" | 💰 ${remaining:.7f} / ${total:.2f}"

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": stats, "done": True}}
            )

        return body
