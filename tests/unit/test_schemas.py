"""Test Kafka schema parsing."""
import pytest
from src.kafka import KafkaEvent


@pytest.mark.unit
class TestKafkaSchemas:
    def test_kafka_event_missing_data(self):
        """Event with missing data should use defaults."""
        event = KafkaEvent.from_dict({})
        assert event.data.text is None
        assert event.data.chat_handles == []
        assert event.data.attachments == []

    def test_kafka_event_full(self):
        """Full event should parse correctly."""
        event = KafkaEvent.from_dict({
            "event_type": "message",
            "timestamp": "2025-12-06T12:00:00Z",
            "data": {
                "text": "hello",
                "from_phone": "+1234",
                "chat_id": 100,
                "message_id": 999,
                "chat_handles": ["+1234", "+5678"],
                "attachments": [],
            }
        })
        assert event.data.text == "hello"
        assert event.data.from_phone == "+1234"
        assert event.data.chat_id == 100
        assert len(event.data.chat_handles) == 2

    def test_kafka_event_partial_data(self):
        """Event with partial data should work."""
        event = KafkaEvent.from_dict({
            "data": {
                "text": "hi",
                "from_phone": "+1555",
            }
        })
        assert event.data.text == "hi"
        assert event.data.chat_id is None

