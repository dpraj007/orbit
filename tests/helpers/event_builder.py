"""Build test events matching KafkaEvent schema."""
import random
from datetime import datetime, timezone
from typing import Optional


def build_event(
    phone: str = "+15551234567",
    chat_id: int = 1001,
    text: str = "Hello",
    message_id: Optional[int] = None,
    chat_handles: Optional[list[str]] = None,
    attachments: Optional[list[dict]] = None,
) -> dict:
    """Build a dict matching KafkaEvent schema for direct process_event calls."""
    return {
        "event_type": "message",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "text": text,
            "from_phone": phone,
            "chat_id": chat_id,
            "message_id": message_id or random.randint(1000, 9999),
            "chat_handles": chat_handles or [phone, "+15550000000"],
            "attachments": attachments or [],
        },
    }

