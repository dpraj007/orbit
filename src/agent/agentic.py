"""Lightweight agentic handler using LLM + deterministic shortcuts for demo."""
import json
import logging
from typing import Any, Dict, Optional

from ..prompts.agent import AGENT_PROMPT, MENTOR_PROMPT
from ..utils.llm import get_llm


def summarize_profile(profile: Optional[Dict[str, Any]]) -> str:
    if not profile:
        return "No profile yet."
    return profile.get("profile_summary") or "No profile summary yet."


def run_agent(
    message: str,
    context: Dict[str, Any],
    db: Any,
    api: Any,
    fallback_phone: str = "+15555550123",
) -> Dict[str, Any]:
    """Agent entrypoint. Returns {response, db_updates}."""
    log = logging.getLogger("orbit.agentic")
    user = context.get("user") or {}
    profile = context.get("profile") or {}
    conv_state = context.get("conversation_state") or {}
    active_match = context.get("active_match")
    connected = conv_state.get("current_node") == "connected"

    msg_lower = message.lower().strip()

    # Hard shortcut: if user explicitly wants a new match or says yes, auto intro fallback
    wants_match = any(kw in msg_lower for kw in ["match", "intro", "connect"]) or msg_lower in {"y", "yes", "sure", "yeah", "ok", "okay"}
    if wants_match and not connected:
        log.info("Agentic: auto-intro fallback")
        return auto_intro_fallback(user, profile, db, fallback_phone)

    # If connected, handle mentor/help and avoid re-pitching
    wants_help = any(kw in msg_lower for kw in ["help", "advice", "feedback", "message", "text", "wingman"])
    if connected and wants_help:
        return {"response": mentor_response(message, profile), "db_updates": []}
    if connected:
        return {"response": "You're already matched. Say 'new match' if you want me to look again.", "db_updates": []}

    # Otherwise, use LLM for a natural, concise reply with tool hints
    llm = get_llm(temperature=0.4)
    prompt = AGENT_PROMPT.format(
        user_name=user.get("name") or "there",
        status=user.get("status", "active"),
        profile=summarize_profile(profile),
        message=message,
    )
    try:
        result = llm.invoke(prompt)
        text = result.content if hasattr(result, "content") else str(result)
        # Try to parse JSON {response: "..."} if present
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, dict) and parsed.get("response"):
            text = parsed["response"]
    except Exception as exc:
        log.warning("Agentic LLM failed: %s", exc)
        text = "Got it! Let me know if you want me to set up an intro or give feedback."

    return {"response": text, "db_updates": []}


def auto_intro_fallback(user: Dict[str, Any], profile: Dict[str, Any], db: Any, fallback_phone: str) -> Dict[str, Any]:
    """Create or reuse a fallback match and auto-intro."""
    user_id = user.get("id") or user.get("user_id") or user.get("pk") or None
    if not user_id:
        return {"response": "I need a user on file before I can introduce you.", "db_updates": []}

    fallback = db.users.get_by_phone(fallback_phone)
    if not fallback:
        fb_id = db.users.create(fallback_phone, None, name="Donald")
        db.profiles.create(fb_id)
        db.profiles.update_summary(
            fb_id,
            "Easygoing, loves kayaking and cartoons. Down-to-earth and keeps things light. Great with dad jokes.",
            1.0,
        )
        db.profiles.update_field(fb_id, "looking_for_summary", "Fun, kind people who like to laugh.")
        fallback = db.users.get_by_phone(fallback_phone)
    match_user_id = fallback["id"]
    score = 75.0
    reason = "Good vibe and lighthearted energy."
    match_profile = db.profiles.get_by_user_id(match_user_id)
    match_profile_dict = dict(match_profile) if match_profile else {}

    # Create match and force mutual
    match_id = db.matches.create(user_id, match_user_id, score)
    db.matches.force_mutual(match_id)
    db.conversation_state.upsert(user_id, current_node="connected", match_in_progress=None)
    db.conversation_state.upsert(match_user_id, current_node="connected", match_in_progress=None)

    pitch = (
        "I found someone who matches your vibe—lighthearted and easygoing, into kayaking and cartoons. "
        "Wants fun, kind chats with low drama."
    )
    return {
        "response": f"{pitch}\n\nGreat news! I’m introducing you now.",
        "db_updates": [
            {
                "type": "create_group",
                "user_a_id": user_id,
                "user_b_id": match_user_id,
                "user_a_name": user.get("name", "You"),
                "user_b_name": fallback["name"],
            }
        ],
        "set_connected_ids": [user_id, match_user_id],
    }


def mentor_response(message: str, profile: Dict[str, Any]) -> str:
    llm = get_llm(temperature=0.5)
    prompt = MENTOR_PROMPT.format(profile=summarize_profile(profile), message=message)
    try:
        result = llm.invoke(prompt)
        return result.content if hasattr(result, "content") else str(result)
    except Exception:
        return "Here’s a quick tweak: make it personal and light. Ask a small question to keep it flowing."
