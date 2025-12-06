import json
import logging
from typing import Dict, Any

from ...store import UserStore
from ..state import DatingState


log = logging.getLogger("orbit.agent.load_context")


def load_context_node(state: DatingState, store: UserStore) -> Dict[str, Any]:
    """Load user, profile, and conversation state from database."""
    phone_number = state["phone_number"]
    chat_id = state["chat_id"]

    # Check if user exists
    user = store.get_user_by_phone(phone_number)

    if not user:
        # New user - create them
        log.info(f"Creating new user: {phone_number}")
        user_id = store.create_user(phone_number, chat_id, status="onboarding")
        user = store.get_user_by_id(user_id)

    user_id = user["id"]
    user_dict = dict(user)

    # Load profile
    profile = store.get_profile(user_id)
    profile_dict = dict(profile) if profile else None

    # Load conversation state
    conv_state = store.get_conversation_state(user_id)
    conv_state_dict = None
    if conv_state:
        conv_state_dict = dict(conv_state)
        if conv_state_dict.get("context"):
            try:
                conv_state_dict["context"] = json.loads(conv_state_dict["context"])
            except:
                conv_state_dict["context"] = {}

    # Load active match if any
    active_match = None
    if conv_state_dict and conv_state_dict.get("match_in_progress"):
        match = store.get_match(conv_state_dict["match_in_progress"])
        active_match = dict(match) if match else None

    return {
        "user_id": user_id,
        "user": user_dict,
        "profile": profile_dict,
        "conversation_state": conv_state_dict,
        "active_match": active_match,
        "db_updates": state.get("db_updates", [])
    }
