"""Test complete onboarding flow."""
import pytest
from tests.helpers.event_builder import build_event


@pytest.mark.integration
class TestOnboardingFlow:
    def test_complete_onboarding_happy_path(self, runner, event_fx):
        """Walk through complete onboarding with realistic answers."""
        phone = "+15559876543"
        chat_id = 2001

        conversations = [
            ("Hey!", "name"),
            ("I'm Taylor, and I'm really into photography", "looking"),
            ("Something serious, ready to settle down", "about"),
            ("I'm a product designer at a startup. Love creative work!", "partner"),
            ("Someone curious, kind, and has their own passions", "dealbreaker"),
            ("Dishonesty and lack of ambition", "communication"),
            ("My friends say I'm thoughtful and a good listener", "weekend"),
            ("Coffee shop in the morning, maybe a hike, dinner with friends", "matches"),
        ]

        for user_msg, expected_keyword in conversations:
            result = runner.run_event(event_fx(phone=phone, chat_id=chat_id, text=user_msg))
            # Check that response contains expected keyword OR user is now active
            assert (
                expected_keyword.lower() in result.response.lower()
                or result.db_state["user"]["status"] == "active"
            )

        # Verify final state
        assert result.db_state["user"]["status"] == "active"
        assert result.db_state["profile"]["completeness"] == 1.0
        assert "taylor" in result.db_state["profile"]["profile_summary"].lower()

