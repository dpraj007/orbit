"""Matching node with bilateral LLM scoring."""
import json
import logging
import math
from typing import Any, Dict, Optional, Tuple

from ...prompts import BILATERAL_SCORING_PROMPT, MATCH_PITCH_PROMPT
from ...utils.llm import get_llm


def calculate_bilateral_score(
    profile_a: Dict[str, Any], profile_b: Dict[str, Any]
) -> Tuple[float, str]:
    """Calculate bilateral compatibility score using LLM."""
    log = logging.getLogger("orbit.agent.matching")

    llm = get_llm()

    # Score A -> B
    prompt_a_to_b = BILATERAL_SCORING_PROMPT.format(
        profile_a=profile_a.get("profile_summary", "No summary"),
        looking_for_a=profile_a.get("looking_for_summary", "No preferences"),
        profile_b=profile_b.get("profile_summary", "No summary"),
        looking_for_b=profile_b.get("looking_for_summary", "No preferences"),
    )

    try:
        result_a = llm.invoke(prompt_a_to_b)
        content_a = result_a.content if hasattr(result_a, "content") else str(result_a)
        # Extract JSON from content
        score_data_a = json.loads(content_a)
        score_a_to_b = float(score_data_a.get("score", 50))
        reason_a = score_data_a.get("reason", "")
    except Exception as exc:
        log.warning("Score A->B failed: %s", exc)
        score_a_to_b = 50.0
        reason_a = "Unable to calculate"

    # Score B -> A
    prompt_b_to_a = BILATERAL_SCORING_PROMPT.format(
        profile_a=profile_b.get("profile_summary", "No summary"),
        looking_for_a=profile_b.get("looking_for_summary", "No preferences"),
        profile_b=profile_a.get("profile_summary", "No summary"),
        looking_for_b=profile_a.get("looking_for_summary", "No preferences"),
    )

    try:
        result_b = llm.invoke(prompt_b_to_a)
        content_b = result_b.content if hasattr(result_b, "content") else str(result_b)
        score_data_b = json.loads(content_b)
        score_b_to_a = float(score_data_b.get("score", 50))
        reason_b = score_data_b.get("reason", "")
    except Exception as exc:
        log.warning("Score B->A failed: %s", exc)
        score_b_to_a = 50.0
        reason_b = "Unable to calculate"

    # Calculate geometric mean
    bilateral_score = math.sqrt(score_a_to_b * score_b_to_a)
    reason = f"A→B: {reason_a} | B→A: {reason_b}"

    log.info(
        "Bilateral score: %.2f (A->B: %.2f, B->A: %.2f)",
        bilateral_score,
        score_a_to_b,
        score_b_to_a,
    )

    return bilateral_score, reason


def find_best_match(user_id: int, user_profile: Dict[str, Any], db: Any) -> Optional[Tuple[int, float, str]]:
    """Find the best match for a user."""
    log = logging.getLogger("orbit.agent.matching")

    # Get candidates
    candidates = db.matches.get_candidates_for_user(user_id)

    if not candidates:
        log.info("No candidates found for user %d", user_id)
        return None

    best_candidate = None
    best_score = 0.0
    best_reason = ""

    # Score each candidate
    for candidate in candidates[:5]:  # Limit to top 5 to save API calls
        candidate_dict = dict(candidate)
        score, reason = calculate_bilateral_score(user_profile, candidate_dict)

        if score > best_score and score >= 60.0:  # Threshold
            best_score = score
            best_candidate = candidate_dict
            best_reason = reason

    if best_candidate:
        log.info("Best match found: user %d with score %.2f", best_candidate["user_id"], best_score)
        return best_candidate["user_id"], best_score, best_reason

    return None


def generate_match_pitch(
    user_profile: Dict[str, Any], match_profile: Dict[str, Any], score: float, reason: str
) -> str:
    """Generate an anonymized match pitch."""
    llm = get_llm()

    prompt = MATCH_PITCH_PROMPT.format(
        user_profile=user_profile.get("profile_summary", ""),
        match_profile=match_profile.get("profile_summary", ""),
        score=score,
        highlights=reason,
    )

    try:
        result = llm.invoke(prompt)
        pitch = result.content if hasattr(result, "content") else str(result)
        return pitch.strip()
    except Exception as exc:
        logging.getLogger("orbit.agent.matching").error("Pitch generation failed: %s", exc)
        return "I found someone who might be a great match for you based on shared values and interests."


