"""Fast-path orchestrator to demo the Leon -> Dhairyasheel intro flow."""
import logging
import time
from typing import Callable, Dict, List, Optional

from .api import SeriesAPI
from .config import Config
from .db import Database
from .utils import get_llm, setup_logger

LEON_PHONE = "+16479165156"
DHAIRYA_PHONE = "+19298776648"
LEON_CHAT_DEFAULT = 1701689
DHAIRYA_CHAT_DEFAULT = 1701723


def send_with_typing(api: SeriesAPI, chat_id: int, text: str, delay: float = 1.2) -> None:
    """Send a message with a short typing indicator."""
    try:
        api.start_typing(chat_id)
    except Exception:
        pass
    time.sleep(delay)
    api.send_message(chat_id, text)


def ensure_tester_profiles(db: Database) -> None:
    """Seed Leon and Dhairyasheel with basic profiles if missing."""
    now = time.time()
    for phone, name, summary, looking in [
        (LEON_PHONE, "Leon", "Builder and tester trying Orbit; enjoys hiking and cooking.", "Curious, kind people"),
        (
            DHAIRYA_PHONE,
            "Dhairyasheel",
            "Product-minded, loves good coffee and long walks. Reads sci-fi.",
            "Thoughtful, playful conversations",
        ),
    ]:
        user = db.users.get_by_phone(phone)
        if not user:
            user_id = db.users.create(phone, None, name=name)
            db.profiles.create(user_id)
            db.profiles.update_summary(user_id, summary, 1.0)
            db.profiles.update_field(user_id, "looking_for_summary", looking)
            db.users.update_status(user_id, "active" if phone == DHAIRYA_PHONE else "onboarding")
        else:
            # Make sure profiles exist
            profile = db.profiles.get_by_user_id(user["id"])
            if not profile:
                db.profiles.create(user["id"])
                db.profiles.update_summary(user["id"], summary, 1.0)
                db.profiles.update_field(user["id"], "looking_for_summary", looking)


def fetch_new_messages(api: SeriesAPI, chat_id: int, last_id: int, log=None, last_count: int = 0) -> tuple:
    """Fetch new messages, using ID scanning if the count increased.
    
    Returns (messages, new_count) where new_count is the updated message count.
    """
    # First check if message count increased (fast check)
    current_count = api.get_chat_message_count(chat_id)
    
    # Try the list endpoint first
    messages = api.get_messages(chat_id, limit=100)
    max_list_id = max((m.get("id", 0) for m in messages), default=0)
    
    fresh = [m for m in messages if isinstance(m.get("id"), int) and m["id"] > last_id]
    
    # If count increased but we didn't find new messages in list, scan for them
    if current_count > last_count and not fresh and last_id > 0:
        if log:
            log.info("Count increased %d->%d but list stale, scanning from ID %d...", 
                     last_count, current_count, last_id)
        scanned = api.scan_for_new_messages(chat_id, last_id, max_scan=10000)
        fresh = [m for m in scanned if m.get("id", 0) > last_id]
        if log and fresh:
            log.info("Scan found %d new messages!", len(fresh))
    
    return sorted(fresh, key=lambda m: m["id"]), current_count


def _pick_leon_chat(api: SeriesAPI, log) -> Optional[int]:
    """Pick the most relevant 1:1 chat with Leon by scanning chats filtered by phone.
    Prefers non-group chats and the one with the highest message_count (proxy for recency).
    """
    try:
        chats = api.list_chats(phone_number=LEON_PHONE, per_page=50)
        if not chats:
            return None
        # Prefer DMs, then highest message_count, then highest id
        def score(c):
            return (
                0 if not c.get("group") else 1,
                -(c.get("message_count") or 0),
                -(c.get("id") or 0),
            )
        chosen = sorted(chats, key=score)[0]
        cid = chosen.get("id")
        log.info("Selected Leon chat %s (group=%s, messages=%s)", cid, chosen.get("group"), chosen.get("message_count"))
        return cid
    except Exception as exc:
        log.warning("Failed to pick Leon chat: %s", exc)
        return None


