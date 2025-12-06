import logging
from typing import Dict, Any

from ..state import DatingState


log = logging.getLogger("orbit.agent.general")


def general_node(state: DatingState) -> Dict[str, Any]:
    """Handle general conversation."""
    return {
        "response": "I'm your dating wingman! I can help you:\n- Build your profile\n- Find matches\n- Get conversation advice\n\nWhat would you like to do?",
        "next_node": None,
        "db_updates": []
    }
