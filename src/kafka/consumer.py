"""Kafka consumer setup."""
import json

from kafka import KafkaConsumer

from ..config import Config


def build_consumer(cfg: Config) -> KafkaConsumer:
    """Build and configure Kafka consumer.
    
    Uses a stable group ID so Kafka tracks committed offsets.
    This ensures messages are only processed once and new messages
    are picked up in real-time.
    """
    return KafkaConsumer(
        cfg.kafka_topic,
        bootstrap_servers=cfg.kafka_bootstrap,
        group_id=cfg.kafka_group,  # Stable group ID for offset tracking
        client_id=cfg.kafka_client_id,
        security_protocol=cfg.kafka_security_protocol,
        sasl_mechanism=cfg.kafka_sasl_mechanism,
        sasl_plain_username=cfg.kafka_sasl_username,
        sasl_plain_password=cfg.kafka_sasl_password,
        auto_offset_reset="latest",  # Only get NEW messages (stable group tracks committed offsets)
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
