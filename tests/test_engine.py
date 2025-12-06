import json
import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch

from src.store import UserStore
from src.engine import (
    process_event,
    handle_onboarding,
    try_match,
    handle_match_decision,
    launch_group_intro,
    handle_sidebar,
    handle_group_message,
    ONBOARDING_QUESTIONS,
)


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = UserStore(path)
    yield s
    s.conn.close()
    os.unlink(path)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.send_message = MagicMock()
    client.set_typing = MagicMock()
    client.create_group_chat = MagicMock(return_value={"chat": {"id": 999}})
    return client


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.extract_onboarding = MagicMock(return_value={"name": "Alice", "passion": "hiking"})
    llm.craft_reply = MagicMock(return_value="Great match suggestion!")
    return llm


class TestProcessEvent:
    def test_new_user_starts_onboarding(self, store, mock_client, mock_llm):
        event = {
            "event_type": "message.received",
            "data": {
                "chat_id": 100,
                "text": "Hello",
                "from_phone": "+15551234567",
                "chat_handles": ["+15551234567", "+1orbit"],
            },
        }
        process_event(event, mock_client, store, mock_llm)

        user = store.get_user("+15551234567")
        assert user is not None
        assert user["status"] == "ONBOARDING"
        assert user["onboarding_step"] == 0
        mock_client.send_message.assert_called_once()
        assert ONBOARDING_QUESTIONS[0] in mock_client.send_message.call_args[0][1]

    def test_skips_event_missing_phone(self, store, mock_client, mock_llm):
        event = {"data": {"chat_id": 100, "text": "Hello"}}
        process_event(event, mock_client, store, mock_llm)
        mock_client.send_message.assert_not_called()

    def test_skips_event_missing_chat_id(self, store, mock_client, mock_llm):
        event = {"data": {"from_phone": "+15551234567", "text": "Hello"}}
        process_event(event, mock_client, store, mock_llm)
        mock_client.send_message.assert_not_called()

    def test_group_message_routed_correctly(self, store, mock_client, mock_llm):
        # Create user first
        store.upsert_user("+15551234567", status="IN_ORBIT")
        event = {
            "data": {
                "chat_id": 100,
                "text": "Hey @orbit help!",
                "from_phone": "+15551234567",
                "chat_handles": ["+15551111111", "+15552222222", "+15553333333"],
            },
        }
        process_event(event, mock_client, store, mock_llm)
        # Should call LLM for group message with @orbit mention
        mock_llm.craft_reply.assert_called()

    def test_process_event_handles_message_block_payload(self, store, mock_client, mock_llm):
        event = {
            "data": {
                "message": {"text": "Hello there", "from_phone": "+15550000001", "chat_id": 321},
                "chat": {
                    "id": 321,
                    "chat_handles": [{"phone_number": "+15550000001"}, {"phone_number": "+15550000002"}],
                },
            }
        }
        process_event(event, mock_client, store, mock_llm)

        user = store.get_user("+15550000001")
        assert user is not None
        assert user["status"] == "ONBOARDING"
        mock_client.send_message.assert_called_once()

    def test_process_event_handles_chat_message_payload(self, store, mock_client, mock_llm):
        event = {
            "data": {
                "chat_message": {"text": "Hey", "from_phone": "+15550000004", "chat_id": 777},
                "chat": {"id": 777, "chat_handles": [{"phone_number": "+15550000004"}, {"phone_number": "+15550000005"}]},
            }
        }
        process_event(event, mock_client, store, mock_llm)

        user = store.get_user("+15550000004")
        assert user is not None
        assert user["status"] == "ONBOARDING"
        mock_client.send_message.assert_called_once()

    def test_process_event_handles_stringified_payload(self, store, mock_client, mock_llm):
        payload = json.dumps(
            {"text": "Hi!", "from_phone": "+15550000003", "chat_id": 654, "chat_handles": ["+1555", "+1666"]}
        )
        process_event({"data": payload}, mock_client, store, mock_llm)

        user = store.get_user("+15550000003")
        assert user is not None
        assert user["status"] == "ONBOARDING"
        mock_client.send_message.assert_called_once()


class TestOnboarding:
    def test_advances_through_steps(self, store, mock_client, mock_llm):
        store.upsert_user("+15551234567", status="ONBOARDING", onboarding_step=0, last_dm_chat_id=100)
        user = store.get_user("+15551234567")

        # Step 0 -> 1
        handle_onboarding(user, "I'm Alice and I love hiking", 100, store, mock_client, mock_llm)
        user = store.get_user("+15551234567")
        assert user["onboarding_step"] == 1
        assert ONBOARDING_QUESTIONS[1] in mock_client.send_message.call_args[0][1]

    def test_completes_onboarding(self, store, mock_client, mock_llm):
        store.upsert_user("+15551234567", status="ONBOARDING", onboarding_step=2, last_dm_chat_id=100)
        mock_llm.extract_onboarding = MagicMock(return_value={"dealbreakers": ["smoking"]})
        user = store.get_user("+15551234567")

        handle_onboarding(user, "No smokers please", 100, store, mock_client, mock_llm)
        user = store.get_user("+15551234567")
        assert user["status"] == "BROWSING"
        assert user["onboarding_step"] == 3


