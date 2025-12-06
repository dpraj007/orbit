"""Router node for intent classification.

PROPER IMPLEMENTATION using LangChain-LangGraph patterns:
- Extracts messages from state using proper message types
- Uses HumanMessage content for intent classification
"""
import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage

from ..prompts import INTENT_CLASSIFICATION_PROMPT
from ..utils.llm import get_llm


def load_context_node(state: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Load user context from database."""
    log = logging.getLogger("orbit.agent.load_context")
    phone = state.get("phone_number")

    if not phone:
        return {"error": "No phone number provided"}

    # Get or create user
    user = db.users.get_by_phone(phone)
    if not user:
        user_id = db.users.create(phone, state.get("chat_id"))
        user = db.users.get_by_id(user_id)
        # Create profile
        db.profiles.create(user_id)

    user_dict = dict(user) if user else None

    # Load profile
    profile = None
    if user:
        profile_row = db.profiles.get_by_user_id(user["id"])
        profile = dict(profile_row) if profile_row else None

    # Load conversation state
    conv_state = None
    if user:
        conv_row = db.conversation_state.get_by_user_id(user["id"])
        conv_state = dict(conv_row) if conv_row else None

    # Load active match if any
    active_match = None
    if conv_state and conv_state.get("match_in_progress"):
        match_row = db.matches.get_by_id(conv_state["match_in_progress"])
        active_match = dict(match_row) if match_row else None

    log.info(
        "Loaded context for user %s: profile=%s, state=%s",
        phone,
        profile is not None,
        conv_state is not None,
    )

    return {
        "user_id": user["id"] if user else None,
        "user": user_dict,
        "profile": profile,
        "conversation_state": conv_state,
        "active_match": active_match,
        "db_updates": [],
    }


def classify_intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Classify user intent.
    
    PROPER: Extracts message from either:
    - state["messages"] (new LangGraph pattern with HumanMessage types)
    - state["message"] (legacy string field for backward compatibility)
    """
    log = logging.getLogger("orbit.agent.router")
    
    # PROPER: Try to get message from messages list first (new pattern)
    message = ""
    messages = state.get("messages", [])
    if messages:
        # Get the last human message from the messages list
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                message = msg.content
                break
    
    # Fallback to legacy message field
    if not message:
        message = state.get("message", "")
    
    user = state.get("user", {})
    conv_state = state.get("conversation_state", {})

    status = user.get("status", "onboarding") if user else "onboarding"
    context = conv_state.get("current_node", "none") if conv_state else "none"
    current_node = context

    # Build prompt
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        status=status, context=context, message=message
    )

    # Call LLM
    llm = get_llm()
    try:
        intent = "general"
        # Map intent based on status / message
        lower_msg = message.lower().strip()
        icebreaker_kw = any(
            kw in lower_msg for kw in ["icebreaker", "ice breaker", "opener", "conversation starter", "start the conversation"]
        )
        has_match_kw = any(kw in lower_msg for kw in ["match", "intro"])
        has_new_match = ("new" in lower_msg and "match" in lower_msg) or lower_msg in {"new match"}
        has_yes_no = (
            "yes" in lower_msg
            or "no" in lower_msg
            or lower_msg in {"y", "yes", "sure", "yeah", "yep", "ok", "okay"}
        )
        wants_advice = any(kw in lower_msg for kw in ["help", "advice", "feedback", "message", "text", "wingman"])

        if status == "onboarding":
            intent = "onboarding"
        elif icebreaker_kw:
            intent = "mentor"
        elif current_node == "connected":
            if has_new_match:
                intent = "matching"
            elif wants_advice:
                intent = "mentor"
            else:
                intent = "general"
        elif has_match_kw or has_new_match or has_yes_no:
            if state.get("active_match") and has_yes_no:
                intent = "match_decision"
            else:
                intent = "matching"
        else:
            intent = "general"

        log.info("Classified intent: %s (status=%s)", intent, status)
        return {"intent": intent, "current_node": "router"}

    except Exception as exc:
        log.error("Intent classification failed: %s", exc)
        return {"intent": "general", "current_node": "router"}


def route_to_node(state: Dict[str, Any]) -> str:
    """Route to appropriate node based on intent."""
    intent = state.get("intent", "general")

    routing_map = {
        "onboarding": "onboarding",
        "matching": "matching",
        "match_decision": "matching",
        "mentor": "mentor",
        "settings": "general",
        "general": "general",
    }

    next_node = routing_map.get(intent, "general")
    logging.getLogger("orbit.agent.router").info(
        "Routing intent '%s' to node '%s'", intent, next_node
    )
    return next_node
