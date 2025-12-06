import pytest
import tempfile
import os
from src.store import UserStore


@pytest.fixture
def store():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = UserStore(path)
    yield s
    s.conn.close()
    os.unlink(path)


class TestUserStore:
    def test_create_and_get_user(self, store):
        store.upsert_user("+15551234567", status="ONBOARDING", name="Alice")
        user = store.get_user("+15551234567")
        assert user is not None
        assert user["name"] == "Alice"
        assert user["status"] == "ONBOARDING"

    def test_get_nonexistent_user(self, store):
        assert store.get_user("+10000000000") is None

    def test_update_existing_user(self, store):
        store.upsert_user("+15551234567", status="ONBOARDING", name="Alice")
        store.upsert_user("+15551234567", status="BROWSING", name="Alice Updated")
        user = store.get_user("+15551234567")
        assert user["status"] == "BROWSING"
        assert user["name"] == "Alice Updated"

    def test_set_status(self, store):
        store.upsert_user("+15551234567", status="ONBOARDING")
        store.set_status("+15551234567", "IN_ORBIT")
        user = store.get_user("+15551234567")
        assert user["status"] == "IN_ORBIT"

    def test_onboarding_step(self, store):
        store.upsert_user("+15551234567", status="ONBOARDING", onboarding_step=0)
        store.set_onboarding_step("+15551234567", 1)
        user = store.get_user("+15551234567")
        assert user["onboarding_step"] == 1

    def test_update_profile(self, store):
        store.upsert_user("+15551234567", status="ONBOARDING")
        store.update_profile(
            "+15551234567",
            name="Bob",
            passion="hiking",
            vibe="chill adventurous curious",
            dealbreakers=["smoking"],
            interests=["hiking", "cooking"],
        )
        user = store.get_user("+15551234567")
        assert user["name"] == "Bob"
        assert "hiking" in user["profile_bio"]
        assert user["profile_vibe"] == "chill adventurous curious"
        assert "smoking" in user["profile_dealbreakers"]
        assert "hiking" in user["profile_interests"]

    def test_set_last_dm_chat(self, store):
        store.upsert_user("+15551234567", status="ONBOARDING")
        store.set_last_dm_chat("+15551234567", 999)
        user = store.get_user("+15551234567")
        assert user["last_dm_chat_id"] == 999

    def test_ensure_user_inserts_and_does_not_override(self, store):
        store.ensure_user("+15551112222", name="First", status="BROWSING")
        user = store.get_user("+15551112222")
        assert user is not None
        assert user["name"] == "First"
        assert user["status"] == "BROWSING"

        # Existing row should remain unchanged
        store.ensure_user("+15551112222", name="Second", status="IN_ORBIT")
        user = store.get_user("+15551112222")
        assert user["name"] == "First"
        assert user["status"] == "BROWSING"

    def test_chat_offsets(self, store):
        assert store.get_last_message_id(123) is None
        store.set_last_message_id(123, 10)
        assert store.get_last_message_id(123) == 10
        store.set_last_message_id(123, 25)
        assert store.get_last_message_id(123) == 25


class TestMatching:
    def test_create_and_get_match(self, store):
        store.upsert_user("+15551111111", status="BROWSING")
        store.upsert_user("+15552222222", status="BROWSING")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking", "cooking"])
        match = store.get_match(match_id)
        assert match is not None
        assert match["user_a"] == "+15551111111"
        assert match["user_b"] == "+15552222222"
        assert "hiking" in match["shared_interests"]
        assert match["state"] == "proposed"
        assert match["user_a_decision"] == "pending"
        assert match["user_b_decision"] == "pending"

    def test_get_browsing_candidates(self, store):
        store.upsert_user("+15551111111", status="BROWSING")
        store.upsert_user("+15552222222", status="BROWSING")
        store.upsert_user("+15553333333", status="ONBOARDING")
        candidates = store.get_browsing_candidates("+15551111111")
        phones = [c["phone_number"] for c in candidates]
        assert "+15552222222" in phones
        assert "+15551111111" not in phones  # Excluded
        assert "+15553333333" not in phones  # Not browsing

    def test_match_decision_yes_yes(self, store):
        store.upsert_user("+15551111111", status="BROWSING")
        store.upsert_user("+15552222222", status="BROWSING")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking"])
        store.update_match_decision(match_id, "+15551111111", "yes")
        match = store.get_match(match_id)
        assert match["user_a_decision"] == "yes"
        assert match["state"] == "proposed"  # Still waiting for B

        store.update_match_decision(match_id, "+15552222222", "yes")
        match = store.get_match(match_id)
        assert match["user_b_decision"] == "yes"
        assert match["state"] == "mutual"

    def test_match_decision_decline(self, store):
        store.upsert_user("+15551111111", status="BROWSING")
        store.upsert_user("+15552222222", status="BROWSING")
        match_id = store.create_match("+15551111111", "+15552222222", ["hiking"])
        store.update_match_decision(match_id, "+15551111111", "no")
        match = store.get_match(match_id)
        assert match["state"] == "declined"

    def test_set_current_match(self, store):
        store.upsert_user("+15551111111", status="BROWSING")
        store.set_current_match("+15551111111", 42)
        user = store.get_user("+15551111111")
        assert user["current_match_id"] == 42

    def test_set_group_chat(self, store):
        store.upsert_user("+15551111111", status="IN_ORBIT")
        store.set_group_chat("+15551111111", 123)
        user = store.get_user("+15551111111")
        assert user["active_group_chat_id"] == 123
        assert user["last_intro_at"] is not None


class TestListSharedInterests:
    def test_list_shared_interests(self, store):
        store.upsert_user("+15551111111", status="BROWSING", profile_interests="hiking, cooking, reading")
        interests = store.list_shared_interests("+15551111111")
        assert "hiking" in interests
        assert "cooking" in interests
        assert len(interests) == 3

    def test_list_shared_interests_empty(self, store):
        store.upsert_user("+15551111111", status="BROWSING")
        interests = store.list_shared_interests("+15551111111")
        assert interests == []
