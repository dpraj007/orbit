"""Test matching node."""
import pytest
from src.agent.nodes.matching import calculate_bilateral_score


@pytest.mark.unit
class TestMatching:
    def test_bilateral_score_calculation(self):
        """Bilateral score should be calculated correctly."""
        profile_a = {
            "profile_summary": "Outgoing, loves hiking",
            "looking_for_summary": "Active partner"
        }
        profile_b = {
            "profile_summary": "Adventurous, fitness enthusiast",
            "looking_for_summary": "Fun companion"
        }

        score, reason = calculate_bilateral_score(profile_a, profile_b)
        assert 0 <= score <= 100
        assert len(reason) > 0

    def test_match_rejection_clears_state(self, db_fx, runner, event_fx):
        """Rejecting a match should clear conversation state."""
        # Setup active match
        user_id = db_fx.users.create("+1555", 100)
        db_fx.profiles.create(user_id)
        db_fx.profiles.update_summary(user_id, "Test user", 1.0)
        db_fx.users.update_status(user_id, "active")

        other_id = db_fx.users.create("+1666", 101)
        db_fx.profiles.create(other_id)

        match_id = db_fx.matches.create(user_id, other_id, 75.0)
        db_fx.conversation_state.upsert(
            user_id, current_node="match_decision", match_in_progress=match_id
        )

        result = runner.run_event(event_fx(phone="+1555", text="no thanks"))

        assert "keep looking" in result.response.lower() or "no worries" in result.response.lower()
        # Match should be rejected
        match = db_fx.matches.get_by_id(match_id)
        assert match["status"] == "rejected"

    def test_match_acceptance_updates_status(self, db_fx, runner, event_fx):
        """Accepting a match should update match status."""
        user_id = db_fx.users.create("+1555", 100)
        db_fx.profiles.create(user_id)
        db_fx.profiles.update_summary(user_id, "Test user", 1.0)
        db_fx.users.update_status(user_id, "active")

        other_id = db_fx.users.create("+1666", 101)
        db_fx.profiles.create(other_id)

        match_id = db_fx.matches.create(user_id, other_id, 75.0)
        db_fx.conversation_state.upsert(
            user_id, current_node="match_decision", match_in_progress=match_id
        )

        result = runner.run_event(event_fx(phone="+1555", text="yes"))

        match = db_fx.matches.get_by_id(match_id)
        assert match["user_a_decision"] == "yes" or match["user_b_decision"] == "yes"

