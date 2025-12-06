"""Database query operations."""
import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from ..utils import utc_now_iso


class UserQueries:
    """User-related database queries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.log = logging.getLogger("orbit.db.users")

    def get_by_phone(self, phone: str) -> Optional[sqlite3.Row]:
        """Get user by phone number."""
        cur = self.conn.execute(
            "SELECT * FROM users WHERE phone_number = ?", (phone,)
        )
        return cur.fetchone()

    def get_by_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """Get user by ID."""
        cur = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()

    def create(
        self, phone: str, chat_id: Optional[int] = None, name: Optional[str] = None
    ) -> int:
        """Create new user."""
        now = utc_now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO users (phone_number, chat_id, name, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, 'onboarding')
            """,
            (phone, chat_id, name, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_status(self, user_id: int, status: str) -> None:
        """Update user status."""
        self.conn.execute(
            "UPDATE users SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now_iso(), user_id),
        )
        self.conn.commit()

    def update_chat_id(self, user_id: int, chat_id: int) -> None:
        """Update user's chat ID."""
        self.conn.execute(
            "UPDATE users SET chat_id = ?, updated_at = ? WHERE id = ?",
            (chat_id, utc_now_iso(), user_id),
        )
        self.conn.commit()

    def get_all(self) -> list:
        """Return all users."""
        cur = self.conn.execute("SELECT * FROM users")
        return cur.fetchall()

    def upsert_profile_with_defaults(
        self,
        phone: str,
        name: str,
        chat_id: int | None = None,
        profile_summary: str | None = None,
        looking_for_summary: str | None = None,
    ) -> int:
        """Ensure a user + profile exists with provided defaults."""
        user = self.get_by_phone(phone)
        if not user:
            user_id = self.create(phone, chat_id, name=name)
        else:
            user_id = user["id"]
            if chat_id and not user.get("chat_id"):
                self.update_chat_id(user_id, chat_id)
        return user_id


class ProfileQueries:
    """Profile-related database queries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.log = logging.getLogger("orbit.db.profiles")

    def get_by_user_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """Get profile by user ID."""
        cur = self.conn.execute(
            "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
        )
        return cur.fetchone()

    def create(self, user_id: int) -> int:
        """Create new profile."""
        cur = self.conn.execute(
            """
            INSERT INTO profiles (user_id, updated_at, completeness, onboarding_step)
            VALUES (?, ?, 0.0, 0)
            """,
            (user_id, utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_summary(
        self, user_id: int, profile_summary: str, completeness: float
    ) -> None:
        """Update profile summary."""
        self.conn.execute(
            """
            UPDATE profiles
            SET profile_summary = ?, completeness = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (profile_summary, completeness, utc_now_iso(), user_id),
        )
        self.conn.commit()

    def update_looking_for(self, user_id: int, looking_for_summary: str) -> None:
        """Update looking-for summary."""
        self.conn.execute(
            """
            UPDATE profiles
            SET looking_for_summary = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (looking_for_summary, utc_now_iso(), user_id),
        )
        self.conn.commit()

    def update_field(self, user_id: int, field: str, value: Any) -> None:
        """Update a specific profile field."""
        self.conn.execute(
            f"UPDATE profiles SET {field} = ?, updated_at = ? WHERE user_id = ?",
            (value, utc_now_iso(), user_id),
        )
        self.conn.commit()

    def increment_step(self, user_id: int) -> int:
        """Increment onboarding step."""
        profile = self.get_by_user_id(user_id)
        if not profile:
            return 0
        new_step = (profile["onboarding_step"] or 0) + 1
        self.update_field(user_id, "onboarding_step", new_step)
        return new_step

    def get_all_active(self) -> List[sqlite3.Row]:
        """Get all profiles with completeness > 0.5."""
        cur = self.conn.execute(
            """
            SELECT p.*, u.phone_number, u.name
            FROM profiles p
            JOIN users u ON p.user_id = u.id
            WHERE p.completeness >= 0.5 AND u.dating_enabled = 1
            """
        )
        return cur.fetchall()


class MatchQueries:
    """Match-related database queries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.log = logging.getLogger("orbit.db.matches")

    def force_mutual(self, match_id: int) -> None:
        """Force a match to mutual yes for both sides."""
        self.conn.execute(
            """
            UPDATE matches
            SET status='mutual', user_a_decision='yes', user_b_decision='yes', resolved_at=?
            WHERE id=?
            """,
            (utc_now_iso(), match_id),
        )
        self.conn.commit()

    def create(
        self, user_a_id: int, user_b_id: int, bilateral_score: float = 0.0
    ) -> int:
        """Create new match."""
        cur = self.conn.execute(
            """
            INSERT INTO matches (user_a_id, user_b_id, bilateral_score, created_at, status)
            VALUES (?, ?, ?, ?, 'pending_a')
            """,
            (user_a_id, user_b_id, bilateral_score, utc_now_iso()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_by_id(self, match_id: int) -> Optional[sqlite3.Row]:
        """Get match by ID."""
        cur = self.conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        return cur.fetchone()

    def update_decision(
        self, match_id: int, user_id: int, decision: str
    ) -> Optional[sqlite3.Row]:
        """Update match decision and resolve status."""
        match = self.get_by_id(match_id)
        if not match:
            return None

        # Determine which user is making the decision
        if match["user_a_id"] == user_id:
            field = "user_a_decision"
            other_decision = match["user_b_decision"]
        else:
            field = "user_b_decision"
            other_decision = match["user_a_decision"]

        # Update decision
        self.conn.execute(
            f"UPDATE matches SET {field} = ? WHERE id = ?", (decision, match_id)
        )

        # Update status based on decisions
        new_status = match["status"]
        if decision == "no":
            new_status = "rejected"
            self.conn.execute(
                "UPDATE matches SET status = ?, resolved_at = ? WHERE id = ?",
                (new_status, utc_now_iso(), match_id),
            )
        elif decision == "yes" and other_decision == "yes":
            new_status = "mutual"
            self.conn.execute(
                "UPDATE matches SET status = ?, resolved_at = ? WHERE id = ?",
                (new_status, utc_now_iso(), match_id),
            )
        elif decision == "yes":
            # First yes, waiting for other
            if match["status"] == "pending_a":
                new_status = "pending_b"
            self.conn.execute(
                "UPDATE matches SET status = ? WHERE id = ?", (new_status, match_id)
            )

        self.conn.commit()
        return self.get_by_id(match_id)

    def get_pending_for_user(self, user_id: int) -> List[sqlite3.Row]:
        """Get pending matches for a user."""
        cur = self.conn.execute(
            """
            SELECT * FROM matches
            WHERE (user_a_id = ? OR user_b_id = ?)
            AND status LIKE 'pending%'
            """,
            (user_id, user_id),
        )
        return cur.fetchall()

    def get_candidates_for_user(
        self, user_id: int, min_score: float = 60.0
    ) -> List[sqlite3.Row]:
        """Get potential match candidates (users not already matched)."""
        cur = self.conn.execute(
            """
            SELECT u.*, p.*
            FROM users u
            JOIN profiles p ON u.id = p.user_id
            WHERE u.id != ?
            AND u.dating_enabled = 1
            AND p.completeness >= 0.5
            AND u.id NOT IN (
                SELECT user_b_id FROM matches WHERE user_a_id = ?
                UNION
                SELECT user_a_id FROM matches WHERE user_b_id = ?
            )
            """,
            (user_id, user_id, user_id),
        )
        return cur.fetchall()


class ConversationStateQueries:
    """Conversation state queries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.log = logging.getLogger("orbit.db.state")

    _UNSET = object()

    def get_by_user_id(self, user_id: int) -> Optional[sqlite3.Row]:
        """Get conversation state for user."""
        cur = self.conn.execute(
            "SELECT * FROM conversation_state WHERE user_id = ?", (user_id,)
        )
        return cur.fetchone()

    def get_all(self) -> List[sqlite3.Row]:
        """Get all conversation_state rows."""
        cur = self.conn.execute("SELECT * FROM conversation_state")
        return cur.fetchall()

    def upsert(
        self,
        user_id: int,
        current_node: Optional[str] = None,
        context: Optional[Dict] = None,
        match_in_progress: Optional[int] | object = _UNSET,
    ) -> None:
        """Create or update conversation state."""
        context_json = json.dumps(context) if context else None
        existing = self.get_by_user_id(user_id)

        # Decide stored values (explicit None should clear, _UNSET preserves existing)
        match_value = None
        if match_in_progress is ConversationStateQueries._UNSET:
            match_value = existing["match_in_progress"] if existing else None
        else:
            match_value = match_in_progress

        if existing:
            self.conn.execute(
                """
                UPDATE conversation_state
                SET current_node = ?, context = ?, match_in_progress = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    current_node or existing["current_node"],
                    context_json or existing["context"],
                    match_value,
                    utc_now_iso(),
                    user_id,
                ),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO conversation_state (user_id, current_node, context, match_in_progress, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, current_node, context_json, match_value, utc_now_iso()),
            )
        self.conn.commit()

    def get_context(self, user_id: int) -> Optional[Dict]:
        """Get parsed context for user."""
        state = self.get_by_user_id(user_id)
        if not state or not state["context"]:
            return None
        try:
            return json.loads(state["context"])
        except json.JSONDecodeError:
            return None
