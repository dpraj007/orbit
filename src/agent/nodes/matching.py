import json
import logging
import math
from typing import Dict, Any, Optional

from ...prompts.matching import get_compatibility_prompt, get_pitch_prompt, get_intro_prompt
from ...store import UserStore
from ..state import DatingState


log = logging.getLogger("orbit.agent.matching")


def matching_node(state: DatingState, store: UserStore, llm, client) -> Dict[str, Any]:
    """Handle matching flow with bilateral scoring."""
    user_id = state["user_id"]
    user = state["user"]
    profile = state["profile"]
    message = state["message"]
    active_match = state.get("active_match")
    conv_state = state.get("conversation_state", {})

    message_lower = message.lower().strip()

    # Check if responding to match decision
    if active_match and active_match.get("status") in ["pending_a", "pending_b"]:
        return handle_match_decision(state, store, llm, client)

    # Check if requesting new match
    if any(word in message_lower for word in ["yes", "sure", "find", "match", "looking"]):
        return find_and_suggest_match(state, store, llm)

    return {
        "response": "Want me to find someone who vibes with you? Say yes to start.",
        "next_node": None,
        "db_updates": []
    }


def handle_match_decision(state: DatingState, store: UserStore, llm, client) -> Dict[str, Any]:
    """Handle user's decision on a match suggestion."""
    user_id = state["user_id"]
    user = state["user"]
    message = state["message"]
    active_match = state["active_match"]

    message_lower = message.lower().strip()

    # Determine decision
    if message_lower.startswith("y") or "yes" in message_lower or "sure" in message_lower:
        decision = "yes"
    elif message_lower.startswith("n") or "no" in message_lower or "pass" in message_lower:
        decision = "no"
    else:
        return {
            "response": "Can you confirm yes or no for the intro?",
            "next_node": None,
            "db_updates": []
        }

    match_id = active_match["id"]
    store.update_match_decision(match_id, user_id, decision)

    # Reload match to see updated status
    match = store.get_match(match_id)
    if not match:
        return {
            "response": "Something went wrong. Let me find you another match.",
            "next_node": None,
            "db_updates": []
        }

    if match["status"] == "rejected":
        # Match declined
        store.update_user(user_id, status="browsing")
        store.upsert_conversation_state(user_id, "browsing", {}, None)
        return {
            "response": "No worries! I'll keep looking for someone great.",
            "next_node": None,
            "db_updates": []
        }

    elif match["status"] == "mutual":
        # Both said yes! Create intro
        return create_mutual_intro(state, match, store, llm, client)

    else:
        # Waiting on other person
        store.upsert_conversation_state(user_id, "match_decision", {"waiting": True}, match_id)
        return {
            "response": "Noted! I'm waiting on the other person. I'll let you know when they respond.",
            "next_node": None,
            "db_updates": []
        }


def find_and_suggest_match(state: DatingState, store: UserStore, llm) -> Dict[str, Any]:
    """Find and suggest a bilateral match."""
    user_id = state["user_id"]
    user = state["user"]
    profile = state["profile"]

    if not profile or not profile.get("profile_summary"):
        return {
            "response": "I need to know more about you first. Let's finish your profile!",
            "next_node": None,
            "db_updates": []
        }

    # Get browsing candidates
    candidates = store.get_browsing_users(user_id)

    if not candidates:
        return {
            "response": "I'm still looking for someone with a shared vibe. I'll ping you soon!",
            "next_node": None,
            "db_updates": []
        }

    # Calculate bilateral scores
    best_match = None
    best_score = 0

    for candidate in candidates:
        try:
            score = calculate_bilateral_score(profile, candidate, llm)
            if score > best_score:
                best_score = score
                best_match = candidate
        except Exception as e:
            log.error(f"Error calculating score for candidate: {e}")

    if not best_match or best_score < 40:  # Threshold
        return {
            "response": "I'm still looking for someone who's a great fit. Check back soon!",
            "next_node": None,
            "db_updates": []
        }

    # Create match record
    match_id = store.create_match(user_id, best_match["id"], best_score, status="pending_a")

    # Generate anonymized pitch
    try:
        pitch_prompt = get_pitch_prompt(best_match["profile_summary"])
        pitch = llm.generate_text(pitch_prompt)
    except Exception as e:
        log.error(f"Pitch generation failed: {e}")
        pitch = "I found someone interesting who shares your vibe."

    # Update conversation state
    store.upsert_conversation_state(user_id, "match_decision", {}, match_id)
    store.update_user(user_id, status="pending_intro")

    response = f"Found a match! {pitch}\n\nInterested? Say yes or no."

    return {
        "response": response,
        "next_node": None,
        "db_updates": []
    }


