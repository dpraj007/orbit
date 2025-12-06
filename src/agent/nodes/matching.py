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

    # Quick path: if user says yes, auto-intro fallback match immediately (demo)
    conv_state = state.get("conversation_state") or {}
    if "yes" in message and conv_state.get("current_node") != "connected":
        # Ensure fallback exists
        fallback = db.users.get_by_phone("+15555550123")
        if not fallback:
            fallback_id = db.users.create("+15555550123", None, name="Donald")
            db.profiles.create(fallback_id)
            db.profiles.update_summary(
                fallback_id,
                "Easygoing, loves kayaking and cartoons. Down-to-earth and keeps things light. Great with dad jokes.",
                1.0,
            )
            db.profiles.update_field(fallback_id, "looking_for_summary", "Fun, kind people who like to laugh.")
            fallback = db.users.get_by_phone("+15555550123")

        match_user_id = fallback["id"]
        score = 75.0
        reason = "Good vibe and lighthearted energy."
        match_profile = db.profiles.get_by_user_id(match_user_id)
        match_profile_dict = dict(match_profile) if match_profile else {}
        pitch = generate_match_pitch(profile, match_profile_dict, score, reason)

        match_id = db.matches.create(user_id, match_user_id, score)
        db.matches.force_mutual(match_id)
        db.conversation_state.upsert(user_id, current_node="connected", match_in_progress=None)
        db.conversation_state.upsert(match_user_id, current_node="connected", match_in_progress=None)

        return {
            "response": f"{pitch}\n\nGreat news! I’m introducing you now.",
            "next_node": "save_and_respond",
            "db_updates": [
                {
                    "type": "create_group",
                    "user_a_id": user_id,
                    "user_b_id": match_user_id,
                    "user_a_name": user.get("name", "You"),
                    "user_b_name": fallback["name"],
                }
            ],
        }

    # If already connected, don't loop the prompt
    if conv_state.get("current_node") == "connected":
        # Pass through to mentor/help if user asks for advice
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in ["help", "advice", "feedback", "what do you think", "message", "text"]):
            return {"response": "I can help you refine that. Tell me what you want to improve, or paste the message and I'll suggest tweaks.", "next_node": "mentor"}
        return {"response": "You're already matched. Say 'new match' if you want me to look again."}

    # Check if this is a match decision
    if active_match:
        # Handle decision
        if "who" in message and len(message.strip()) <= 8:
            # Give a quick teaser about the current match
            other_user_id = (
                active_match["user_b_id"]
                if active_match["user_a_id"] == user_id
                else active_match["user_a_id"]
            )
            other_profile = db.profiles.get_by_user_id(other_user_id)
            pitch = generate_match_pitch(profile, dict(other_profile or {}), active_match.get("bilateral_score", 70), "Good vibe match.")
            return {"response": f"I've got someone lined up. Quick teaser: {pitch}\n\nReady to meet? Reply yes or no."}

        decision = "yes" if message.startswith("y") else "no" if message.startswith("n") else None

        if not decision:
            return {"response": "I’ve got a match ready. Say yes to meet now or no to skip. Ask “who?” for a quick teaser."}

        # Update match decision
        match_id = active_match["id"]
        if decision == "no":
            db.matches.update_decision(match_id, user_id, decision)
            db.conversation_state.upsert(user_id, current_node="active", match_in_progress=None)
            response = "No worries! I'll keep looking for someone who's the right fit."
            return {"response": response, "next_node": "save_and_respond"}

        # They said yes: force mutual and intro immediately
        db.matches.force_mutual(match_id)
        other_user_id = (
            active_match["user_b_id"]
            if active_match["user_a_id"] == user_id
            else active_match["user_a_id"]
        )
        other_user = db.users.get_by_id(other_user_id)
        other_name = other_user["name"] if other_user else "your match"
        user_name = user.get("name", "you")

        db.conversation_state.upsert(user_id, current_node="connected", match_in_progress=None)
        if other_user:
            db.conversation_state.upsert(other_user_id, current_node="connected", match_in_progress=None)

        response = f"Great news! I’m introducing you to {other_name} now. Have fun!"
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

    # Not a decision - find a new match
    log.info("Finding new match for user %d", user_id)

    match_result = find_best_match(user_id, profile, db)

    is_fallback = False
    if not match_result:
        # Fallback: use a warm preset match (Donald)
        is_fallback = True
        fallback = db.users.get_by_phone("+15555550123")
        if not fallback:
            fallback_id = db.users.create("+15555550123", None, name="Donald")
            db.profiles.create(fallback_id)
            db.profiles.update_summary(
                fallback_id,
                "Easygoing, loves kayaking and cartoons. Down-to-earth and keeps things light.",
                1.0,
            )
            db.profiles.update_field(fallback_id, "looking_for_summary", "Fun, kind people who like to laugh.")
            fallback = db.users.get_by_phone("+15555550123")
        match_user_id = fallback["id"]
        score = 75.0
        reason = "Good vibe and lighthearted energy."
    else:
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

    # If fallback, auto-approve and create group immediately
    if is_fallback:
        db.matches.force_mutual(match_id)
        db.conversation_state.upsert(user_id, current_node="connected", match_in_progress=None)
        match_user = db.users.get_by_id(match_user_id)
        return {
            "response": f"{pitch}\n\nGreat news—I'm introducing you now.",
            "next_node": "save_and_respond",
            "db_updates": [
                {
                    "type": "create_group",
                    "user_a_id": user_id,
                    "user_b_id": match_user_id,
                    "user_a_name": user.get('name', 'You'),
                    "user_b_name": match_user['name'] if match_user else 'your match',
                }
            ],
        }

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
