"""Kafka module for consuming and producing messages."""
from .consumer import build_consumer
from .schemas import KafkaEvent

__all__ = ["build_consumer", "KafkaEvent"]
