import json
import logging
from typing import Dict, Any

import httpx


log = logging.getLogger("orbit.llm")


SYSTEM_DATING_ASSISTANT = (
    "You are Orbit, a warm, insightful dating AI assistant. "
    "You help people build meaningful connections through natural conversation. "
    "Be brief, genuine, and supportive. Never be pushy or manipulative."
)


class WingmanLLM:
    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.log = logging.getLogger("orbit.llm")

    def _post_chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Make a chat completion request."""
        if not self.api_key:
            raise RuntimeError("Missing OPENROUTER_API_KEY")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/lehzhu/orbit",
            "X-Title": "Orbit Dating Wingman",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        try:
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
        except Exception as e:
            self.log.error(f"LLM request failed: {e}")
            raise

    def classify_intent(self, prompt: str) -> str:
        """Classify user intent from a prompt."""
        try:
            result = self._post_chat(
                [
                    {"role": "system", "content": SYSTEM_DATING_ASSISTANT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            # Extract first word
            return result.split()[0].strip().lower()
        except Exception as e:
            self.log.error(f"Intent classification failed: {e}")
            return "general"

    def extract_profile_info(self, prompt: str) -> Dict[str, Any]:
        """Extract profile information and return as JSON."""
        try:
            result = self._post_chat(
                [
                    {"role": "system", "content": SYSTEM_DATING_ASSISTANT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            # Try to parse as JSON
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
                return json.loads(result)
        except Exception as e:
            self.log.error(f"Profile extraction failed: {e}")
            return {}

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate text from a prompt."""
        try:
            return self._post_chat(
                [
                    {"role": "system", "content": SYSTEM_DATING_ASSISTANT},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
        except Exception as e:
            self.log.error(f"Text generation failed: {e}")
            return "I'm having trouble generating a response right now."

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        """Generate JSON response from a prompt."""
        try:
            result = self._post_chat(
                [
                    {"role": "system", "content": SYSTEM_DATING_ASSISTANT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            # Try to parse as JSON
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
                return json.loads(result)
        except Exception as e:
            self.log.error(f"JSON generation failed: {e}")
            return {}

    # Legacy methods for backwards compatibility
    def craft_reply(self, prompt: str, temperature: float = 0.7) -> str:
        """Legacy method - use generate_text instead."""
        return self.generate_text(prompt, temperature)

    def extract_onboarding(self, step: int, message: str) -> Dict[str, str]:
        """Legacy method - use extract_profile_info instead."""
        from .prompts.onboarding import get_extraction_prompt
        prompt = get_extraction_prompt(step, message)
        return self.extract_profile_info(prompt)
