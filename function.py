"""
title: OpenRouter Stats & Cost tracking
author: Hristo Karamanliev
author_url: https://github.com/karamanliev
version: 1.1.0
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
            default="",
            description="API key for OpenRouter API (add this if you want to track your remaining credits)",
        )
        total_tokens: bool = Field(
            default=True, description="Display total number of tokens"
        )
        elapsed_time: bool = Field(default=True, description="Display the elapsed time")
        tokens_per_sec: bool = Field(
            default=True, description="Display tokens per second metric"
        )
        base_credits: bool = Field(
            default=True,
            description="Display base credits (the amount of credits you bought)",
        )
        show_emojis: bool = Field(
            default=True, description="Show emojis in the status message"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.start_time = None
        self.is_openrouter = False

    async def inlet(
        self,
        body: Dict,
        __model__: Optional[dict] = None,
    ) -> Dict:
        model_id = __model__.get("id", "")
        top_provider = __model__.get("top_provider")

        if "/" in model_id and top_provider:
            self.is_openrouter = True
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

        EMOJI = {
            "tokens": "🪙" if self.valves.show_emojis else "",
            "time": "⏱️" if self.valves.show_emojis else "",
            "speed": "⚡" if self.valves.show_emojis else "",
            "cost": "💸" if self.valves.show_emojis else "",
            "credits": "💰" if self.valves.show_emojis else "",
        }

        usage = body.get("messages", [{}])[-1].get("usage", {})
        total_tokens = usage.get("total_tokens", 0)

        cost = usage.get("cost", 0)

        end_time = time.time()
        elapsed_time = end_time - self.start_time
        tokens_per_sec = total_tokens / elapsed_time

        # Fetch remaining credits if API key provided
        remaining: Optional[float] = None
        key = self.valves.openrouter_api_key
        if key and key != "":
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
                base_credits = float(data.get("total_credits", 0))
            except Exception as exc:
                logger.warning("Credits lookup failed – %s", exc)

        stats = []

        if self.valves.total_tokens:
            stats.append(f"{EMOJI['tokens']} {total_tokens} Tokens")
        if self.valves.elapsed_time:
            stats.append(f"{EMOJI['time']} {elapsed_time:.2f} s")
        if self.valves.tokens_per_sec:
            stats.append(f"{EMOJI['speed']} {tokens_per_sec:.2f} T/s")

        if cost != 0:
            stats.append(f"{EMOJI['cost']} ${cost:.7f}")

        if remaining is not None:
            if self.valves.base_credits:
                stats.append(
                    f"{EMOJI['credits']} ${remaining:.7f} of ${base_credits:.2f}"
                )
            else:
                stats.append(f"{EMOJI['credits']} ${remaining:.7f}")

        final_stats = " | ".join(stats)

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": final_stats, "done": True}}
            )

        return body
