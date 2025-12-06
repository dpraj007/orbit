import pytest
from unittest.mock import patch, MagicMock

from src.llm import WingmanLLM


@pytest.fixture
def llm():
    return WingmanLLM(api_key="test-key", model="test-model", timeout=5.0)


class TestWingmanLLM:
    def test_classify_intent(self, llm):
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "onboarding"}}]
            }
            mock_post.return_value = mock_response

            result = llm.classify_intent("My name is Alice", "ONBOARDING")

            assert result == "onboarding"
            mock_post.assert_called_once()

    def test_classify_intent_fallback_on_error(self, llm):
        with patch("httpx.post") as mock_post:
            mock_post.side_effect = Exception("API error")

            result = llm.classify_intent("Hello", "")

            assert result == "general"

    def test_extract_onboarding_step_0(self, llm):
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"name": "Alice", "passion": "hiking"}'}}]
            }
            mock_post.return_value = mock_response

            result = llm.extract_onboarding(0, "I'm Alice and I love hiking")

            assert result["name"] == "Alice"
            assert result["passion"] == "hiking"

    def test_extract_onboarding_fallback_on_error(self, llm):
        with patch("httpx.post") as mock_post:
            mock_post.side_effect = Exception("API error")

            result = llm.extract_onboarding(0, "Hello")

            assert result == {}

    def test_craft_reply(self, llm):
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Great suggestion!"}}]
            }
            mock_post.return_value = mock_response

            result = llm.craft_reply("Give me advice", temperature=0.8)

            assert result == "Great suggestion!"

    def test_craft_reply_fallback_on_error(self, llm):
        with patch("httpx.post") as mock_post:
            mock_post.side_effect = Exception("API error")

            result = llm.craft_reply("Give me advice")

            assert result == "Mind grabbing that again?"

    def test_missing_api_key_raises(self):
        llm = WingmanLLM(api_key="", model="test-model")

        with pytest.raises(RuntimeError, match="Missing OPENROUTER_API_KEY"):
            llm._post_chat([{"role": "user", "content": "test"}])

    def test_headers_include_auth(self, llm):
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "response"}}]
            }
            mock_post.return_value = mock_response

            llm.craft_reply("test")

            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer test-key"
            assert headers["X-Title"] == "Orbit Wingman"
