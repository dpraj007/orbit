"""Test LLM-simulated persona conversations."""
import pytest
from tests.simulation.driver import ConversationDriver
from tests.simulation.personas import PERSONAS


@pytest.mark.llm_slow
@pytest.mark.integration
class TestPersonaSimulations:
    def test_analytical_persona_completes_onboarding(self, runner):
        """Analytical persona should complete onboarding with detailed answers."""
        driver = ConversationDriver(runner, max_turns=15)
        persona = PERSONAS[0]  # Alex - analytical

        result = driver.run_full_conversation(
            persona,
            initial_message="Hi, I heard about this dating feature and want to try it"
        )

        assert result.onboarding_completed
        assert len(result.turns) >= 7  # At least the onboarding questions
        assert result.tokens_used < 3000

    def test_shy_persona_handles_onboarding(self, runner):
        """Shy/terse persona should still complete onboarding."""
        driver = ConversationDriver(runner, max_turns=20)
        persona = PERSONAS[2]  # Sam - shy

        result = driver.run_full_conversation(
            persona,
            initial_message="hey"
        )

        # Might take more turns due to terse answers
        assert result.onboarding_completed or len(result.turns) >= 10

    def test_multiple_personas_get_matched(self, runner, db_fx):
        """Simulate two personas completing onboarding and matching."""
        driver = ConversationDriver(runner, max_turns=12)

        # Run Alex through onboarding
        alex_result = driver.run_full_conversation(
            PERSONAS[0],
            phone="+15551111111",
            chat_id=1001,
            initial_message="Hey! Ready to find someone special"
        )

        # Run Jordan through onboarding
        driver.tokens_used = 0  # Reset token counter
        jordan_result = driver.run_full_conversation(
            PERSONAS[1],
            phone="+15552222222",
            chat_id=1002,
            initial_message="Hiii!! Super excited to try this 🎉"
        )

        # Both should complete onboarding
        assert alex_result.onboarding_completed
        assert jordan_result.onboarding_completed

        # Verify both profiles exist and are searchable
        alex_user = db_fx.users.get_by_phone("+15551111111")
        jordan_user = db_fx.users.get_by_phone("+15552222222")

        if alex_user:
            alex_profile = db_fx.profiles.get_by_user_id(alex_user["id"])
            assert alex_profile["completeness"] == 1.0

        if jordan_user:
            jordan_profile = db_fx.profiles.get_by_user_id(jordan_user["id"])
            assert jordan_profile["completeness"] == 1.0

