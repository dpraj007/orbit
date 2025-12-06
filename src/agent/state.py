"""LangGraph state schema for dating agent."""
from typing import Any, Dict, List, Optional, TypedDict


class DatingState(TypedDict, total=False):
    """State schema for the dating agent graph."""

    # Input fields
    user_id: int
    phone_number: str
    chat_id: int
    message: str

    # Loaded context
    user: Optional[Dict[str, Any]]
    profile: Optional[Dict[str, Any]]
    conversation_state: Optional[Dict[str, Any]]
    active_match: Optional[Dict[str, Any]]

    # Routing
    intent: str
    current_node: str

    # Processing fields
    db_updates: List[Dict[str, Any]]
    response: str
    next_node: Optional[str]

    # Additional context
    messages: List[Any]  # For LangChain message history
    error: Optional[str]
