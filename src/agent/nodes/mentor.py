"""Mentor node for dating guidance.

PROPER IMPLEMENTATION using LangChain-LangGraph patterns:
- Extracts message from proper HumanMessage types
- Returns AIMessage for response (will be added to messages via add_messages)
"""
import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from ...prompts import (
    CONVERSATION_CONTINUATION_PROMPT,
    ICEBREAKER_PROMPT,
    POST_DATE_DEBRIEF_PROMPT,
    PRE_DATE_PREP_PROMPT,
    RECOVERY_PROMPT,
)
from ...utils.llm import get_llm


def detect_mentor_mode(message: str) -> str:
    """Detect which mentor mode to use."""
    message_lower = message.lower()

    # Check more specific patterns first
    if any(phrase in message_lower for phrase in ["icebreaker", "opener", "first message", "start conversation", "conversation starter"]):
        return "icebreaker"
    elif any(phrase in message_lower for phrase in ["went", "happened", "debrief", "how was", "date went"]):
        return "post_date"
    elif any(phrase in message_lower for phrase in ["date", "meeting", "prep", "nervous", "upcoming date"]):
        return "pre_date"
    elif any(phrase in message_lower for phrase in ["ghost", "rejected", "stuck", "ignored"]):
        return "recovery"
    elif "help" in message_lower and any(word in message_lower for word in ["start", "conversation", "message", "talk"]):
        return "icebreaker"
    elif "help" in message_lower:
        return "recovery"
    else:
        return "continuation"


def generate_icebreakers(
    user_profile: Dict[str, Any], match_profile: Dict[str, Any]
) -> str:
    """Generate conversation icebreakers."""
    llm = get_llm()

    user_style = user_profile.get("communication_style", "warm")

    prompt = ICEBREAKER_PROMPT.format(
        user_profile=user_profile.get("profile_summary", ""),
        match_profile=match_profile.get("profile_summary", ""),
        user_style=user_style,
    )

    try:
        result = llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)
    except Exception as exc:
        logging.getLogger("orbit.agent.mentor").error("Icebreaker generation failed: %s", exc)
        return "Here are some conversation starters:\n1. Ask about their interests\n2. Share something about yourself\n3. Find common ground"


def provide_conversation_help(
    user_profile: Dict[str, Any], match_profile: Dict[str, Any], recent_conversation: str
) -> str:
    """Provide conversation continuation advice."""
    llm = get_llm()

    prompt = CONVERSATION_CONTINUATION_PROMPT.format(
        user_profile=user_profile.get("profile_summary", ""),
        match_profile=match_profile.get("profile_summary", ""),
        conversation_excerpt=recent_conversation,
    )

    try:
        result = llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)
    except Exception as exc:
        logging.getLogger("orbit.agent.mentor").error("Conversation help failed: %s", exc)
        return "Focus on topics they seem engaged with, ask open-ended questions, and share your own experiences too."


def provide_pre_date_prep(
    user_profile: Dict[str, Any], match_profile: Dict[str, Any], date_context: str
) -> str:
    """Provide pre-date preparation advice."""
    llm = get_llm()

    prompt = PRE_DATE_PREP_PROMPT.format(
        user_profile=user_profile.get("profile_summary", ""),
        match_profile=match_profile.get("profile_summary", ""),
        date_context=date_context,
    )

    try:
        result = llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)
    except Exception as exc:
        logging.getLogger("orbit.agent.mentor").error("Pre-date prep failed: %s", exc)
        return "Be yourself, ask questions, listen actively, and enjoy getting to know them. You've got this!"


def provide_post_date_debrief(
    user_profile: Dict[str, Any], match_profile: Dict[str, Any], reflection: str
) -> str:
    """Provide post-date debrief support."""
    llm = get_llm()

    prompt = POST_DATE_DEBRIEF_PROMPT.format(
        user_profile=user_profile.get("profile_summary", ""),
        match_profile=match_profile.get("profile_summary", ""),
        user_reflection=reflection,
    )

    try:
        result = llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)
    except Exception as exc:
        logging.getLogger("orbit.agent.mentor").error("Post-date debrief failed: %s", exc)
        return "Thanks for sharing! How are you feeling about it? What stood out to you?"


def provide_recovery_support(user_profile: Dict[str, Any], situation: str) -> str:
    """Provide recovery support for difficult situations."""
    llm = get_llm()

    prompt = RECOVERY_PROMPT.format(
        user_profile=user_profile.get("profile_summary", ""), situation=situation
    )

    try:
        result = llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)
    except Exception as exc:
        logging.getLogger("orbit.agent.mentor").error("Recovery support failed: %s", exc)
        return "That's tough, and it's okay to feel disappointed. Remember, it's not a reflection of your worth. Want to talk about it or look for new matches?"


def mentor_node(state: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Handle mentor guidance requests.
    
    PROPER: Extracts message from messages list (HumanMessage types)
    and returns AIMessage for response.
    """
    log = logging.getLogger("orbit.agent.mentor")

    user_id = state.get("user_id")
    profile = state.get("profile", {})
    conv_state = state.get("conversation_state", {})
    
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

    if not user_id or not profile:
        resp = "I need to get to know you better first before I can help!"
        return {"messages": [AIMessage(content=resp)], "response": resp}

    # Detect mentor mode
    mode = detect_mentor_mode(message)
    log.info("Mentor mode: %s for user %d", mode, user_id)

    # Get match profile if available
    match_id = conv_state.get("match_in_progress") if conv_state else None
    match_profile = {}

    if match_id:
        match_row = db.matches.get_by_id(match_id)
        if match_row:
            other_user_id = (
                match_row["user_b_id"]
                if match_row["user_a_id"] == user_id
                else match_row["user_a_id"]
            )
            match_profile_row = db.profiles.get_by_user_id(other_user_id)
            match_profile = dict(match_profile_row) if match_profile_row else {}

    # Generate response based on mode
    if mode == "icebreaker":
        if not match_profile:
            response = "I need to know who you're matched with to help with icebreakers. Do you have an active match?"
        else:
            response = generate_icebreakers(profile, match_profile)

    elif mode == "pre_date":
        if not match_profile:
            response = "Tell me about your upcoming date! Who is it with and where are you going?"
        else:
            response = provide_pre_date_prep(profile, match_profile, message)

    elif mode == "post_date":
        if not match_profile:
            match_profile = {"profile_summary": "your recent date"}
        response = provide_post_date_debrief(profile, match_profile, message)

    elif mode == "recovery":
        response = provide_recovery_support(profile, message)

    else:  # continuation
        if not match_profile:
            response = "I can help with conversation tips! Tell me more about who you're talking to and what you've discussed so far."
        else:
            response = provide_conversation_help(profile, match_profile, message)

    # PROPER: Return both messages (for new pattern) and response (for legacy)
    return {"messages": [AIMessage(content=response)], "response": response, "next_node": "save_and_respond"}
