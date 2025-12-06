"""Main entry point for Orbit dating agent."""
import json
import logging
import time
import signal
import sys
from typing import Any, Dict, Iterable, Tuple

from .agent.core import AgentCore
from .api import SeriesAPI
from .config import Config
from .db import Database
from .kafka import KafkaEvent, build_consumer
from .utils import setup_logger


core_agent: AgentCore  # instantiated in main


def process_event(event: Dict[str, Any], db: Database, api: SeriesAPI, log: logging.Logger) -> None:
    """Process a Kafka event through the LangGraph."""
    try:
        if "event_type" in event:
            # Kafka-style event
            kafka_event = KafkaEvent.from_dict(event)
            data = kafka_event.data
            phone = data.from_phone
            chat_id = data.chat_id
            text = (data.text or "").strip()
            chat_handles = data.chat_handles or []
        else:
            # Minimal REST-polled event
            data = event.get("data", {})
            phone = data.get("from_phone")
            chat_id = data.get("chat_id")
            text = (data.get("text") or "").strip()
            chat_handles = data.get("chat_handles") or []

        if not phone or chat_id is None or not text:
            log.warning("Skipping event missing phone/chat_id: %s", event)
            return

        is_group = bool(event.get("data", {}).get("is_group")) or len(chat_handles) > 2
        log.info(
            "📝 Message: '%s' from %s (group=%s, handles=%d)",
            text[:50] if text else "(empty)",
            phone,
            is_group,
            len(chat_handles),
        )

        # In group chats, only react when explicitly mentioned to avoid spam
        if is_group and "@orbit" not in text.lower():
            log.debug("Skipping group message without @orbit mention")
            return

        initial_state = {
            "phone_number": phone,
            "chat_id": chat_id,
            "message": text,
            "db_updates": [],
        }

        log.info("Processing message from %s in chat %d", phone, chat_id)
        # Pass event to deterministic core agent
        core_agent.handle_event({"data": {"chat_id": chat_id, "from_phone": phone, "text": text, "chat_handles": chat_handles, "is_group": is_group}})

    except Exception as exc:
        log.exception("Failed to process event: %s", exc)


def seed_testers(db: Database, testers: Iterable[Tuple[str, str]]) -> None:
    """Ensure known tester accounts exist without overwriting data."""
    log = logging.getLogger("orbit.seed")
    for phone, name in testers:
        existing = db.users.get_by_phone(phone)
        if not existing:
            user_id = db.users.create(phone, name=name)
            db.profiles.create(user_id)
            log.info("Seeded tester %s", phone)
        else:
            user_id = existing["id"]
            # Ensure profile exists
            if not db.profiles.get_by_user_id(user_id):
                db.profiles.create(user_id)

    # Prepopulate profiles with friendly summaries
    presets = {
        "+16479165156": (
            "Leon",
            "Builder and tester trying Orbit; enjoys hiking and cooking. Chill fact-dropper starting a casual convo.",
            "Curious, kind people; likes playful banter.",
            0.9,
        ),
        "+19298776648": (
            "Dhairyasheel",
            "Product-minded, loves good coffee and long walks. Reads sci-fi.",
            "Thoughtful, playful conversations.",
            1.0,
        ),
        "+15555550123": (
            "Donald",
            "Easygoing, loves kayaking and cartoons. Down-to-earth and keeps things light. Great with dad jokes.",
            "Fun, kind people who like to laugh; looking for low-drama connection.",
            1.0,
        ),
    }
    for phone, (pname, summary, looking, completeness) in presets.items():
        user = db.users.get_by_phone(phone)
        if not user:
            user_id = db.users.create(phone, name=pname)
            db.profiles.create(user_id)
        else:
            user_id = user["id"]
        db.profiles.update_summary(user_id, summary, completeness)
        db.profiles.update_field(user_id, "looking_for_summary", looking)
        db.users.update_status(user_id, "active")


