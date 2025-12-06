"""Test LLM failure handling fallbacks."""
import pytest

from src.agent.nodes import matching


@pytest.mark.unit
class TestLLMFailures:
    def test_llm_timeout_graceful_fallback(self, runner, event_fx, monkeypatch):
        """Agent should provide fallback response on LLM timeout."""

        class FailingLLM:
            def invoke(self, *_args, **_kwargs):
                raise TimeoutError("LLM timeout")

        class SimpleLLM:
            def __init__(self, content: str):
                self.content = content

            def invoke(self, *_args, **_kwargs):
                class Response:
                    def __init__(self, text: str):
                        self.content = text

                return Response(self.content)

        # Patch all LLM entrypoints used in this flow
        import src.agent.router as router

        monkeypatch.setattr(matching, "get_llm", lambda: FailingLLM())
        monkeypatch.setattr(router, "get_llm", lambda: SimpleLLM("onboarding"))

        result = runner.run_event(event_fx(text="find me a match"))

        assert result.response  # Should return a fallback response
        assert result.error is None

    def test_llm_invalid_json_response(self, monkeypatch):
        """Agent should handle malformed LLM JSON responses."""

        class BadLLM:
            def invoke(self, *_args, **_kwargs):
                class Response:
                    content = "not-json"

                return Response()

        monkeypatch.setattr(matching, "get_llm", lambda: BadLLM())

        profile_a = {"profile_summary": "A", "looking_for_summary": "B"}
        profile_b = {"profile_summary": "C", "looking_for_summary": "D"}

        score, reason = matching.calculate_bilateral_score(profile_a, profile_b)

        assert score == 50.0
        assert "Unable to calculate" in reason
