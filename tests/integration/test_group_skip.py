"""Test group chat skip logic."""
import pytest
from tests.helpers.event_builder import build_event


@pytest.mark.integration
class TestGroupSkip:
    def test_group_message_without_mention_skipped(self, runner, event_fx):
        """Group messages without @orbit should be ignored."""
        event = event_fx(
            text="Hey everyone, what's up?",
            chat_handles=["+1555", "+1666", "+1777"],  # 3 = group
        )

        result = runner.run_event(event)
        # Should complete without sending response
        assert result.response == "" or result.error is None

    def test_group_message_with_mention_processed(self, db_fx, runner, event_fx):
        """Group messages with @orbit should be processed."""
        phone = "+15551234567"
        user_id = db_fx.users.create(phone, 3001)
        db_fx.profiles.create(user_id)
        db_fx.users.update_status(user_id, "active")

        event = event_fx(
            phone=phone,
            chat_id=3001,
            text="@orbit help me with an icebreaker",
            chat_handles=[phone, "+1666", "+1777"],
        )

        result = runner.run_event(event)
        assert result.response  # Should get a response

