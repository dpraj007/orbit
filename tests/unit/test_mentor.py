"""Test mentor node."""
import pytest
from src.agent.nodes.mentor import detect_mentor_mode


@pytest.mark.unit
class TestMentor:
    def test_mentor_detects_icebreaker_mode(self):
        """Mentor should detect icebreaker requests."""
        assert detect_mentor_mode("need some icebreaker ideas") == "icebreaker"
        assert detect_mentor_mode("help me start the conversation") == "icebreaker"
        assert detect_mentor_mode("give me openers") == "icebreaker"

    def test_mentor_detects_pre_date_mode(self):
        """Mentor should detect pre-date prep requests."""
        assert detect_mentor_mode("I have a date tomorrow") == "pre_date"
        assert detect_mentor_mode("nervous about meeting") == "pre_date"

    def test_mentor_detects_post_date_mode(self):
        """Mentor should detect post-date debrief requests."""
        assert detect_mentor_mode("date went well") == "post_date"
        assert detect_mentor_mode("how was the date") == "post_date"

    def test_mentor_detects_recovery_mode(self):
        """Mentor should detect recovery/support requests."""
        assert detect_mentor_mode("they ghosted me") == "recovery"
        assert detect_mentor_mode("I got rejected") == "recovery"

    def test_mentor_generates_icebreakers(self, db_fx, runner, event_fx):
        """Mentor should generate icebreakers when requested."""
        # Setup matched users
        user_id = db_fx.users.create("+1555", 100)
        db_fx.profiles.create(user_id)
        db_fx.profiles.update_summary(user_id, "Loves hiking and cooking", 1.0)
        db_fx.users.update_status(user_id, "active")

        other_id = db_fx.users.create("+1666", 101)
        db_fx.profiles.create(other_id)
        db_fx.profiles.update_summary(other_id, "Yoga enthusiast, world traveler", 1.0)

        match_id = db_fx.matches.create(user_id, other_id, 80.0)
        db_fx.matches.update_decision(match_id, user_id, "yes")
        db_fx.matches.update_decision(match_id, other_id, "yes")
        db_fx.conversation_state.upsert(
            user_id, current_node="connected", match_in_progress=match_id
        )

        result = runner.run_event(event_fx(phone="+1555", text="give me some icebreaker ideas"))

        # Should return conversation starters
        assert len(result.response) > 50

