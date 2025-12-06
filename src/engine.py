import json
import logging
from typing import Any, Dict, Iterable, Optional

from .client import SeriesClient
from .llm import WingmanLLM
from .store import UserStore
from .utils import safe_json, shared_interests


ONBOARDING_QUESTIONS = [
    "Hey! What's your name and one thing you're passionate about?",
    "Describe your ideal weekend vibe in three words.",
    "Any absolute dealbreakers?",
]


def process_event(event: Dict, client: SeriesClient, store: UserStore, llm: WingmanLLM) -> None:
    log = logging.getLogger("orbit.engine")
    parsed = _normalize_event(event, log)
    if not parsed:
        return
    text = parsed["text"]
    from_phone = parsed["from_phone"]
    chat_id = parsed["chat_id"]
    chat_handles = parsed["chat_handles"]

    is_group = len(chat_handles) > 2
    user = store.get_user(from_phone)
    if not user:
        # New user: start onboarding
        store.upsert_user(from_phone, status="ONBOARDING", onboarding_step=0, last_dm_chat_id=chat_id)
        client.set_typing(chat_id)
        client.send_message(chat_id, ONBOARDING_QUESTIONS[0])
        return
    else:
        store.set_last_dm_chat(from_phone, chat_id)

    status = user["status"]
    if is_group:
        handle_group_message(text, chat_id, client, llm)
        return

    if status == "ONBOARDING":
        handle_onboarding(user, text, chat_id, store, client, llm)
        return
    if status == "PENDING_INTRO" and user["current_match_id"]:
        handle_match_decision(user, text, chat_id, store, client)
        return
    if status == "IN_ORBIT":
        handle_sidebar(user, text, chat_id, store, client, llm)
        return
    if status == "BROWSING":
        lower = text.lower()
        if any(token in lower for token in ["yes", "sure", "match", "intro", "find"]):
            try_match(from_phone, chat_id, store, client, llm)
        else:
            client.send_message(chat_id, "Want me to find someone who vibes with you? Say yes to start.")
        return

    # Default private DM behavior
    client.send_message(chat_id, "Got you. Want me to find someone who vibes with you? Reply yes/no.")


def _normalize_event(event: Dict[str, Any], log: logging.Logger) -> Optional[Dict[str, Any]]:
    """
    Accepts a few different payload envelopes and distills the fields we need.

    Supports:
    - {"data": {...}} (canonical)
    - {"data": "<json>"} (stringified payloads)
    - {"data": {"message": {...}, "chat": {...}}} (API-shaped message objects)
    """
    raw_data: Any = event.get("data") or event.get("payload") or {}

    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except Exception:
            log.warning("Skipping event with non-JSON data: %s", raw_data)
            return None

    if not isinstance(raw_data, dict):
        log.warning("Skipping event with unexpected data type: %s", type(raw_data))
        return None

    message_block = raw_data.get("message")
    message_block = message_block if isinstance(message_block, dict) else {}
    chat_message_block = raw_data.get("chat_message")
    chat_message_block = chat_message_block if isinstance(chat_message_block, dict) else {}
    chat_block = raw_data.get("chat")
    chat_block = chat_block if isinstance(chat_block, dict) else {}

    def _first_non_empty(*candidates: Any) -> Optional[Any]:
        for cand in candidates:
            if isinstance(cand, str) and cand.strip():
                return cand
            if cand not in (None, "", []):
                return cand
        return None

    def _normalize_handles(handles: Any) -> list[str]:
        normalized: list[str] = []
        for handle in handles or []:
            if isinstance(handle, dict):
                phone = handle.get("phone_number") or handle.get("handle") or handle.get("id") or handle.get("value")
                if phone:
                    normalized.append(str(phone))
            elif handle:
                normalized.append(str(handle))
        return normalized

    text = (_first_non_empty(raw_data.get("text"), message_block.get("text"), chat_message_block.get("text")) or "").strip()
    from_phone = _first_non_empty(
        raw_data.get("from_phone"),
        message_block.get("from_phone"),
        chat_message_block.get("from_phone"),
        raw_data.get("sent_from"),
        message_block.get("sent_from"),
        chat_message_block.get("sent_from"),
    )
    chat_id = _first_non_empty(
        raw_data.get("chat_id"),
        message_block.get("chat_id"),
        chat_message_block.get("chat_id"),
        chat_block.get("id"),
        (message_block.get("chat") or {}).get("id") if isinstance(message_block.get("chat"), dict) else None,
    )
    chat_handles = _normalize_handles(
        _first_non_empty(
            raw_data.get("chat_handles"),
            chat_block.get("chat_handles"),
            (message_block.get("chat") or {}).get("chat_handles") if isinstance(message_block.get("chat"), dict) else None,
        )
        or [],
    )

    if not from_phone or chat_id is None:
        log.warning("Skipping event missing phone/chat_id: %s", safe_json(event))
        return None

    return {"text": text, "from_phone": from_phone, "chat_id": chat_id, "chat_handles": chat_handles}


def handle_onboarding(user_row, text: str, chat_id: int, store: UserStore, client: SeriesClient, llm: WingmanLLM) -> None:
    phone = user_row["phone_number"]
    step = user_row["onboarding_step"] or 0
    extraction = llm.extract_onboarding(step, text)
    store.update_profile(
        phone,
        name=extraction.get("name"),
        passion=extraction.get("passion"),
        vibe=extraction.get("vibe"),
        dealbreakers=(extraction.get("dealbreakers") or []),
        interests=[extraction.get("passion")] if extraction.get("passion") else [],
    )
    next_step = step + 1
    if next_step < len(ONBOARDING_QUESTIONS):
        store.set_onboarding_step(phone, next_step)
        client.set_typing(chat_id)
        client.send_message(chat_id, ONBOARDING_QUESTIONS[next_step])
        return

    store.set_onboarding_step(phone, next_step)
    store.set_status(phone, "BROWSING")
    client.send_message(chat_id, "Thanks! I’ll keep an eye out for a great match. Want me to start looking now?")
    try_match(phone, chat_id, store, client, llm)


