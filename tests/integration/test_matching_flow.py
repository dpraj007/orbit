"""Test matching flow with two users."""
import pytest
from src.agent.nodes import matching
import src.agent.router as router


@pytest.mark.integration
class TestMatchingFlow:
    def test_mutual_match_creates_group(self, db_fx, api_stub, runner, event_fx, monkeypatch):
        """Two users match and get connected via group chat."""
        # Ensure deterministic high score and pitch without real LLM calls
        class StubLLM:
            def __init__(self, content: str):
                self.content = content

            def invoke(self, *_args, **_kwargs):
                class Response:
                    def __init__(self, text: str):
                        self.content = text
                return Response(self.content)

        monkeypatch.setattr(router, "get_llm", lambda: StubLLM("matching"))
        monkeypatch.setattr(matching, "calculate_bilateral_score", lambda *_: (90.0, "great fit"))
        monkeypatch.setattr(matching, "generate_match_pitch", lambda *_, **__: "Awesome match!")

        # Setup User A (completed onboarding)
        user_a_phone = "+15551111111"
        user_a_chat = 1001
        user_a_id = db_fx.users.create(user_a_phone, user_a_chat)
        db_fx.profiles.create(user_a_id)
        db_fx.profiles.update_summary(user_a_id, "Alex loves hiking and tech", 1.0)
        db_fx.profiles.update_field(user_a_id, "looking_for_summary", "Active, curious partner")
        db_fx.users.update_status(user_a_id, "active")

        # Setup User B
        user_b_phone = "+15552222222"
        user_b_chat = 1002
        user_b_id = db_fx.users.create(user_b_phone, user_b_chat)
        db_fx.profiles.create(user_b_id)
        db_fx.profiles.update_summary(user_b_id, "Jordan is adventurous and outgoing", 1.0)
        db_fx.profiles.update_field(user_b_id, "looking_for_summary", "Someone thoughtful and active")
        db_fx.users.update_status(user_b_id, "active")

        # User A requests match
        result_a = runner.run_event(event_fx(phone=user_a_phone, chat_id=user_a_chat, text="find me a match"))
        assert "intro" in result_a.response.lower() or "yes" in result_a.response.lower()

        # User A says yes
        runner.run_event(event_fx(phone=user_a_phone, chat_id=user_a_chat, text="yes"))

        # User B says yes (they got notified)
        runner.run_event(event_fx(phone=user_b_phone, chat_id=user_b_chat, text="yes"))

        # Check group chat was created
        group_calls = [c for c in api_stub.calls if c.method == "create_group_chat"]
        assert group_calls, "Expected create_group_chat to be called for mutual match"
        assert user_a_phone in group_calls[0].payload["phone_numbers"]
        assert user_b_phone in group_calls[0].payload["phone_numbers"]

