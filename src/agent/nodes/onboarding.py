import json
import logging
from typing import Dict, Any

from ...prompts.onboarding import ONBOARDING_QUESTIONS, get_extraction_prompt
from ...store import UserStore
from ..state import DatingState


log = logging.getLogger("orbit.agent.onboarding")


def onboarding_node(state: DatingState, store: UserStore, llm) -> Dict[str, Any]:
    """Handle onboarding flow and build natural language profile."""
    user_id = state["user_id"]
    profile = state.get("profile", {}) or {}
    message = state["message"]

    step = profile.get("onboarding_step", 0)
    current_summary = profile.get("profile_summary", "")
    current_looking_for = profile.get("looking_for_summary", "")

    # Extract information from user's response using LLM
    try:
        prompt = get_extraction_prompt(step, message, current_summary, current_looking_for)
        extraction_json = llm.extract_profile_info(prompt)
        extraction = json.loads(extraction_json) if isinstance(extraction_json, str) else extraction_json
        log.info(f"Extracted profile info: {extraction}")
    except Exception as e:
        log.error(f"Profile extraction failed: {e}")
        extraction = {}

    # Update profile with extracted information
    profile_updates = {}

    if extraction.get("name"):
        store.update_user(user_id, name=extraction["name"])

    if extraction.get("profile_summary"):
        profile_updates["profile_summary"] = extraction["profile_summary"]

    if extraction.get("looking_for_summary"):
        profile_updates["looking_for_summary"] = extraction["looking_for_summary"]

    if extraction.get("relationship_goal"):
        profile_updates["relationship_goal"] = extraction["relationship_goal"]

    if extraction.get("communication_style"):
        profile_updates["communication_style"] = extraction["communication_style"]

    if extraction.get("interests"):
        profile_updates["interests"] = ", ".join(extraction["interests"])

    if extraction.get("dealbreakers"):
        profile_updates["dealbreakers"] = ", ".join(extraction["dealbreakers"])

    # Move to next step
    next_step = step + 1
    profile_updates["onboarding_step"] = next_step

    # Calculate completeness
    total_steps = len(ONBOARDING_QUESTIONS)
    profile_updates["completeness"] = min(1.0, next_step / (total_steps - 1))

    # Update profile in database
    store.update_profile(user_id, **profile_updates)

    # Determine next action
    if next_step < total_steps:
        # Continue onboarding
        response = ONBOARDING_QUESTIONS[next_step]
        return {
            "response": response,
            "next_node": None,
            "db_updates": []
        }
    else:
        # Onboarding complete
        store.update_user(user_id, status="browsing")
        store.upsert_conversation_state(user_id, "browsing", {})
        response = "Thanks! I'll start looking for great matches. Want me to find someone now?"
        return {
            "response": response,
            "next_node": None,
            "db_updates": []
        }
