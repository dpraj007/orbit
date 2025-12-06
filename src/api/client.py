"""Series iMessage REST API client."""
import logging
import time
from typing import Any, Dict, Iterable, Optional

import httpx


def backoff(retry: int, base: float = 0.5, cap: float = 8.0) -> float:
    """Calculate exponential backoff delay."""
    return min(cap, base * (2**retry)) + (0.05 * retry)


class SeriesAPI:
    """Client for Series iMessage REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        sender_number: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.sender_number = sender_number
        self.log = logging.getLogger("orbit.api")

    def _request(
        self, method: str, path: str, json: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                resp = httpx.request(
                    method, url, headers=headers, json=json, timeout=self.timeout
                )
                resp.raise_for_status()
                return resp.json() if resp.content else {}
            except Exception as exc:
                last_exc = exc
                delay = backoff(attempt)
                self.log.warning(
                    "API request failed (%s %s): %s, retrying in %.2fs",
                    method,
                    path,
                    exc,
                    delay,
                )
                time.sleep(delay)

        raise last_exc  # type: ignore[misc]

    def get_or_create_chat(self, phone: str) -> int:
        """Get or create a 1:1 chat with a phone number."""
        # This would typically check for existing chat first
        # For now, we assume chat_id is provided via events
        raise NotImplementedError("Use chat_id from Kafka events")

    def send_message(
        self, chat_id: int, text: str, attachments: Optional[Iterable[dict]] = None
    ) -> Dict[str, Any]:
        """Send a message to a chat."""
        payload = {"message": {"text": text}}
        if attachments:
            payload["message"]["attachments"] = list(attachments)
        return self._request("POST", f"/api/chats/{chat_id}/chat_messages", json=payload)

    def start_typing(self, chat_id: int) -> None:
        """Show typing indicator in chat."""
        try:
            self._request("POST", f"/api/chats/{chat_id}/start_typing")
        except Exception as exc:
            self.log.warning("Failed to start typing indicator: %s", exc)

    def stop_typing(self, chat_id: int) -> None:
        """Stop typing indicator in chat."""
        try:
            self._request("POST", f"/api/chats/{chat_id}/stop_typing")
        except Exception as exc:
            self.log.warning("Failed to stop typing indicator: %s", exc)

    def get_messages(self, chat_id: int, limit: int = 50) -> list:
        """Get recent messages from a chat."""
        resp = self._request("GET", f"/api/chats/{chat_id}/chat_messages?limit={limit}")
        return resp.get("messages", [])

    def add_reaction(self, message_id: int, reaction_type: str) -> None:
        """Add a reaction to a message."""
        payload = {"type": reaction_type}
        self._request("POST", f"/api/chat_messages/{message_id}/reactions", json=payload)

    def create_group_chat(
        self,
        phone_numbers: Iterable[str],
        initial_text: str,
        display_name: str = "",
        send_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a group chat with initial message."""
        payload = {
            "chat": {"phone_numbers": list(phone_numbers)},
            "message": {"text": initial_text},
        }
        if display_name:
            payload["chat"]["display_name"] = display_name
        send_from_number = send_from or self.sender_number
        if send_from_number:
            payload["send_from"] = send_from_number
        return self._request("POST", "/api/chats", json=payload)

    def send_with_typing(self, chat_id: int, text: str, delay: float = 1.5) -> None:
        """Send message with typing indicator."""
        self.start_typing(chat_id)
        time.sleep(delay)
        self.send_message(chat_id, text)
