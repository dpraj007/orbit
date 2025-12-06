import pytest
from unittest.mock import patch, MagicMock
import httpx

from src.client import SeriesClient


@pytest.fixture
def client():
    return SeriesClient(
        base_url="https://api.example.com",
        api_key="test-key",
        timeout=5.0,
        max_retries=2,
        sender_number="+15550000000",
    )


class TestSeriesClient:
    def test_send_message(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b'{"id": 123}'
            mock_response.json.return_value = {"id": 123}
            mock_request.return_value = mock_response

            result = client.send_message(42, "Hello!")

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert "/api/chats/42/chat_messages" in call_args[0][1]
            assert call_args[1]["json"]["message"]["text"] == "Hello!"
            assert result == {"id": 123}

    def test_send_message_with_attachments(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b'{}'
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            client.send_message(42, "Check this out", attachments=[{"url": "http://example.com/img.png"}])

            call_args = mock_request.call_args
            payload = call_args[1]["json"]
            assert payload["message"]["attachments"] == [{"url": "http://example.com/img.png"}]

    def test_create_group_chat(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b'{"chat": {"id": 999}}'
            mock_response.json.return_value = {"chat": {"id": 999}}
            mock_request.return_value = mock_response

            result = client.create_group_chat(
                ["+15551111111", "+15552222222"],
                "Welcome!",
                display_name="Test Chat",
            )

            call_args = mock_request.call_args
            payload = call_args[1]["json"]
            assert "+15551111111" in payload["chat"]["phone_numbers"]
            assert payload["message"]["text"] == "Welcome!"
            assert payload["chat"]["display_name"] == "Test Chat"
            assert payload["send_from"] == "+15550000000"
            assert result["chat"]["id"] == 999

    def test_set_typing(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b''
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            client.set_typing(42)

            call_args = mock_request.call_args
            assert "/api/chats/42/start_typing" in call_args[0][1]

    def test_send_reaction(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b''
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            client.send_reaction(123, "love")

            call_args = mock_request.call_args
            assert "/api/chat_messages/123/reactions" in call_args[0][1]
            assert call_args[1]["json"]["type"] == "love"

    def test_list_chats(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b'{"data": [{"id": 1}]}'
            mock_response.json.return_value = {"data": [{"id": 1}]}
            mock_request.return_value = mock_response

            chats = list(client.list_chats(phone_number="+1555", page=2, per_page=10))

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert "/api/chats" in call_args[0][1]
            assert call_args[1]["params"]["phone_number"] == "+1555"
            assert call_args[1]["params"]["page"] == 2
            assert call_args[1]["params"]["per_page"] == 10
            assert chats == [{"id": 1}]

    def test_list_chat_messages(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b'{"data": [{"id": 5}]}'
            mock_response.json.return_value = {"data": [{"id": 5}]}
            mock_request.return_value = mock_response

            messages = list(client.list_chat_messages(99, page=3, per_page=5))

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert "/api/chats/99/chat_messages" in call_args[0][1]
            assert call_args[1]["params"]["page"] == 3
            assert call_args[1]["params"]["per_page"] == 5
            assert messages == [{"id": 5}]

    def test_retry_on_failure(self, client):
        with patch("httpx.request") as mock_request:
            # Fail first, succeed second
            mock_response_fail = MagicMock()
            mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=MagicMock()
            )

            mock_response_ok = MagicMock()
            mock_response_ok.raise_for_status = MagicMock()
            mock_response_ok.content = b'{}'
            mock_response_ok.json.return_value = {}

            mock_request.side_effect = [mock_response_fail, mock_response_ok]

            with patch("time.sleep"):  # Skip actual sleep
                result = client.send_message(42, "Hello!")

            assert mock_request.call_count == 2
            assert result == {}

    def test_auth_header(self, client):
        with patch("httpx.request") as mock_request:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.content = b'{}'
            mock_response.json.return_value = {}
            mock_request.return_value = mock_response

            client.send_message(42, "Hello!")

            call_args = mock_request.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer test-key"
