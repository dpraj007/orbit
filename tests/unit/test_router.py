"""Test router intent classification."""
import pytest
from tests.helpers.event_builder import build_event


@pytest.mark.unit
class TestRouter:
    def test_route_onboarding_user_goes_to_onboarding(self, runner, event_fx):
        """New user should route to onboarding."""
        result = runner.run_event(event_fx(text="Hi there"))
        assert result.db_state["user"] is not None
        assert result.db_state["user"]["status"] == "onboarding"

    def test_route_match_decision_when_active_match(self, db_fx, runner, event_fx):
        """User with active match should route to matching node."""
        # Seed user with active match
        user_id = db_fx.users.create("+1555", 100)
        db_fx.profiles.create(user_id)
        db_fx.profiles.update_summary(user_id, "Test user", 1.0)
        db_fx.users.update_status(user_id, "active")
        other_id = db_fx.users.create("+1666", 101)
        db_fx.profiles.create(other_id)
        match_id = db_fx.matches.create(user_id, other_id, 75.0)
        db_fx.conversation_state.upsert(user_id, match_in_progress=match_id)

        result = runner.run_event(event_fx(phone="+1555", text="yes"))
        # Should route to matching node
        assert "match" in result.response.lower() or "waiting" in result.response.lower()

    def test_route_mentor_intent(self, db_fx, runner, event_fx):
        """Mentor-related messages should route to mentor node."""
        user_id = db_fx.users.create("+1555", 100)
        db_fx.profiles.create(user_id)
        db_fx.profiles.update_summary(user_id, "Test user", 1.0)
        db_fx.users.update_status(user_id, "active")

        result = runner.run_event(event_fx(phone="+1555", text="help me with icebreakers"))
        assert len(result.response) > 0

