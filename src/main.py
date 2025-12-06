import json
import logging
import signal
import sys
from typing import Any, Dict

from kafka import KafkaConsumer

from .client import SeriesClient
from .config import Config
from .engine import process_event
from .llm import WingmanLLM
from .store import UserStore
from .utils import setup_logger
from .agent.graph import create_dating_graph


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


def main() -> None:
    cfg = Config.from_env()
    log = setup_logger(cfg.log_level)

    # Initialize components
    store = UserStore(cfg.db_path)
    series_client = SeriesClient(
        cfg.series_base_url,
        cfg.series_api_key,
        timeout=cfg.request_timeout,
        max_retries=cfg.max_retries,
        sender_number=cfg.series_sender_number,
    )
    llm = WingmanLLM(cfg.openrouter_api_key, cfg.openrouter_model)

    # Create LangGraph agent
    log.info("Building LangGraph agent...")
    graph = create_dating_graph(store, llm, series_client)

    # Start Kafka consumer
    consumer = build_consumer(cfg)
    log.info("Orbit consumer started on topic %s", cfg.kafka_topic)
    log.info("Dating agent ready with LangGraph")

    should_run = True

    def handle_signal(signum, frame):  # type: ignore[unused-argument]
        nonlocal should_run
        should_run = False
        log.info("Shutting down...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while should_run:
        for message in consumer:
            if not should_run:
                break
            try:
                event: Dict[str, Any] = message.value
                process_event(event, series_client, store, llm, graph)
            except Exception as exc:
                log.exception("Failed to process message: %s", exc)

    # Cleanup
    consumer.close()
    store.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)