def main() -> None:
    """Main entry point."""
    cfg = Config.from_env()
    log = setup_logger(cfg.log_level)

    log.info("Initializing Orbit dating agent...")

    db = Database(cfg.db_path)
    seed_testers(
        db,
        [
            ("+16479165156", "Leon"),
            ("+19298776648", "Dhairyasheel"),
            ("+15555550123", "Donald"),
        ],
    )
    log.info("Database initialized")

    api = SeriesAPI(
        cfg.series_base_url,
        cfg.series_api_key,
        timeout=cfg.request_timeout,
        max_retries=cfg.max_retries,
        sender_number=cfg.series_sender_number,
    )
    log.info("API client initialized")

    global core_agent
    core_agent = AgentCore(db, api)
    log.info("Agent core initialized")

    consumer = None
    if cfg.ingress_mode != "api":
        consumer = build_consumer(cfg)
        log.info("Kafka consumer started on topic %s", cfg.kafka_topic)

    should_run = True

    def handle_signal(signum, frame):  # type: ignore[unused-argument]
        nonlocal should_run
        should_run = False
        log.info("Shutting down...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    log.info("🚀 Orbit agent is running! Waiting for messages...")

    try:
        if cfg.ingress_mode == "api":
            log.info("Ingress mode=api (REST polling). Kafka disabled.")
            last_ids: Dict[int, int] = {}
            sender_number = cfg.series_sender_number
            while should_run:
                # 1: Poll DM chats for users
                users = db.users.get_all()
                for user in users:
                    chat_id = user["chat_id"]
                    if not chat_id:
                        continue
                    msgs = api.get_messages(chat_id, limit=100)
                    if chat_id not in last_ids:
                        last_ids[chat_id] = max((m.get("id", 0) for m in msgs), default=0)
                        continue
                    new_msgs = [m for m in msgs if m.get("id", 0) > last_ids[chat_id]]
                    for m in sorted(new_msgs, key=lambda x: x.get("id", 0)):
                        last_ids[chat_id] = max(last_ids[chat_id], m.get("id", 0))
                        if m.get("sent_from") == sender_number:
                            continue  # skip our own sends
                        event = {
                            "data": {
                                "chat_id": chat_id,
                                "from_phone": m.get("sent_from"),
                                "text": m.get("text", ""),
                                "chat_handles": m.get("chat_handles") or [],
                                "is_group": False,
                                "sent_at": m.get("sent_at"),
                                "attachments": m.get("attachments") or [],
                            }
                        }
                        process_event(event, db, api, log)

                # 2: Poll group chats associated with conversation_state
                try:
                    states = db.conversation_state.get_all()
                except Exception:
                    states = []
                group_ids = set()
                for row in states:
                    ctx_raw = row["context"]
                    if not ctx_raw:
                        continue
                    try:
                        ctx_obj = json.loads(ctx_raw)
                        if not isinstance(ctx_obj, dict):
                            ctx_obj = {}
                    except Exception:
                        continue
                    gid = ctx_obj.get("group_chat_id")
                    if isinstance(gid, int):
                        group_ids.add(gid)

                for gid in group_ids:
                    msgs = api.get_messages(gid, limit=100)
                    if gid not in last_ids:
                        last_ids[gid] = max((m.get("id", 0) for m in msgs), default=0)
                        continue
                    new_msgs = [m for m in msgs if m.get("id", 0) > last_ids[gid]]
                    for m in sorted(new_msgs, key=lambda x: x.get("id", 0)):
                        last_ids[gid] = max(last_ids[gid], m.get("id", 0))
                        event = {
                            "data": {
                                "chat_id": gid,
                                "from_phone": m.get("sent_from"),
                                "text": m.get("text", ""),
                                "chat_handles": m.get("chat_handles") or [],
                                "is_group": True,
                                "sent_at": m.get("sent_at"),
                                "attachments": m.get("attachments") or [],
                            }
                        }
                        process_event(event, db, api, log)
                time.sleep(cfg.poll_interval_sec)
        else:
            while should_run:
                for message in consumer:
                    if not should_run:
                        break
                    event: Dict[str, Any] = message.value
                    process_event(event, db, api, log)
    finally:
        log.info("Closing connections...")
        if consumer:
            consumer.close()
        db.close()
        log.info("Shutdown complete")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)
