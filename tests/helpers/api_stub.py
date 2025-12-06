"""SeriesAPI stub that records calls without network I/O."""
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


@dataclass
class APICall:
    """Recorded API call."""
    method: str
    chat_id: Optional[int]
    payload: dict
    timestamp: datetime = field(default_factory=utc_now)


class SeriesAPIStub:
    """Records all API calls without network I/O."""

    def __init__(self):
        self.calls: list[APICall] = []
        self.group_chat_counter = 5000

    def send_message(
        self, chat_id: int, text: str, attachments: Optional[Iterable[dict]] = None
    ) -> dict:
        """Record send_message call."""
        payload = {"text": text}
        if attachments:
            payload["attachments"] = list(attachments)
        self.calls.append(APICall("send_message", chat_id, payload))
        return {"id": random.randint(1, 9999)}

    def send_with_typing(self, chat_id: int, text: str, delay: float = 0) -> None:
        """Record send_with_typing call."""
        self.calls.append(APICall("send_with_typing", chat_id, {"text": text}))

    def create_group_chat(
        self,
        phone_numbers: Iterable[str],
        initial_text: str,
        display_name: str = "",
        send_from: Optional[str] = None,
    ) -> dict:
        """Record create_group_chat call."""
        self.group_chat_counter += 1
        self.calls.append(
            APICall(
                "create_group_chat",
                None,
                {
                    "phone_numbers": list(phone_numbers),
                    "text": initial_text,
                    "display_name": display_name,
                    "send_from": send_from,
                },
            )
        )
        return {"chat": {"id": self.group_chat_counter}}

    def start_typing(self, chat_id: int) -> None:
        """Record start_typing call."""
        self.calls.append(APICall("start_typing", chat_id, {}))

    def stop_typing(self, chat_id: int) -> None:
        """Record stop_typing call."""
        self.calls.append(APICall("stop_typing", chat_id, {}))

    def get_messages(self, chat_id: int, limit: int = 50) -> list:
        """Return empty list (stub)."""
        return []

    def add_reaction(self, message_id: int, reaction_type: str) -> None:
        """Record add_reaction call."""
        self.calls.append(APICall("add_reaction", None, {"message_id": message_id, "type": reaction_type}))

    def get_messages_to(self, chat_id: int) -> list[str]:
        """Get all messages sent to a specific chat."""
        return [c.payload["text"] for c in self.calls if c.chat_id == chat_id and "text" in c.payload]

    def reset(self) -> None:
        """Clear all recorded calls."""
        self.calls.clear()
        self.group_chat_counter = 5000