class TestMatching:
    def test_try_match_no_candidates(self, store, mock_client, mock_llm):
        store.upsert_user("+15551234567", status="BROWSING", profile_interests="hiking")
        try_match("+15551234567", 100, store, mock_client, mock_llm)
        mock_client.send_message.assert_called_once()
        assert "still looking" in mock_client.send_message.call_args[0][1].lower()

    def test_try_match_finds_candidate(self, store, mock_client, mock_llm):
        store.upsert_user("+15551234567", status="BROWSING", profile_interests="hiking, cooking")
        store.upsert_user("+15559999999", status="BROWSING", profile_interests="hiking, reading", last_dm_chat_id=200)

        try_match("+15551234567", 100, store, mock_client, mock_llm)

        user = store.get_user("+15551234567")
        candidate = store.get_user("+15559999999")
        assert user["status"] == "PENDING_INTRO"
        assert candidate["status"] == "PENDING_INTRO"
        assert user["current_match_id"] is not None
        # Should notify both users
        assert mock_client.send_message.call_count == 2


class TestMatchDecision:
    def test_decline_returns_to_browsing(self, store, mock_client):
        store.upsert_user("+15551111111", status="PENDING_INTRO")
        store.upsert_user("+15552222222", status="PENDING_INTRO")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking"])
        store.set_current_match("+15551111111", match_id)
        store.set_current_match("+15552222222", match_id)

        user = store.get_user("+15551111111")
        handle_match_decision(user, "no", 100, store, mock_client)

        user = store.get_user("+15551111111")
        other = store.get_user("+15552222222")
        assert user["status"] == "BROWSING"
        assert other["status"] == "BROWSING"
        assert user["current_match_id"] is None

    def test_mutual_yes_launches_intro(self, store, mock_client):
        store.upsert_user("+15551111111", status="PENDING_INTRO", name="Alice")
        store.upsert_user("+15552222222", status="PENDING_INTRO", name="Bob")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking"])
        store.set_current_match("+15551111111", match_id)
        store.set_current_match("+15552222222", match_id)

        # First user says yes
        store.update_match_decision(match_id, "+15551111111", "yes")
        user_a = store.get_user("+15551111111")
        handle_match_decision(user_a, "yes", 100, store, mock_client)

        # Second user says yes
        user_b = store.get_user("+15552222222")
        handle_match_decision(user_b, "yes", 200, store, mock_client)

        # Should create group chat
        mock_client.create_group_chat.assert_called_once()
        user_a = store.get_user("+15551111111")
        user_b = store.get_user("+15552222222")
        assert user_a["status"] == "IN_ORBIT"
        assert user_b["status"] == "IN_ORBIT"

    def test_unclear_response_asks_for_clarification(self, store, mock_client):
        store.upsert_user("+15551111111", status="PENDING_INTRO")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking"])
        store.set_current_match("+15551111111", match_id)

        user = store.get_user("+15551111111")
        handle_match_decision(user, "maybe later", 100, store, mock_client)

        assert "yes or no" in mock_client.send_message.call_args[0][1].lower()


class TestGroupIntro:
    def test_launch_group_intro(self, store, mock_client):
        store.upsert_user("+15551111111", status="PENDING_INTRO", name="Alice")
        store.upsert_user("+15552222222", status="PENDING_INTRO", name="Bob")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking"])
        match = store.get_match(match_id)

        launch_group_intro("+15551111111", "+15552222222", match, store, mock_client)

        mock_client.create_group_chat.assert_called_once()
        call_args = mock_client.create_group_chat.call_args
        assert "+15551111111" in call_args[0][0]
        assert "+15552222222" in call_args[0][0]
        assert "Alice" in call_args[0][1]
        assert "Bob" in call_args[0][1]

        user_a = store.get_user("+15551111111")
        user_b = store.get_user("+15552222222")
        assert user_a["status"] == "IN_ORBIT"
        assert user_b["status"] == "IN_ORBIT"


class TestSidebar:
    def test_handle_sidebar_calls_llm(self, store, mock_client, mock_llm):
        store.upsert_user("+15551234567", status="IN_ORBIT", profile_bio="Loves hiking", profile_interests="hiking")
        user = store.get_user("+15551234567")

        handle_sidebar(user, "What should I say next?", 100, store, mock_client, mock_llm)

        mock_llm.craft_reply.assert_called_once()
        mock_client.send_message.assert_called_once()


class TestGroupMessage:
    def test_ignores_message_without_mention(self, mock_client, mock_llm):
        handle_group_message("Hey how are you?", 100, mock_client, mock_llm)
        mock_llm.craft_reply.assert_not_called()
        mock_client.send_message.assert_not_called()

    def test_responds_to_orbit_mention(self, mock_client, mock_llm):
        handle_group_message("Hey @orbit what should we talk about?", 100, mock_client, mock_llm)
        mock_llm.craft_reply.assert_called_once()
        mock_client.send_message.assert_called_once()

    def test_case_insensitive_mention(self, mock_client, mock_llm):
        handle_group_message("Hey @ORBIT help us!", 100, mock_client, mock_llm)
        mock_llm.craft_reply.assert_called_once()
