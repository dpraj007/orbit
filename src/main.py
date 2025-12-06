import json
import logging
import signal
import sys
import time
from typing import Any, Dict

from kafka import KafkaConsumer

from .client import SeriesClient
from .config import Config
from .engine import process_event
from .llm import WingmanLLM
from .store import UserStore
from .utils import setup_logger


def build_consumer(cfg: Config) -> KafkaConsumer:
    return KafkaConsumer(
        cfg.kafka_topic,
        bootstrap_servers=cfg.kafka_bootstrap,
        group_id=cfg.kafka_group,
        client_id=cfg.kafka_client_id,
        security_protocol=cfg.kafka_security_protocol,
        sasl_mechanism=cfg.kafka_sasl_mechanism,
        sasl_plain_username=cfg.kafka_sasl_username,
        sasl_plain_password=cfg.kafka_sasl_password,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )


def _process_with_guard(event: Dict[str, Any], client: SeriesClient, store: UserStore, llm: WingmanLLM, log) -> None:
    try:
        process_event(event, client, store, llm)
    except Exception as exc:
        log.exception("Failed to process message: %s", exc)


def _run_kafka_loop(
    cfg: Config, log, store: UserStore, client: SeriesClient, llm: WingmanLLM, keep_running
) -> None:
    consumer = build_consumer(cfg)
    log.info("Orbit consumer started on topic %s", cfg.kafka_topic)
    try:
        while keep_running():
            records = consumer.poll(timeout_ms=1000)
            for messages in records.values():
                for message in messages:
                    if not keep_running():
                        break
                    event: Dict[str, Any] = message.value
                    _process_with_guard(event, client, store, llm, log)
    finally:
        consumer.close()


def _run_api_polling(
    cfg: Config, log, store: UserStore, client: SeriesClient, llm: WingmanLLM, keep_running
) -> None:
    poll_interval = max(cfg.poll_interval_sec, 0.5)
    log.info("Orbit API polling started (every %.1fs)", poll_interval)
    while keep_running():
        try:
            chats = list(client.list_chats(per_page=50))
        except Exception as exc:
            log.exception("Failed to list chats: %s", exc)
            time.sleep(poll_interval)
            continue

        for chat in chats:
            if not keep_running():
                break
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            try:
                messages = list(client.list_chat_messages(int(chat_id), per_page=50))
            except Exception as exc:
                log.warning("Failed to fetch messages for chat %s: %s", chat_id, exc)
                continue

            last_seen = store.get_last_message_id(int(chat_id)) or 0
            max_seen = last_seen
            sorted_messages = sorted(
                (m for m in messages if isinstance(m, dict) and isinstance(m.get("id"), int)),
                key=lambda m: m.get("id", 0),
            )

            for msg in sorted_messages:
                if not keep_running():
                    break
                msg_id = msg.get("id")
                if not isinstance(msg_id, int) or msg_id <= last_seen:
                    max_seen = max(max_seen, msg_id or 0)
                    continue
                if msg.get("is_from_me"):
                    max_seen = max(max_seen, msg_id)
                    continue
                sent_from = str(msg.get("sent_from") or "")
                if cfg.series_sender_number and sent_from == cfg.series_sender_number:
                    max_seen = max(max_seen, msg_id)
                    continue
                event = {"data": {"chat_message": msg, "chat": chat}}
                _process_with_guard(event, client, store, llm, log)
                max_seen = max(max_seen, msg_id)

            if max_seen > last_seen:
                store.set_last_message_id(int(chat_id), max_seen)

        time.sleep(poll_interval)


def main() -> None:
    cfg = Config.from_env()
    log = setup_logger(cfg.log_level)
    store = UserStore(cfg.db_path)
    # Seed primary testers if not already present (no override of existing data).
    store.ensure_user("+16479165156", name="Leon", status="BROWSING")
    store.ensure_user("+19298776648", name="Dhairyasheel", status="BROWSING")
    series_client = SeriesClient(
        cfg.series_base_url,
        cfg.series_api_key,
        timeout=cfg.request_timeout,
        max_retries=cfg.max_retries,
        sender_number=cfg.series_sender_number,
    )
    llm = WingmanLLM(cfg.openrouter_api_key, cfg.openrouter_model)

    should_run = True

    def handle_signal(signum, frame):  # type: ignore[unused-argument]
        nonlocal should_run
        should_run = False
        log.info("Shutting down...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    ingress_mode = cfg.ingress_mode or "kafka"
    if ingress_mode == "api":
        _run_api_polling(cfg, log, store, series_client, llm, lambda: should_run)
    else:
        _run_kafka_loop(cfg, log, store, series_client, llm, lambda: should_run)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)
