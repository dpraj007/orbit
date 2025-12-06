"""Pydantic models for API requests and responses."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageAttachment(BaseModel):
    """Message attachment model."""

    type: str
    url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    """Request to send a message."""

    text: str
    attachments: Optional[List[MessageAttachment]] = Field(default_factory=list)


class CreateGroupChatRequest(BaseModel):
    """Request to create a group chat."""

    phone_numbers: List[str]
    display_name: Optional[str] = None
    initial_message: str


class APIResponse(BaseModel):
    """Generic API response."""

    success: bool = True
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
