import logging
from typing import Dict, Any

from ...prompts.mentor import get_icebreaker_prompt, get_conversation_help_prompt
from ...store import UserStore
from ..state import DatingState


log = logging.getLogger("orbit.agent.mentor")


def mentor_node(state: DatingState, store: UserStore, llm) -> Dict[str, Any]:
    """Provide dating advice and mentorship."""
    user_id = state["user_id"]
    profile = state.get("profile", {})
    message = state["message"]
    active_match = state.get("active_match")

    message_lower = message.lower().strip()

    # Check what kind of help they need
    if any(word in message_lower for word in ["icebreaker", "opener", "first message", "what should i say"]):
        return generate_icebreakers(state, store, llm)

    elif any(word in message_lower for word in ["conversation", "continue", "help", "advice", "stuck"]):
        return provide_conversation_help(state, store, llm)

    else:
        # General mentor response
        return {
            "response": "I can help with icebreakers or conversation advice. What would you like?",
            "next_node": None,
            "db_updates": []
        }


def generate_icebreakers(state: DatingState, store: UserStore, llm) -> Dict[str, Any]:
    """Generate icebreaker suggestions for a match."""
    user_id = state["user_id"]
    profile = state.get("profile", {})
    active_match = state.get("active_match")

    if not active_match or active_match.get("status") != "mutual":
        return {
            "response": "You need an active match first! Want me to find someone?",
            "next_node": None,
            "db_updates": []
        }

    # Get match's profile
    match_user_id = active_match["user_b_id"] if active_match["user_a_id"] == user_id else active_match["user_a_id"]
    match_profile = store.get_profile(match_user_id)

    if not match_profile:
        return {
            "response": "I don't have enough info about your match yet.",
            "next_node": None,
            "db_updates": []
        }

    # Generate icebreakers
    try:
        prompt = get_icebreaker_prompt(
            profile.get("profile_summary", ""),
            match_profile.get("profile_summary", "")
        )
        icebreakers = llm.generate_text(prompt)
        response = f"Here are some conversation starters:\n\n{icebreakers}\n\nWhich feels most like you?"
    except Exception as e:
        log.error(f"Icebreaker generation failed: {e}")
        response = "Having trouble generating openers. Try asking about their interests!"

    return {
        "response": response,
        "next_node": None,
        "db_updates": []
    }


def provide_conversation_help(state: DatingState, store: UserStore, llm) -> Dict[str, Any]:
    """Provide advice for continuing a conversation."""
    user_id = state["user_id"]
    profile = state.get("profile", {})
    message = state["message"]
    active_match = state.get("active_match")

    if not active_match:
        return {
            "response": "Want me to find you a match first?",
            "next_node": None,
            "db_updates": []
        }

    # Get match's profile
    match_user_id = active_match["user_b_id"] if active_match["user_a_id"] == user_id else active_match["user_a_id"]
    match_profile = store.get_profile(match_user_id)

    # Generate advice
    try:
        prompt = get_conversation_help_prompt(
            profile.get("profile_summary", ""),
            match_profile.get("profile_summary", "") if match_profile else "",
            message
        )
        advice = llm.generate_text(prompt)
    except Exception as e:
        log.error(f"Conversation help failed: {e}")
        advice = "Ask about their interests and share your own stories. Be genuine and curious!"

    return {
        "response": advice,
        "next_node": None,
        "db_updates": []
    }
