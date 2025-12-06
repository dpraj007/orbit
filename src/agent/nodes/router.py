import logging
from typing import Dict, Any

from ...prompts.router import get_intent_prompt
from ..state import DatingState


log = logging.getLogger("orbit.agent.router")


def classify_intent_node(state: DatingState, llm) -> Dict[str, Any]:
    """Classify user intent to route to appropriate node."""
    message = state["message"]
    user = state.get("user", {})
    conv_state = state.get("conversation_state", {})

    status = user.get("status", "") if user else ""
    current_node = conv_state.get("current_node", "") if conv_state else ""

    # Simple rule-based routing for common cases
    message_lower = message.lower().strip()

    # If user is in onboarding status
    if status == "onboarding":
        return {"intent": "onboarding"}

    # If waiting for match decision
    if status == "pending_intro" or current_node == "match_decision":
        if any(word in message_lower for word in ["yes", "yeah", "sure", "y", "no", "n", "nah", "nope"]):
            return {"intent": "match_decision"}

    # If asking for help or advice
    if any(word in message_lower for word in ["help", "advice", "what should", "how do", "icebreaker", "opener", "suggest"]):
        return {"intent": "mentor"}

    # If requesting match
    if any(word in message_lower for word in ["match", "find someone", "looking", "meet"]):
        return {"intent": "matching"}

    # Use LLM for ambiguous cases
    try:
        prompt = get_intent_prompt(message, status, current_node)
        intent = llm.classify_intent(prompt)
        log.info(f"Classified intent: {intent}")
        return {"intent": intent}
    except Exception as e:
        log.error(f"Intent classification failed: {e}")
        return {"intent": "general"}


def route_by_intent(state: DatingState) -> str:
    """Route to appropriate node based on intent."""
    intent = state.get("intent", "general")

    if intent == "onboarding":
        return "onboarding"
    elif intent == "match_decision":
        return "matching"
    elif intent == "mentor":
        return "mentor"
    elif intent == "matching":
        return "matching"
    else:
        return "general"
