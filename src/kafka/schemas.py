"""Pydantic schemas for Kafka message formats."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ChatHandle(BaseModel):
    """Chat handle from Kafka event."""
    display_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_me: Optional[bool] = None


class KafkaEventData(BaseModel):
    """Data payload from Kafka event."""

    text: Optional[str] = None
    from_phone: Optional[str] = None
    chat_id: Optional[int] = None
    chat_handles: Optional[List[ChatHandle]] = Field(default_factory=list)
    message_id: Optional[int] = None
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_handles(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Allow chat_handles to be passed as phone strings or dicts."""
        handles = values.get("chat_handles")
        if not handles:
            values["chat_handles"] = []
            return values

        normalized = []
        for handle in handles:
            if isinstance(handle, ChatHandle):
                normalized.append(handle.model_dump())
            elif isinstance(handle, str):
                normalized.append({"phone_number": handle})
            elif isinstance(handle, dict):
                normalized.append(handle)
        values["chat_handles"] = normalized
        return values


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
