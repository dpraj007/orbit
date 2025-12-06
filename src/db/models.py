"""Database models for Orbit dating agent."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """User model."""

    phone_number: str
    chat_id: Optional[int] = None
    name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    dating_enabled: bool = True
    status: str = "onboarding"


@dataclass
class Profile:
    """Dating profile model with natural language summaries."""

    user_id: int
    profile_summary: Optional[str] = None  # Natural language - who they are
    looking_for_summary: Optional[str] = None  # Natural language - what they want
    dealbreakers: Optional[str] = None  # Comma-separated
    interests: Optional[str] = None  # Comma-separated
    communication_style: Optional[str] = None  # warm / witty / direct / analytical
    relationship_goal: Optional[str] = None  # casual / serious / exploring
    completeness: float = 0.0  # 0.0 to 1.0
    onboarding_step: int = 0
    updated_at: Optional[str] = None


@dataclass
class Match:
    """Match between two users."""

    id: Optional[int] = None
    user_a_id: int = 0
    user_b_id: int = 0
    bilateral_score: float = 0.0
    status: str = "pending_a"  # pending_a / pending_b / mutual / rejected
    user_a_decision: str = "pending"  # yes / no / pending
    user_b_decision: str = "pending"
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


@dataclass
class ConversationState:
    """Conversation state for tracking agent flow."""

    user_id: int
    current_node: Optional[str] = None
    context: Optional[str] = None  # JSON blob
    match_in_progress: Optional[int] = None
    updated_at: Optional[str] = None
