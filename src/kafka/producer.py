"""Kafka producer setup and utilities using confluent-kafka."""
import json
import logging
from typing import Any, Dict, Optional

from confluent_kafka import Producer, KafkaError, Message

from ..config import Config

logger = logging.getLogger(__name__)


def build_producer(cfg: Config) -> Producer:
    """Build and configure Kafka producer."""
    conf = {
        'bootstrap.servers': cfg.kafka_bootstrap,
        'client.id': cfg.kafka_client_id,
        'security.protocol': cfg.kafka_security_protocol,
        'sasl.mechanism': cfg.kafka_sasl_mechanism,
        'sasl.username': cfg.kafka_sasl_username,
        'sasl.password': cfg.kafka_sasl_password,
    }
    return Producer(conf)


def delivery_report(err: Optional[KafkaError], msg: Message) -> None:
    """Callback for message delivery reports."""
    if err is not None:
        logger.error("Message delivery failed: %s", err)
    else:
        logger.info("Message delivered to %s [%s] at offset %s", 
                   msg.topic(), msg.partition(), msg.offset())


def send_event(producer: Producer, topic: str, event: Dict[str, Any], timeout: int = 10) -> bool:
    """
    Send a message to Kafka and wait for acknowledgment.
    
    Args:
        producer: Configured Producer instance
        topic: Topic name to send to
        event: Dictionary containing the message payload
        timeout: Timeout in seconds to wait for acknowledgment (flush)
        
    Returns:
        bool: True if sent successfully (enqueued), False otherwise. 
              Note: flush() waits for delivery, so True means likely delivered.
    """
    try:
        # Serialize to JSON bytes
        value = json.dumps(event).encode('utf-8')
        
        # Produce asynchronously with callback
        producer.produce(topic, value, callback=delivery_report)
        
        # Wait for any outstanding messages to be delivered and delivery report callbacks to be triggered.
        # This makes it synchronous effectively, similar to the previous implementation.
        messages_left = producer.flush(timeout)
        
        if messages_left > 0:
            logger.warning("%d messages were still in queue after flush timeout", messages_left)
            return False
            
        return True
        
    except Exception as e:
        logger.error("Unexpected error sending Kafka message: %s", e)
        return False
