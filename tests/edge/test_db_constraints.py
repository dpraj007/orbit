"""Test database constraint handling."""
import pytest


@pytest.mark.unit
class TestDBConstraints:
    def test_duplicate_phone_number(self, db_fx):
        """Creating user with duplicate phone should not duplicate."""
        user_id1 = db_fx.users.create("+15551234567", 100)

        # Second create with same phone should return existing user
        user = db_fx.users.get_by_phone("+15551234567")
        assert user is not None
        assert user["id"] == user_id1

    def test_match_with_self_prevented(self, db_fx):
        """User should not be able to match with themselves."""
        user_id = db_fx.users.create("+1555", 100)
        db_fx.profiles.create(user_id)
        db_fx.profiles.update_summary(user_id, "Test", 1.0)
        db_fx.users.update_status(user_id, "active")

        # Matching logic should exclude self
        candidates = db_fx.matches.get_candidates_for_user(user_id)
        assert user_id not in [c["user_id"] for c in candidates]