def try_match(phone: str, chat_id: int, store: UserStore, client: SeriesClient, llm: WingmanLLM) -> None:
    user = store.get_user(phone)
    if not user:
        return
    candidates = store.get_browsing_candidates(phone)
    best_candidate = None
    best_overlap: Iterable[str] = []
    for cand in candidates:
        overlap = shared_interests(store.list_shared_interests(phone), store.list_shared_interests(cand["phone_number"]))
        if overlap:
            best_candidate = cand
            best_overlap = overlap
            break
    if not best_candidate:
        client.send_message(chat_id, "I’m still looking for someone with a shared vibe. I’ll ping you soon.")
        return
    match_id = store.create_match(phone, best_candidate["phone_number"], best_overlap, state="proposed")
    store.set_current_match(phone, match_id)
    store.set_current_match(best_candidate["phone_number"], match_id)
    store.set_status(phone, "PENDING_INTRO")
    store.set_status(best_candidate["phone_number"], "PENDING_INTRO")

    pitch_prompt = (
        f"User profile: {user['profile_bio']} | vibe: {user['profile_vibe']} | interests: {user['profile_interests']}\n"
        f"Candidate: {best_candidate['profile_bio']} | vibe: {best_candidate['profile_vibe']} | interests: {best_candidate['profile_interests']}\n"
        f"Shared: {', '.join(best_overlap)}\n"
        "Write one short intro pitch to ask the user if they want an intro."
    )
    pitch = llm.craft_reply(pitch_prompt, temperature=0.6)
    client.send_message(chat_id, f"Found someone who shares {', '.join(best_overlap)}. {pitch} Say yes/no.")

    # Notify candidate if we know their DM chat id
    candidate_chat = best_candidate["last_dm_chat_id"]
    if candidate_chat:
        client.send_message(
            candidate_chat,
            f"Orbit here. I think you and someone else both dig {', '.join(best_overlap)}. Want an intro? Say yes/no.",
        )


def handle_match_decision(user_row, text: str, chat_id: int, store: UserStore, client: SeriesClient) -> None:
    decision = "yes" if text.lower().startswith("y") else "no" if text.lower().startswith("n") else None
    if not decision:
        client.send_message(chat_id, "Can you confirm yes or no for the intro?")
        return
    match_id = user_row["current_match_id"]
    if not match_id:
        client.send_message(chat_id, "I don't have an intro pending. Want me to look for a match?")
        store.set_status(user_row["phone_number"], "BROWSING")
        return
    store.update_match_decision(match_id, user_row["phone_number"], decision)
    match = store.get_match(match_id)
    if not match:
        client.send_message(chat_id, "I lost track of that intro. Mind trying again later?")
        return
    if match["state"] == "declined":
        client.send_message(chat_id, "No worries. I’ll keep looking.")
        other_phone = match["user_b"] if match["user_a"] == user_row["phone_number"] else match["user_a"]
        store.set_status(user_row["phone_number"], "BROWSING")
        store.set_current_match(user_row["phone_number"], None)
        store.set_status(other_phone, "BROWSING")
        store.set_current_match(other_phone, None)
        return
    other_phone = match["user_b"] if match["user_a"] == user_row["phone_number"] else match["user_a"]
    if match["user_a_decision"] == "yes" and match["user_b_decision"] == "yes":
        launch_group_intro(user_row["phone_number"], other_phone, match, store, client)
    else:
        client.send_message(chat_id, "Noted! I’m waiting on the other person.")


def launch_group_intro(user_a: str, user_b: str, match, store: UserStore, client: SeriesClient) -> None:
    user_a_row = store.get_user(user_a)
    user_b_row = store.get_user(user_b)
    if not user_a_row or not user_b_row:
        return
    shared = match["shared_interests"] or ""
    opener = (
        f"Hi! {user_a_row['name'] or user_a}, meet {user_b_row['name'] or user_b}. "
        f"You both vibe on {shared if shared else 'similar interests'}. "
        "Have fun!"
    )
    resp = client.create_group_chat([user_a, user_b], opener, display_name="Connect")
    chat_id = resp.get("chat", {}).get("id") or resp.get("id")
    store.set_group_chat(user_a, chat_id)
    store.set_group_chat(user_b, chat_id)
    store.set_status(user_a, "IN_ORBIT")
    store.set_status(user_b, "IN_ORBIT")
    client.send_message(chat_id, "I’m here if you @Orbit. Otherwise I’ll hang back.")


def handle_sidebar(user_row, text: str, chat_id: int, store: UserStore, client: SeriesClient, llm: WingmanLLM) -> None:
    profile = user_row["profile_bio"] or ""
    interests = user_row["profile_interests"] or ""
    prompt = (
        f"You are Orbit giving a sidebar tip.\nUser profile: {profile}\nInterests: {interests}\n"
        f"User asked: {text}\nGive a short, specific suggestion."
    )
    reply = llm.craft_reply(prompt, temperature=0.8)
    client.send_message(chat_id, reply)


def handle_group_message(text: str, chat_id: int, client: SeriesClient, llm: WingmanLLM) -> None:
    if "@orbit" not in text.lower():
        return
    prompt = (
        "You were tagged in a 3-person chat. Provide a single short reply that nudges conversation forward. "
        f"Message: {text}"
    )
    reply = llm.craft_reply(prompt, temperature=0.8)
    client.send_message(chat_id, reply)
