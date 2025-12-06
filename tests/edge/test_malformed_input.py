"""Test malformed input handling."""
import pytest
from tests.helpers.event_builder import build_event


@pytest.mark.unit
class TestMalformedInput:
    def test_empty_message(self, runner, event_fx):
        """Empty message should still get a response."""
        result = runner.run_event(event_fx(text=""))
        assert result.response or result.error is None

    def test_whitespace_only_message(self, runner, event_fx):
        """Whitespace-only message should be handled."""
        result = runner.run_event(event_fx(text="   \n\t  "))
        assert result.response or result.error is None

    def test_missing_phone(self, runner):
        """Missing phone should be handled gracefully."""
        event = {"data": {"text": "hello", "chat_id": 100}}
        result = runner.run_event(event)
        # Should handle gracefully without crashing
        assert result.error is not None or result.response == ""

    def test_extremely_long_message(self, runner, event_fx):
        """Extremely long message should be handled."""
        long_text = "a" * 10000
        result = runner.run_event(event_fx(text=long_text))
        assert result.response or result.error is None

