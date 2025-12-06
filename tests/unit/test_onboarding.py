"""Test onboarding node."""
import pytest
from tests.helpers.event_builder import build_event


@pytest.mark.unit
class TestOnboarding:
    def test_onboarding_extracts_name(self, runner, event_fx):
        """Onboarding should extract name from first message."""
        runner.run_event(event_fx(text="Hi"))  # First contact
        result = runner.run_event(event_fx(text="Alex, I love hiking"))

        assert result.db_state["profile"]["onboarding_step"] >= 1

    def test_onboarding_completes_after_all_steps(self, runner, event_fx):
        """Onboarding should complete after all questions."""
        messages = [
            "Alex, passionate about technology",
            "Looking for something serious",
            "I'm a software engineer who loves building things",
            "Someone kind, smart, and adventurous",
            "Smoking is a dealbreaker",
            "Friends say I'm warm and thoughtful",
            "Hiking, coffee shops, and board game nights",
        ]

        for msg in messages:
            result = runner.run_event(event_fx(text=msg))

        assert result.db_state["user"]["status"] == "active"
        assert result.db_state["profile"]["completeness"] == 1.0

    def test_onboarding_progresses_through_steps(self, runner, event_fx):
        """Onboarding should increment step correctly."""
        result1 = runner.run_event(event_fx(text="Hi"))
        step1 = result1.db_state["profile"]["onboarding_step"]

        result2 = runner.run_event(event_fx(text="I'm Taylor"))
        step2 = result2.db_state["profile"]["onboarding_step"]

        assert step2 > step1

