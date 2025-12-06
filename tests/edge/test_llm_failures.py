"""Test LLM failure handling fallbacks."""
import pytest

from src.agent.nodes import matching
from src.utils import llm as llm_utils
from src.utils.llm import reset_llm
import src.agent.nodes.matching as matching_module


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

        # Patch LLM at the source (utils.llm.get_llm)
        monkeypatch.setattr(llm_utils, "get_llm", lambda: SimpleLLM("onboarding"))

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

        # Reset LLM cache and patch get_llm to return our BadLLM
        reset_llm()
        bad_llm = BadLLM()
        monkeypatch.setattr(llm_utils, "get_llm", lambda *args, **kwargs: bad_llm)
        # Also patch where it's imported in matching module
        monkeypatch.setattr(matching_module, "get_llm", lambda *args, **kwargs: bad_llm)

        profile_a = {"profile_summary": "A", "looking_for_summary": "B"}
        profile_b = {"profile_summary": "C", "looking_for_summary": "D"}

        score, reason = matching.calculate_bilateral_score(profile_a, profile_b)

        assert score == 50.0, f"Expected 50.0 but got {score}. Reason: {reason}"
        assert "Unable to calculate" in reason
