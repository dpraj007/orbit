import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from .utils import utc_now_iso


class UserStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.log = logging.getLogger("orbit.store")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                chat_id INTEGER,
                name TEXT,
                created_at TEXT,
                updated_at TEXT,
                dating_enabled INTEGER DEFAULT 1,
                status TEXT
            );
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_summary TEXT,
                looking_for_summary TEXT,
                dealbreakers TEXT,
                interests TEXT,
                communication_style TEXT,
                relationship_goal TEXT,
                completeness REAL DEFAULT 0.0,
                onboarding_step INTEGER DEFAULT 0,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_a_id INTEGER NOT NULL,
                user_b_id INTEGER NOT NULL,
                bilateral_score REAL,
                status TEXT,
                user_a_decision TEXT DEFAULT 'pending',
                user_b_decision TEXT DEFAULT 'pending',
                created_at TEXT,
                resolved_at TEXT,
                FOREIGN KEY (user_a_id) REFERENCES users(id),
                FOREIGN KEY (user_b_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS conversation_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                current_node TEXT,
                context TEXT,
                match_in_progress INTEGER,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (match_in_progress) REFERENCES matches(id)
            );
            """
        )
        self.conn.commit()

    def get_user_by_phone(self, phone: str) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM users WHERE phone_number=?", (phone,))
        return cur.fetchone()

    def get_user_by_id(self, user_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return cur.fetchone()

    def create_user(self, phone: str, chat_id: int, status: str = "onboarding") -> int:
        now = utc_now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO users (phone_number, chat_id, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (phone, chat_id, now, now, status),
        )
        self.conn.commit()
        user_id = int(cur.lastrowid)

        # Create empty profile
        self.conn.execute(
            """
            INSERT INTO profiles (user_id, updated_at, completeness, onboarding_step)
            VALUES (?, ?, 0.0, 0)
            """,
            (user_id, now),
        )
        self.conn.commit()
        return user_id

    def update_user(self, user_id: int, **kwargs) -> None:
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key}=?")
                values.append(value)

        if not fields:
            return

        fields.append("updated_at=?")
        values.append(utc_now_iso())
        values.append(user_id)

        query = f"UPDATE users SET {', '.join(fields)} WHERE id=?"
        self.conn.execute(query, values)
        self.conn.commit()

    def get_profile(self, user_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,))
        return cur.fetchone()

    def update_profile(self, user_id: int, **kwargs) -> None:
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key}=?")
                values.append(value)

        if not fields:
            return

        fields.append("updated_at=?")
        values.append(utc_now_iso())
        values.append(user_id)

        query = f"UPDATE profiles SET {', '.join(fields)} WHERE user_id=?"
        self.conn.execute(query, values)
        self.conn.commit()

    def get_conversation_state(self, user_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM conversation_state WHERE user_id=?", (user_id,))
        return cur.fetchone()

    def upsert_conversation_state(self, user_id: int, current_node: str, context: Dict, match_in_progress: Optional[int] = None) -> None:
        existing = self.get_conversation_state(user_id)
        now = utc_now_iso()
        context_json = json.dumps(context)

        if existing:
            self.conn.execute(
                """
                UPDATE conversation_state
                SET current_node=?, context=?, match_in_progress=?, updated_at=?
                WHERE user_id=?
                """,
                (current_node, context_json, match_in_progress, now, user_id),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO conversation_state (user_id, current_node, context, match_in_progress, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, current_node, context_json, match_in_progress, now),
            )
        self.conn.commit()

    def create_match(self, user_a_id: int, user_b_id: int, bilateral_score: float, status: str = "pending_a") -> int:
        now = utc_now_iso()
        cur = self.conn.execute(
            """
            INSERT INTO matches (user_a_id, user_b_id, bilateral_score, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_a_id, user_b_id, bilateral_score, status, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_match(self, match_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM matches WHERE id=?", (match_id,))
        return cur.fetchone()

    def update_match_decision(self, match_id: int, user_id: int, decision: str) -> None:
        match = self.get_match(match_id)
        if not match:
            return

        field = "user_a_decision" if match["user_a_id"] == user_id else "user_b_decision"
        other_field = "user_b_decision" if field == "user_a_decision" else "user_a_decision"
        other_decision = match[other_field]

        # Determine new status
        if decision == "no":
            new_status = "rejected"
        elif decision == "yes" and other_decision == "yes":
            new_status = "mutual"
        elif decision == "yes":
            new_status = "pending_b" if field == "user_a_decision" else "pending_a"
        else:
            new_status = match["status"]

        self.conn.execute(
            f"UPDATE matches SET {field}=?, status=?, resolved_at=? WHERE id=?",
            (decision, new_status, utc_now_iso() if new_status in ["mutual", "rejected"] else None, match_id),
        )
        self.conn.commit()

    def get_browsing_users(self, exclude_user_id: int) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            """
            SELECT u.*, p.profile_summary, p.looking_for_summary, p.interests, p.communication_style, p.relationship_goal
            FROM users u
            JOIN profiles p ON u.id = p.user_id
            WHERE u.id != ? AND u.status = 'browsing' AND p.completeness >= 0.5
            """,
            (exclude_user_id,),
        )
        return cur.fetchall()

    def close(self) -> None:
        self.conn.close()
