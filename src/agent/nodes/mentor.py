"""Mentor node for dating guidance.

PROPER IMPLEMENTATION using LangChain-LangGraph patterns:
- Extracts message from proper HumanMessage types
- Returns AIMessage for response (will be added to messages via add_messages)
- Uses LLM to generate dynamic, contextual responses instead of hardcoded fallbacks
"""
import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from ...prompts import (
    CONVERSATION_CONTINUATION_PROMPT,
    ICEBREAKER_PROMPT,
    MENTOR_INTRO_PROMPT,
    NEEDS_ONBOARDING_PROMPT,
    POST_DATE_DEBRIEF_PROMPT,
    PRE_DATE_PREP_PROMPT,
    RECOVERY_PROMPT,
)
from ...utils.llm import get_llm


def generate_dynamic_response(prompt_template: str, **kwargs) -> str:
    """Generate a dynamic response using LLM with the given prompt template."""
    log = logging.getLogger("orbit.agent.mentor")
    llm = get_llm()

    prompt = prompt_template.format(**kwargs)

    try:
        result = llm.invoke(prompt)
        response = result.content if hasattr(result, "content") else str(result)
        return response.strip()
    except Exception as exc:
        log.error("Failed to generate dynamic response: %s", exc)
        return None


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
        # Dynamic fallback using LLM
        return generate_dynamic_response(
            """You are Orbit. Generate 3 creative conversation starters.
            
User style: {user_style}
Match interests: {match_interests}

Create openers that feel natural and spark dialogue. Return as a numbered list.""",
            user_style=user_style,
            match_interests=match_profile.get("profile_summary", "various interests"),
        ) or "Try asking about something they mentioned in their profile, or share something interesting about yourself!"


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
        return generate_dynamic_response(
            """You are Orbit helping with dating conversation advice.

The user needs help continuing a conversation with their match.
Their message: {message}

Give brief, actionable conversation tips. 2-3 sentences max.""",
            message=recent_conversation,
        ) or "Ask open-ended questions about what they're into, and share your own experiences too!"


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
        return generate_dynamic_response(
            """You are Orbit giving pre-date advice.

User's situation: {context}

Give warm, encouraging prep advice like a supportive friend. 2-3 sentences max.""",
            context=date_context,
        ) or "Be yourself, ask questions, and enjoy getting to know them. You've got this!"


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
        return generate_dynamic_response(
            """You are Orbit helping someone process a date experience.

What they shared: {reflection}

Respond as a supportive friend - ask how they're feeling and offer perspective. 2-3 sentences.""",
            reflection=reflection,
        ) or "How are you feeling about it? Tell me more about what happened!"


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
        return generate_dynamic_response(
            """You are Orbit offering emotional support.

User's situation: {situation}

Validate their feelings and offer perspective. Be warm and genuine. 2-3 sentences.""",
            situation=situation,
        ) or "That's tough, and your feelings are valid. It's not a reflection of your worth. Want to talk about it?"


def mentor_node(state: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Handle mentor guidance requests.
    
    PROPER: Extracts message from messages list (HumanMessage types)
    and returns AIMessage for response. Uses LLM for dynamic responses.
    """
    log = logging.getLogger("orbit.agent.mentor")

    user_id = state.get("user_id")
    user = state.get("user", {})
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

    user_name = user.get("name", "") if user else ""
    profile_summary = profile.get("profile_summary", "") if profile else ""

    if not user_id or not profile:
        resp = generate_dynamic_response(
            NEEDS_ONBOARDING_PROMPT,
            user_name=user_name or "friend",
            action="get dating advice",
            completeness="incomplete",
        ) or "I need to know you a bit better first to give good advice! Let's finish your profile."
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
            response = generate_dynamic_response(
                MENTOR_INTRO_PROMPT,
                user_name=user_name,
                user_profile=profile_summary,
                message=message,
                has_match="no",
            ) or "I can help with conversation starters! Tell me about who you're trying to message."
        else:
            response = generate_icebreakers(profile, match_profile)

    elif mode == "pre_date":
        if not match_profile:
            response = generate_dynamic_response(
                """You are Orbit. A user wants pre-date advice but you don't know who they're meeting.

User name: {user_name}
Their message: {message}

Ask about the upcoming date to give personalized advice. Be warm and helpful. 1-2 sentences.""",
                user_name=user_name,
                message=message,
            ) or "Tell me about your upcoming date! Where are you going and what do you know about them?"
        else:
            response = provide_pre_date_prep(profile, match_profile, message)

    elif mode == "post_date":
        if not match_profile:
            match_profile = {"profile_summary": "their recent date"}
        response = provide_post_date_debrief(profile, match_profile, message)

    elif mode == "recovery":
        response = provide_recovery_support(profile, message)

    else:  # continuation
        if not match_profile:
            response = generate_dynamic_response(
                MENTOR_INTRO_PROMPT,
                user_name=user_name,
                user_profile=profile_summary,
                message=message,
                has_match="no",
            ) or "I'd love to help! Tell me more about the conversation and who you're talking to."
        else:
            response = provide_conversation_help(profile, match_profile, message)

    # PROPER: Return both messages (for new pattern) and response (for legacy)
    return {"messages": [AIMessage(content=response)], "response": response, "next_node": "save_and_respond"}