def calculate_bilateral_score(profile_a: Dict, profile_b: Dict, llm) -> float:
    """Calculate bilateral compatibility score using geometric mean."""
    try:
        # Score A -> B
        prompt_a_to_b = get_compatibility_prompt(
            profile_a.get("profile_summary", ""),
            profile_a.get("looking_for_summary", ""),
            profile_b.get("profile_summary", ""),
            profile_b.get("looking_for_summary", "")
        )
        result_a_to_b = llm.generate_json(prompt_a_to_b)
        score_a_to_b = result_a_to_b.get("score", 0)

        # Score B -> A
        prompt_b_to_a = get_compatibility_prompt(
            profile_b.get("profile_summary", ""),
            profile_b.get("looking_for_summary", ""),
            profile_a.get("profile_summary", ""),
            profile_a.get("looking_for_summary", "")
        )
        result_b_to_a = llm.generate_json(prompt_b_to_a)
        score_b_to_a = result_b_to_a.get("score", 0)

        # Geometric mean
        bilateral_score = math.sqrt(score_a_to_b * score_b_to_a)
        log.info(f"Bilateral score: {bilateral_score} (A->B: {score_a_to_b}, B->A: {score_b_to_a})")
        return bilateral_score

    except Exception as e:
        log.error(f"Bilateral score calculation failed: {e}")
        return 0.0


def create_mutual_intro(state: DatingState, match: Dict, store: UserStore, llm, client) -> Dict[str, Any]:
    """Create introduction for mutual match."""
    user_a_id = match["user_a_id"]
    user_b_id = match["user_b_id"]

    user_a = store.get_user_by_id(user_a_id)
    user_b = store.get_user_by_id(user_b_id)
    profile_a = store.get_profile(user_a_id)
    profile_b = store.get_profile(user_b_id)

    # Generate intro message
    try:
        intro_prompt = get_intro_prompt(
            user_a["name"] or user_a["phone_number"],
            profile_a.get("profile_summary", ""),
            user_b["name"] or user_b["phone_number"],
            profile_b.get("profile_summary", ""),
            profile_a.get("interests", "")
        )
        intro_message = llm.generate_text(intro_prompt)
    except Exception as e:
        log.error(f"Intro generation failed: {e}")
        intro_message = f"Hi! {user_a['name']}, meet {user_b['name']}. You both seem like a great match!"

    # Create group chat
    try:
        resp = client.create_group_chat(
            [user_a["phone_number"], user_b["phone_number"]],
            intro_message,
            display_name="Match"
        )
        log.info(f"Created group chat: {resp}")
    except Exception as e:
        log.error(f"Group chat creation failed: {e}")

    # Update both users
    store.update_user(user_a_id, status="in_match")
    store.update_user(user_b_id, status="in_match")
    store.upsert_conversation_state(user_a_id, "in_match", {}, match["id"])
    store.upsert_conversation_state(user_b_id, "in_match", {}, match["id"])

    return {
        "response": f"Great! I've connected you both. Check your group chat!",
        "next_node": None,
        "db_updates": []
    }
