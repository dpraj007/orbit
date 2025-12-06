"""Kafka module for consuming and producing messages."""
from .schemas import KafkaEvent

# Lazy import consumer to avoid requiring kafka-python for tests
try:
    from .consumer import build_consumer
    __all__ = ["build_consumer", "KafkaEvent"]
except ImportError:
    # Kafka dependencies not available (e.g., in test environment)
    __all__ = ["KafkaEvent"]
