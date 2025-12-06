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
        self, method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                resp = httpx.request(
                    method, url, headers=headers, json=json, params=params, timeout=self.timeout
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

    def create_chat(self, phone_number: str, initial_text: str = "") -> Dict[str, Any]:
        """Create a single-recipient chat.
        
        Per OpenAPI spec, send_from, chat, and message are ALL required.
        """
        if not self.sender_number:
            raise ValueError("sender_number is required to create chats (set SERIES_SENDER_NUMBER)")
        # message.text is required per spec
        text = initial_text if initial_text else "👋"
        payload = {
            "send_from": self.sender_number,
            "chat": {"phone_numbers": [phone_number]},
            "message": {"text": text},
        }
        return self._request("POST", "/api/chats", json=payload)

    def list_chats(self, phone_number: Optional[str] = None, page: int = 1, per_page: int = 50) -> list:
        """List chats, optionally filtered by phone."""
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if phone_number:
            params["phone_number"] = phone_number
        resp = self._request("GET", "/api/chats", params=params)
        if "data" in resp and isinstance(resp["data"], list):
            return resp["data"]
        if "chats" in resp and isinstance(resp["chats"], list):
            return resp["chats"]
        return []

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
        """Stop typing indicator in chat.
        
        Per OpenAPI spec, this is a DELETE request.
        """
        try:
            self._request("DELETE", f"/api/chats/{chat_id}/stop_typing")
        except Exception as exc:
            self.log.warning("Failed to stop typing indicator: %s", exc)

    def get_messages(self, chat_id: int, limit: int = 50) -> list:
        """Get recent messages from a chat.
        
        Note: The Series API pagination is broken, so we fetch what we can
        from the list endpoint and use scan_for_new_messages() to find newer ones.
        """
        resp = self._request(
            "GET", 
            f"/api/chats/{chat_id}/chat_messages", 
            params={"per_page": 25}
        )
        msgs = resp.get("data") or resp.get("messages") or []
        msgs.sort(key=lambda m: m.get("id", 0))
        return msgs[-limit:] if limit else msgs

    def get_message_by_id(self, chat_id: int, message_id: int) -> dict | None:
        """Fetch a single message by ID."""
        try:
            resp = self._request("GET", f"/api/chats/{chat_id}/chat_messages/{message_id}")
            return resp.get("data")
        except Exception:
            return None

    def _fast_check_message(self, chat_id: int, message_id: int) -> dict | None:
        """Fast single-attempt message check (no retries) for scanning."""
        url = f"{self.base_url}/api/chats/{chat_id}/chat_messages/{message_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            resp = httpx.get(url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                return resp.json().get("data")
        except Exception:
            pass
        return None

    def get_chat_message_count(self, chat_id: int) -> int:
        """Get the total message count for a chat."""
        try:
            resp = self._request("GET", f"/api/chats/{chat_id}")
            return resp.get("data", {}).get("message_count", 0)
        except Exception:
            return 0

    def scan_for_new_messages(
        self, chat_id: int, after_id: int, max_scan: int = 25000, step: int = 1
    ) -> list:
        """Scan for new messages by probing IDs after a known message.
        
        This is a workaround for the broken list pagination.
        Uses fast non-retrying requests for efficiency.
        Returns messages found, sorted by ID ascending.
        """
        import concurrent.futures
        found = []
        
        def check_id(mid: int):
            msg = self._fast_check_message(chat_id, mid)
            return msg
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            results = executor.map(check_id, range(after_id + 1, after_id + max_scan, step))
            found = [m for m in results if m]
        
        found.sort(key=lambda m: m.get("id", 0))
        return found

    def list_chat_messages(self, chat_id: int, page: int = 1, per_page: int = 50) -> list:
        """List messages with pagination."""
        resp = self._request(
            "GET", f"/api/chats/{chat_id}/chat_messages", params={"page": page, "per_page": per_page}
        )
        data = resp.get("data") or resp.get("messages")
        return data if isinstance(data, list) else []

    def add_reaction(self, message_id: int, reaction_type: str, operation: str = "add") -> None:
        """Add or remove a reaction to a message.
        
        Per OpenAPI spec, both operation and type are required.
        operation: "add" or "remove"
        type: "love", "like", "dislike", "laugh", "emphasize", "question"
        """
        payload = {"operation": operation, "type": reaction_type}
        self._request("POST", f"/api/chat_messages/{message_id}/reactions", json=payload)

    def create_group_chat(
        self,
        phone_numbers: Iterable[str],
        initial_text: str,
        display_name: str = "",
        send_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a group chat with initial message.
        
        Per OpenAPI spec, send_from, chat, and message are ALL required.
        """
        send_from_number = send_from or self.sender_number
        if not send_from_number:
            raise ValueError("send_from is required to create chats (set SERIES_SENDER_NUMBER)")
        if not initial_text:
            raise ValueError("initial_text is required to create chats")
        payload = {
            "send_from": send_from_number,
            "chat": {"phone_numbers": list(phone_numbers)},
            "message": {"text": initial_text},
        }
        if display_name:
            payload["chat"]["display_name"] = display_name
        return self._request("POST", "/api/chats", json=payload)

    def send_with_typing(self, chat_id: int, text: str, delay: float = 1.5) -> None:
        """Send message with typing indicator."""
        self.start_typing(chat_id)
        time.sleep(delay)
        self.send_message(chat_id, text)
