"""Onboarding node for profile building.

PROPER IMPLEMENTATION using LangChain-LangGraph patterns:
- Extracts message from proper HumanMessage types
- Returns AIMessage for response (will be added to messages via add_messages)
"""
import json
import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from ...prompts import PROFILE_UPDATE_PROMPT
from ...utils.llm import get_llm

ONBOARDING_QUESTIONS = [
    "Hey! What's your name and one thing you're passionate about?",
    "What kind of vibe are you looking for? (casual, serious, or just exploring?)",
    "Tell me a bit about yourself - what do you do, what lights you up?",
    "What matters to you in a partner? What are you looking for?",
    "Any dealbreakers or hard stops we should know about?",
    "How would your friends describe your communication style?",
    "What does a perfect weekend look like for you?",
]


def extract_profile_info(message: str, current_profile: str, step: int) -> Dict[str, Any]:
    """Extract profile information from user message."""
    log = logging.getLogger("orbit.agent.onboarding")

    # Simple extraction based on step
    extraction = {}

    try:
        # For the first few steps, do simple extraction
        if step == 0:
            # Name and passion
            words = message.split()
            if len(words) > 0:
                extraction["name"] = words[0].strip(".,!?")
            extraction["passion"] = message

        elif step == 1:
            # Relationship goal
            message_lower = message.lower()
            if "casual" in message_lower:
                extraction["relationship_goal"] = "casual"
            elif "serious" in message_lower:
                extraction["relationship_goal"] = "serious"
            else:
                extraction["relationship_goal"] = "exploring"

        elif step == 2:
            # About themselves
            extraction["bio"] = message

        elif step == 3:
            # Looking for
            extraction["looking_for"] = message

        elif step == 4:
            # Dealbreakers
            extraction["dealbreakers"] = message

        elif step == 5:
            # Communication style
            message_lower = message.lower()
            if "warm" in message_lower or "friendly" in message_lower:
                extraction["communication_style"] = "warm"
            elif "witty" in message_lower or "funny" in message_lower:
                extraction["communication_style"] = "witty"
            elif "direct" in message_lower or "straightforward" in message_lower:
                extraction["communication_style"] = "direct"
            else:
                extraction["communication_style"] = "analytical"

        elif step == 6:
            # Interests from weekend description
            extraction["interests"] = message

        return extraction

    except Exception as exc:
        log.warning("Extraction failed: %s", exc)
        return {}


def update_profile_summary(
    current_summary: str, new_info: Dict[str, Any], user_name: str
) -> str:
    """Update natural language profile summary."""
    log = logging.getLogger("orbit.agent.onboarding")

    # Build a simple summary from extracted info
    parts = []

    if user_name:
        if new_info.get("bio"):
            parts.append(f"{user_name} {new_info['bio']}")
        else:
            parts.append(f"{user_name}")

    if new_info.get("passion"):
        parts.append(f"Passionate about {new_info['passion']}.")

    if new_info.get("communication_style"):
        parts.append(f"Communication style: {new_info['communication_style']}.")

    if new_info.get("interests"):
        parts.append(f"Interests: {new_info['interests']}.")

    summary = " ".join(parts) if parts else (current_summary or "")

    # If we have current summary, merge it
    if current_summary and summary and summary != current_summary:
        summary = f"{current_summary} {summary}"

    # Ensure we have a string, not None
    if not summary:
        summary = ""

    return summary[:500]  # Keep it reasonable length


def onboarding_node(state: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Handle onboarding flow.
    
    PROPER: Extracts message from messages list (HumanMessage types) 
    and returns response that will be added to messages via add_messages.
    """
    log = logging.getLogger("orbit.agent.onboarding")

    user = state.get("user", {})
    profile = state.get("profile", {})
    user_id = state.get("user_id")
    
    # PROPER: Extract message from messages list or fall back to legacy field
    message = ""
    messages = state.get("messages", [])
    if messages:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                message = msg.content
                break
    if not message:
        message = state.get("message", "")

    if not user_id:
        return {"response": "Sorry, I couldn't find your profile. Let's start over.", "error": "No user_id"}

    # Get current step
    current_step = profile.get("onboarding_step", 0) if profile else 0
    log.info("Onboarding step %d for user %d", current_step, user_id)

    # Extract info from current message
    current_summary = profile.get("profile_summary", "") if profile else ""
    user_name = user.get("name", "User")

    extraction = extract_profile_info(message, current_summary, current_step)

    # Update database
    if extraction:
        # Update name if extracted
        if extraction.get("name") and not user.get("name"):
            user_name = extraction["name"]
            # Will be updated via db_updates

        # Update profile fields
        if extraction.get("relationship_goal"):
            db.profiles.update_field(user_id, "relationship_goal", extraction["relationship_goal"])

        if extraction.get("communication_style"):
            db.profiles.update_field(user_id, "communication_style", extraction["communication_style"])

        if extraction.get("dealbreakers"):
            db.profiles.update_field(user_id, "dealbreakers", extraction["dealbreakers"])

        if extraction.get("looking_for"):
            db.profiles.update_field(user_id, "looking_for_summary", extraction["looking_for"])

        # Update summary
        new_summary = update_profile_summary(current_summary, extraction, user_name)
        if new_summary != current_summary:
            completeness = min((current_step + 1) / len(ONBOARDING_QUESTIONS), 1.0)
            db.profiles.update_summary(user_id, new_summary, completeness)

    # Move to next step
    next_step = current_step + 1
    db.profiles.increment_step(user_id)

    # Check if onboarding is complete
    if next_step >= len(ONBOARDING_QUESTIONS):
        db.users.update_status(user_id, "active")
        response = (
            "Thanks! I've got a good sense of who you are now. "
            "I'll start looking for people who might vibe with you. "
            "Want me to find some matches?"
        )
        db.conversation_state.upsert(user_id, current_node="browsing")
    else:
        # Ask next question
        response = ONBOARDING_QUESTIONS[next_step]
        db.conversation_state.upsert(user_id, current_node="onboarding")

    log.info("Onboarding response generated for step %d -> %d", current_step, next_step)

    # PROPER: Return both messages (for new pattern) and response (for legacy)
    return {
        "messages": [AIMessage(content=response)],  # Will be appended via add_messages
        "response": response,  # Legacy field for backward compatibility
        "next_node": "save_and_respond",
        "db_updates": [{"type": "onboarding_step", "user_id": user_id, "step": next_step}],
    }
