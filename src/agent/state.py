"""LangGraph state schema for dating agent.

PROPER IMPLEMENTATION using LangChain-LangGraph patterns:
- Uses Annotated with add_messages for message accumulation
- Uses proper LangChain message types (HumanMessage, AIMessage, etc.)
- State is designed for graph traversal with reducers
"""
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class DatingState(TypedDict, total=False):
    """
    State schema for the dating agent graph.
    
    Key features:
    - messages: Uses add_messages reducer for automatic accumulation
    - Proper typing for LangChain integration
    """

    # PROPER: Messages with add_messages reducer for accumulation
    # When a node returns {"messages": [new_message]}, it APPENDS instead of replacing
    messages: Annotated[List[BaseMessage], add_messages]

    # Input fields
    user_id: int
    phone_number: str
    chat_id: int
    
    # Legacy field for backward compatibility during transition
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

    # Error handling
    error: Optional[str]
