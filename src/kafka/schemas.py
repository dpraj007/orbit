"""Pydantic schemas for Kafka message formats."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatHandle(BaseModel):
    """Chat participant handle."""
    display_name: Optional[str] = None
    identifier: Optional[str] = None
    is_me: Optional[bool] = False


class KafkaEventData(BaseModel):
    """Data payload from Kafka event."""

    text: Optional[str] = None
    from_phone: Optional[str] = None
    chat_id: Optional[int] = None
    chat_handles: Optional[List[ChatHandle]] = Field(default_factory=list)
    message_id: Optional[int] = None
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class KafkaEvent(BaseModel):
    """Kafka message event schema."""

    event_type: Optional[str] = None
    data: KafkaEventData = Field(default_factory=KafkaEventData)
    timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KafkaEvent":
        """Create from raw dictionary."""
        return cls(
            event_type=data.get("event_type"),
            data=KafkaEventData(**data.get("data", {})),
            timestamp=data.get("timestamp"),
        )