def run_fastlane(
    cfg: Config,
    db: Database,
    api: SeriesAPI,
    llm=None,
    log=None,
    stop_event=None,
    on_error: Optional[Callable[[str, str], None]] = None,
    on_state_change: Optional[Callable[..., None]] = None,
    get_kafka_inbox: Optional[Callable[[], List[Dict]]] = None,
) -> None:
    """Run the Leon -> Dh scripted flow until stop_event is set."""
    log = log or logging.getLogger("orbit.fastlane")
    llm = llm or get_llm(temperature=0.7)
    stop_event = stop_event

    def report_error(msg: str) -> None:
        log.error(msg)
        if on_error:
            on_error("fastlane", msg)

    ensure_tester_profiles(db)

    leon_user = db.users.get_by_phone(LEON_PHONE)
    # Use stored chat_id if present; fallback to known chat id; avoid broken list filter
    leon_chat = None
    if leon_user and leon_user["chat_id"]:
        leon_chat = leon_user["chat_id"]
    if not leon_chat:
        leon_chat = LEON_CHAT_DEFAULT
    if leon_user and leon_user["chat_id"] != leon_chat:
        db.users.update_chat_id(leon_user["id"], leon_chat)
    if not leon_chat:
        report_error("Unable to create/find chat for Leon")
        return

    # Initialize last_ids by fetching current messages so we don't re-process old ones
    # Because the list API pagination is broken, we need to scan to find the real max ID
    try:
        existing_msgs = api.get_messages(leon_chat, limit=100)
        max_list_id = max((m.get("id", 0) for m in existing_msgs), default=0)
        log.info("List endpoint max_id: %d (found %d msgs)", max_list_id, len(existing_msgs))
        
        # Scan to find actual latest messages (API pagination is broken)
        # Use smaller scan for faster startup - we'll catch up via polling
        log.info("Scanning for newer messages from ID %d...", max_list_id)
        scanned = api.scan_for_new_messages(leon_chat, max_list_id, max_scan=30000)
        if scanned:
            max_existing_id = max(m.get("id", 0) for m in scanned)
            log.info("Scan found %d messages, max_id now: %d", len(scanned), max_existing_id)
        else:
            max_existing_id = max_list_id
    except Exception as exc:
        log.warning("Failed to initialize message IDs: %s", exc)
        max_existing_id = 0
    
    try:
        intro_msg = llm.invoke(
            "Write a short, warm opener to a tester named Leon. Mention you're Orbit and you're here to help find a great intro."
        ).content
        send_with_typing(api, leon_chat, intro_msg)
    except Exception as exc:
        report_error(f"Failed to send intro message: {exc}")
        return

    # Start tracking from BEFORE we sent the intro, so we catch any message
    # that arrives after we started (including fast replies)
    # We'll filter out our own messages in the loop
    last_ids: Dict[str, int] = {str(leon_chat): max_existing_id}
    last_counts: Dict[str, int] = {str(leon_chat): api.get_chat_message_count(leon_chat)}
    log.info("Starting with last_id=%d, count=%d", max_existing_id, last_counts[str(leon_chat)])
    stage = "wait_leon"
    processed_msg_ids: set = set()  # Track which messages we've already handled
    group_chat_id: Optional[int] = None

    def update_state(**kwargs):
        if on_state_change:
            on_state_change(**kwargs)

    log.info("Fastlane running. Watching Leon chat %s", leon_chat)
    update_state(stage=stage, chat_id=leon_chat, activity="Started watching Leon's chat")
    no_new_counter = 0
    while True:
        if stop_event and stop_event.is_set():
            log.info("Fastlane stop requested.")
            break
        # If we've seen no new messages for ~45s, re-pick the current Leon chat (handles collisions)
        if no_new_counter >= int(45 / max(1, int(cfg.poll_interval_sec))):
            maybe_new = _pick_leon_chat(api, log)
            if maybe_new and maybe_new != leon_chat:
                log.info("Switching watch to Leon chat %s -> %s", leon_chat, maybe_new)
                leon_chat = maybe_new
                last_ids[str(leon_chat)] = last_ids.get(str(leon_chat), 0)
                update_state(chat_id=leon_chat, activity=f"Switched to chat #{leon_chat}")
                no_new_counter = 0
        # Handle Leon DM - check both REST API and Kafka inbox
        try:
            chat_key = str(leon_chat)
            new_msgs, new_count = fetch_new_messages(
                api, leon_chat, last_ids.get(chat_key, 0), 
                log=log, last_count=last_counts.get(chat_key, 0)
            )
            last_counts[chat_key] = new_count
            if new_msgs:
                log.info("Fetched %d new REST messages (last_id=%d, count=%d)", 
                         len(new_msgs), last_ids.get(chat_key, 0), new_count)
        except Exception as exc:
            report_error(f"Failed to fetch messages: {exc}")
            new_msgs = []
        
        # Also check Kafka inbox for real-time messages
        if get_kafka_inbox:
            kafka_msgs = get_kafka_inbox()
            for km in kafka_msgs:
                # Convert Kafka event to message-like dict
                if km.get("from_phone") == LEON_PHONE and km.get("text"):
                    fake_msg = {
                        "id": km.get("message_id") or int(time.time() * 1000),
                        "text": km.get("text"),
                        "sent_from": km.get("from_phone"),
                        "chat_id": km.get("chat_id"),
                    }
                    log.info("Got Kafka message from Leon: %s", km.get("text")[:50])
                    # Add if not already in new_msgs
                    if not any(m.get("text") == fake_msg["text"] for m in new_msgs):
                        new_msgs.append(fake_msg)
        if not new_msgs:
            no_new_counter += 1
        else:
            no_new_counter = 0
        for msg in new_msgs:
            msg_id = msg["id"]
            last_ids[str(leon_chat)] = msg_id
            sent_from = msg.get("sent_from", "")
            
            # Log every message we see
            is_ours = sent_from == cfg.series_sender_number
            log.info("  Msg %d from %s%s: %s", msg_id, sent_from[-4:] if sent_from else "?", 
                     " (OURS)" if is_ours else "", (msg.get("text") or "")[:40])
            
            # Skip messages we've already processed or sent ourselves
            if msg_id in processed_msg_ids:
                continue
            if is_ours:
                processed_msg_ids.add(msg_id)
                continue
            if msg.get("is_from_me"):
                processed_msg_ids.add(msg_id)
                continue
            
            processed_msg_ids.add(msg_id)
            text = (msg.get("text") or "").strip()
            if not text:
                continue
                
            log.info("Leon [stage=%s] -> %s", stage, text)
            update_state(activity=f"Leon said: {text[:50]}..." if len(text) > 50 else f"Leon said: {text}")
            
            if stage == "wait_leon":
                summary = llm.invoke(
                    f"Summarize this person's vibe in one line: {text}. Keep it casual."
                ).content
                if leon_user:
                    db.profiles.update_summary(leon_user["id"], summary, 0.8)
                    db.users.update_status(leon_user["id"], "active")
                ask_intro = llm.invoke(
                    "Ask if Leon wants an intro to someone thoughtful who likes coffee and sci-fi. Keep it short."
                ).content
                send_with_typing(api, leon_chat, ask_intro)
                stage = "ask_intro"
                update_state(stage=stage, activity="Asked Leon about intro")
                log.info("Stage -> ask_intro")
                break  # Only process one message per loop iteration
                
            elif stage == "ask_intro":
                lower_text = text.lower()
                if lower_text.startswith("y") or "yes" in lower_text or "sure" in lower_text or "please" in lower_text:
                    intro = llm.invoke(
                        "Write a short two-sentence intro between Leon and Dhairyasheel citing coffee and sci-fi. Include names."
                    ).content
                    created = api.create_group_chat([LEON_PHONE, DHAIRYA_PHONE], intro, display_name="Connect")
                    # API returns {"data": {"id": ..., ...}} per OpenAPI spec
                    group_chat_id = created.get("data", {}).get("id") or created.get("id")
                    log.info("Group chat created: %s", group_chat_id)
                    if group_chat_id:
                        last_ids[str(group_chat_id)] = 0
                        send_with_typing(
                            api,
                            group_chat_id,
                            "I'll hang back. If you need me, just type @Orbit or ask for advice!",
                            delay=0.8,
                        )
                        stage = "group_live"
                        update_state(stage=stage, chat_id=group_chat_id, activity=f"Created group chat #{group_chat_id}")
                        log.info("Stage -> group_live")
                    break
                elif lower_text.startswith("n") or "no" in lower_text:
                    send_with_typing(api, leon_chat, "No worries—let me know if you change your mind!")
                    stage = "done"  # Don't loop back, just wait
                    update_state(stage=stage, activity="Leon declined intro")
                    log.info("Stage -> done (user declined)")
                    break
                # If unclear response, stay in ask_intro and wait for clearer answer

        # Handle group chat chatter
        if stage == "group_live" and group_chat_id:
            group_key = str(group_chat_id)
            group_msgs, group_count = fetch_new_messages(
                api, group_chat_id, last_ids.get(group_key, 0), 
                log=log, last_count=last_counts.get(group_key, 0)
            )
            last_counts[group_key] = group_count
            for msg in group_msgs:
                last_ids[group_key] = msg["id"]
                if msg.get("sent_from") == cfg.series_sender_number or msg.get("is_from_me"):
                    continue
                text = (msg.get("text") or "").strip()
                if "@orbit" in text.lower() or text.lower().startswith("orbit"):
                    reply = llm.invoke(
                        f"Give one short nudge to keep a date chat flowing. Context: {text}"
                    ).content
                    send_with_typing(api, group_chat_id, reply, delay=0.6)

        time.sleep(2.0)


def main() -> None:
    cfg = Config.from_env()
    log = setup_logger(cfg.log_level)
    db = Database(cfg.db_path)
    api = SeriesAPI(
        cfg.series_base_url,
        cfg.series_api_key,
        timeout=cfg.request_timeout,
        max_retries=cfg.max_retries,
        sender_number=cfg.series_sender_number,
    )
    llm = get_llm(temperature=0.7)
    run_fastlane(cfg, db, api, llm=llm, log=log)


if __name__ == "__main__":
    main()
