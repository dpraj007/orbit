import json
import logging
from typing import Dict, Optional

import httpx

from .utils import safe_json


SYSTEM_WINGMAN = (
    "You are Orbit, a concise, warm dating wingman. You help humans connect over iMessage. "
    "Be brief, personal, lightly playful, and never spammy. Use short sentences. "
    "If giving advice, make it actionable in one or two lines."
)


class WingmanLLM:
    def __init__(self, api_key: str, model: str, timeout: float = 12.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.log = logging.getLogger("orbit.llm")

    def _post_chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        if not self.api_key:
            raise RuntimeError("Missing OPENROUTER_API_KEY")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/lehzhu/orbit",
            "X-Title": "Orbit Wingman",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()

    def classify_intent(self, message: str, state_hint: str = "") -> str:
        prompt = (
            "Classify the user's intent in one word from: onboarding, match_decision, mentor, general, settings.\n"
            f"State hint: {state_hint}\n"
            f"Message: {message}\n"
            "Respond with just the label."
        )
        try:
            return self._post_chat(
                [
                    {"role": "system", "content": SYSTEM_WINGMAN},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            ).split()[0].strip().lower()
        except Exception as exc:
            self.log.warning("Intent classify failed: %s", exc)
            return "general"

    def extract_onboarding(self, step: int, message: str) -> Dict[str, str]:
        instructions = {
            0: "Extract name and a passion if present.",
            1: "Extract 3-word vibe or weekend description.",
            2: "Extract any hard dealbreakers as a short list.",
        }
        prompt = (
            f"Message: {message}\n"
            f"Task: {instructions.get(step, 'Extract relevant details')} "
            "Return JSON with keys: name, passion, vibe, dealbreakers."
        )
        try:
            raw = self._post_chat(
                [
                    {"role": "system", "content": SYSTEM_WINGMAN},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return json.loads(raw)
        except Exception as exc:
            self.log.warning("Onboarding extract fallback: %s", exc)
            return {}

    def craft_reply(
        self,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        try:
            return self._post_chat(
                [{"role": "system", "content": SYSTEM_WINGMAN}, {"role": "user", "content": prompt}],
                temperature=temperature,
            )
        except Exception as exc:
            self.log.error("LLM reply failed: %s", exc)
            return "Mind grabbing that again?"
