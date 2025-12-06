"""Main entry point for Orbit dating agent."""
import logging
import signal
import sys
from typing import Any, Dict, Iterable, Tuple

from .agent import build_graph
from .api import SeriesAPI
from .config import Config
from .db import Database
from .kafka import KafkaEvent, build_consumer
from .utils import setup_logger


def process_event(event: Dict[str, Any], graph: Any, log: logging.Logger) -> None:
    """Process a Kafka event through the LangGraph."""
    try:
        kafka_event = KafkaEvent.from_dict(event)
        data = kafka_event.data

        phone = data.from_phone
        chat_id = data.chat_id
        text = (data.text or "").strip()
        chat_handles = data.chat_handles or []

        if not phone or chat_id is None:
            log.warning("Skipping event missing phone/chat_id: %s", event)
            return

        is_group = len(chat_handles) > 2
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
        result = graph.invoke(initial_state)
        log.debug("Graph execution completed: %s", result.get("response", "")[:50])

    except Exception as exc:
        log.exception("Failed to process event: %s", exc)


def seed_testers(db: Database, testers: Iterable[Tuple[str, str]]) -> None:
    """Ensure known tester accounts exist without overwriting data."""
    log = logging.getLogger("orbit.seed")
    for phone, name in testers:
        existing = db.users.get_by_phone(phone)
        if existing:
            continue
        user_id = db.users.create(phone, name=name)
        db.profiles.create(user_id)
        log.info("Seeded tester %s", phone)


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

    graph = build_graph(db, api)
    log.info("LangGraph agent built successfully")

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
        while should_run:
            for message in consumer:
                if not should_run:
                    break
                event: Dict[str, Any] = message.value
                process_event(event, graph, log)
    finally:
        log.info("Closing connections...")
        consumer.close()
        db.close()
        log.info("Shutdown complete")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)