def matching_node(state: Dict[str, Any], db: Any) -> Dict[str, Any]:
    """Handle matching flow."""
    log = logging.getLogger("orbit.agent.matching")

    user = state.get("user", {})
    profile = state.get("profile", {})
    message = state.get("message", "").lower()
    user_id = state.get("user_id")
    active_match = state.get("active_match")

    if not user_id or not profile:
        return {"response": "I need to get to know you better first. Let's finish onboarding!"}

    # Check if this is a match decision
    if active_match:
        # Handle decision
        decision = "yes" if message.startswith("y") else "no" if message.startswith("n") else None

        if not decision:
            return {"response": "Can you confirm yes or no for this match?"}

        # Update match decision
        match_id = active_match["id"]
        updated_match = db.matches.update_decision(match_id, user_id, decision)

        if decision == "no":
            # They declined
            db.conversation_state.upsert(user_id, current_node="active", match_in_progress=None)
            response = "No worries! I'll keep looking for someone who's the right fit."
            return {"response": response, "next_node": "save_and_respond"}

        # They said yes
        if updated_match["status"] == "mutual":
            # Mutual match!
            other_user_id = (
                updated_match["user_b_id"]
                if updated_match["user_a_id"] == user_id
                else updated_match["user_a_id"]
            )

            # Get other user info
            other_user = db.users.get_by_id(other_user_id)
            other_profile = db.profiles.get_by_user_id(other_user_id)

            user_name = user.get("name", "someone")
            other_name = other_user["name"] if other_user else "your match"

            response = (
                f"Great news! It's a mutual match with {other_name}! "
                f"I'll introduce you both now. Have fun connecting!"
            )

            # Create group chat (will be handled in save_and_respond)
            db.conversation_state.upsert(user_id, current_node="connected", match_in_progress=None)

            return {
                "response": response,
                "next_node": "save_and_respond",
                "db_updates": [
                    {
                        "type": "create_group",
                        "user_a_id": user_id,
                        "user_b_id": other_user_id,
                        "user_a_name": user_name,
                        "user_b_name": other_name,
                    }
                ],
            }
        else:
            # Waiting for other person
            response = "Noted! I'm waiting to hear from them. I'll let you know when they respond."
            return {"response": response, "next_node": "save_and_respond"}

    # Not a decision - find a new match
    log.info("Finding new match for user %d", user_id)

    match_result = find_best_match(user_id, profile, db)

    if not match_result:
        response = "I'm still looking for someone with the right vibe. I'll ping you when I find a great match!"
        return {"response": response, "next_node": "save_and_respond"}

    match_user_id, score, reason = match_result

    # Create match in database
    match_id = db.matches.create(user_id, match_user_id, score)

    # Get match profile
    match_profile = db.profiles.get_by_user_id(match_user_id)
    match_profile_dict = dict(match_profile) if match_profile else {}

    # Generate pitch
    pitch = generate_match_pitch(profile, match_profile_dict, score, reason)

    response = f"{pitch}\n\nWant an intro? Reply yes or no."

    # Update conversation state
    db.conversation_state.upsert(user_id, current_node="match_decision", match_in_progress=match_id)

    # Notify the match candidate too
    match_user = db.users.get_by_id(match_user_id)
    if match_user and match_user.get("chat_id"):
        match_pitch_for_them = generate_match_pitch(match_profile_dict, profile, score, reason)
        match_response = f"{match_pitch_for_them}\n\nInterested? Reply yes or no."

        db.conversation_state.upsert(
            match_user_id, current_node="match_decision", match_in_progress=match_id
        )

        return {
            "response": response,
            "next_node": "save_and_respond",
            "db_updates": [
                {
                    "type": "notify_match",
                    "chat_id": match_user["chat_id"],
                    "message": match_response,
                }
            ],
        }

    return {"response": response, "next_node": "save_and_respond"}
