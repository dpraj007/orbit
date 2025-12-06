import logging
import time
from typing import Any, Dict, Iterable, Optional

import httpx

from .utils import backoff


class SeriesClient:
    def __init__(
        self, base_url: str, api_key: str, timeout: float = 10.0, max_retries: int = 3, sender_number: str = ""
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.sender_number = sender_number
        self.log = logging.getLogger("orbit.series")

    def _request(
        self, method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = httpx.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json() if resp.content else {}
            except Exception as exc:
                last_exc = exc
                delay = backoff(attempt)
                self.log.warning("Series request failed (%s %s): %s retrying in %.2fs", method, path, exc, delay)
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    def send_message(self, chat_id: int, text: str, attachments: Optional[Iterable[dict]] = None) -> Dict[str, Any]:
        payload = {"message": {"text": text}}
        if attachments:
            payload["message"]["attachments"] = list(attachments)
        return self._request("POST", f"/api/chats/{chat_id}/chat_messages", json=payload)

    def create_group_chat(
        self, phone_numbers: Iterable[str], initial_text: str, display_name: str = "", send_from: Optional[str] = None
    ) -> Dict[str, Any]:
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

    def list_chats(self, phone_number: Optional[str] = None, page: int = 1, per_page: int = 50) -> Iterable[Dict[str, Any]]:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if phone_number:
            params["phone_number"] = phone_number
        resp = self._request("GET", "/api/chats", params=params)
        data = resp.get("data")
        return data if isinstance(data, list) else []

    def list_chat_messages(self, chat_id: int, page: int = 1, per_page: int = 50) -> Iterable[Dict[str, Any]]:
        params = {"page": page, "per_page": per_page}
        resp = self._request("GET", f"/api/chats/{chat_id}/chat_messages", params=params)
        data = resp.get("data")
        return data if isinstance(data, list) else []

    def set_typing(self, chat_id: int) -> None:
        self._request("POST", f"/api/chats/{chat_id}/start_typing")

    def send_reaction(self, message_id: int, reaction_type: str) -> None:
        self._request("POST", f"/api/chat_messages/{message_id}/reactions", json={"type": reaction_type})
