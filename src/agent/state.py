from typing import TypedDict, Optional, Dict, Any


class DatingState(TypedDict):
    """State schema for the dating agent graph."""

    # Input from Kafka event
    phone_number: str
    chat_id: int
    message: str

    # Loaded from database
    user_id: Optional[int]
    user: Optional[Dict[str, Any]]
    profile: Optional[Dict[str, Any]]
    conversation_state: Optional[Dict[str, Any]]
    active_match: Optional[Dict[str, Any]]

    # Routing
    intent: Optional[str]

    # Output
    response: str
    next_node: Optional[str]

    # Database updates to be committed
    db_updates: list
