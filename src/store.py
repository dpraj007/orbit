import logging
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .utils import parse_csv, to_csv, utc_now_iso


class UserStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.log = logging.getLogger("orbit.store")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                phone_number TEXT PRIMARY KEY,
                name TEXT,
                status TEXT,
                profile_bio TEXT,
                profile_interests TEXT,
                profile_vibe TEXT,
                profile_dealbreakers TEXT,
                current_match_id INTEGER,
                active_group_chat_id INTEGER,
                last_dm_chat_id INTEGER,
                last_seen_at TEXT,
                last_intro_at TEXT,
                onboarding_step INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_a TEXT NOT NULL,
                user_b TEXT NOT NULL,
                shared_interests TEXT,
                proposed_at TEXT,
                state TEXT,
                user_a_decision TEXT,
                user_b_decision TEXT
            );
            """
        )
        self.conn.commit()

    def get_user(self, phone: str) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM users WHERE phone_number=?", (phone,))
        return cur.fetchone()

    def upsert_user(
        self,
        phone: str,
        status: str,
        name: Optional[str] = None,
        profile_bio: Optional[str] = None,
        profile_interests: Optional[str] = None,
        profile_vibe: Optional[str] = None,
        profile_dealbreakers: Optional[str] = None,
        onboarding_step: Optional[int] = None,
        last_dm_chat_id: Optional[int] = None,
    ) -> None:
        now = utc_now_iso()
        existing = self.get_user(phone)
        if existing:
            self.conn.execute(
                """
                UPDATE users
                SET status=?, name=COALESCE(?, name), profile_bio=COALESCE(?, profile_bio),
                    profile_interests=COALESCE(?, profile_interests),
                    profile_vibe=COALESCE(?, profile_vibe),
                    profile_dealbreakers=COALESCE(?, profile_dealbreakers),
                    onboarding_step=COALESCE(?, onboarding_step),
                    last_dm_chat_id=COALESCE(?, last_dm_chat_id),
                    last_seen_at=?
                WHERE phone_number=?
                """,
                (
                    status,
                    name,
                    profile_bio,
                    profile_interests,
                    profile_vibe,
                    profile_dealbreakers,
                    onboarding_step,
                    last_dm_chat_id,
                    now,
                    phone,
                ),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO users (phone_number, status, name, profile_bio, profile_interests,
                    profile_vibe, profile_dealbreakers, onboarding_step, last_seen_at, last_dm_chat_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    phone,
                    status,
                    name,
                    profile_bio,
                    profile_interests,
                    profile_vibe,
                    profile_dealbreakers,
                    onboarding_step if onboarding_step is not None else 0,
                    now,
                    last_dm_chat_id,
                ),
            )
        self.conn.commit()

    def update_profile(
        self,
        phone: str,
        name: Optional[str] = None,
        passion: Optional[str] = None,
        vibe: Optional[str] = None,
        dealbreakers: Optional[Iterable[str]] = None,
        interests: Optional[Iterable[str]] = None,
    ) -> None:
        user = self.get_user(phone)
        if not user:
            return
        new_interests = to_csv(parse_csv(user["profile_interests"]) + (list(interests) if interests else []))
        new_dealbreakers = to_csv(parse_csv(user["profile_dealbreakers"]) + (list(dealbreakers) if dealbreakers else []))
        bio_parts = [part for part in [user["profile_bio"], passion] if part]
        bio = ". ".join([p.strip() for p in bio_parts if p.strip()])
        self.conn.execute(
            """
            UPDATE users
            SET name=COALESCE(?, name),
                profile_bio=?,
                profile_interests=?,
                profile_vibe=COALESCE(?, profile_vibe),
                profile_dealbreakers=?,
                last_seen_at=?
            WHERE phone_number=?
            """,
            (
                name,
                bio,
                new_interests,
                vibe,
                new_dealbreakers,
                utc_now_iso(),
                phone,
            ),
        )
        self.conn.commit()

    def set_status(self, phone: str, status: str) -> None:
        self.conn.execute(
            "UPDATE users SET status=?, last_seen_at=? WHERE phone_number=?",
            (status, utc_now_iso(), phone),
        )
        self.conn.commit()

    def set_onboarding_step(self, phone: str, step: int) -> None:
        self.conn.execute(
            "UPDATE users SET onboarding_step=?, last_seen_at=? WHERE phone_number=?",
            (step, utc_now_iso(), phone),
        )
        self.conn.commit()

    def set_current_match(self, phone: str, match_id: Optional[int]) -> None:
        self.conn.execute(
            "UPDATE users SET current_match_id=?, last_seen_at=? WHERE phone_number=?",
            (match_id, utc_now_iso(), phone),
        )
        self.conn.commit()

    def set_group_chat(self, phone: str, chat_id: Optional[int]) -> None:
        self.conn.execute(
            "UPDATE users SET active_group_chat_id=?, last_intro_at=?, last_seen_at=? WHERE phone_number=?",
            (chat_id, utc_now_iso(), utc_now_iso(), phone),
        )
        self.conn.commit()

    def set_last_dm_chat(self, phone: str, chat_id: int) -> None:
        self.conn.execute(
            "UPDATE users SET last_dm_chat_id=?, last_seen_at=? WHERE phone_number=?",
            (chat_id, utc_now_iso(), phone),
        )
        self.conn.commit()

    def get_browsing_candidates(self, exclude_phone: str) -> List[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT * FROM users WHERE phone_number != ? AND status = 'BROWSING'",
            (exclude_phone,),
        )
        return cur.fetchall()

    def create_match(
        self, user_a: str, user_b: str, shared_interests: Iterable[str], state: str = "proposed"
    ) -> int:
        shared = to_csv(shared_interests)
        cur = self.conn.execute(
            """
            INSERT INTO matches (user_a, user_b, shared_interests, proposed_at, state, user_a_decision, user_b_decision)
            VALUES (?, ?, ?, ?, ?, 'pending', 'pending')
            """,
            (user_a, user_b, shared, utc_now_iso(), state),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_match(self, match_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM matches WHERE id=?", (match_id,))
        return cur.fetchone()

    def update_match_decision(self, match_id: int, phone: str, decision: str) -> None:
        match = self.get_match(match_id)
        if not match:
            return
        field = "user_a_decision" if match["user_a"] == phone else "user_b_decision"
        self.conn.execute(
            f"UPDATE matches SET {field}=?, state=? WHERE id=?",
            (
                decision,
                self._resolve_state(decision, match, phone, field),
                match_id,
            ),
        )
        self.conn.commit()

    def _resolve_state(self, decision: str, match: sqlite3.Row, phone: str, field: str) -> str:
        other_field = "user_b_decision" if field == "user_a_decision" else "user_a_decision"
        other_decision = match[other_field]
        if decision == "no":
            return "declined"
        if decision == "yes" and other_decision == "yes":
            return "mutual"
        if decision == "yes":
            return "proposed"
        return match["state"]

    def list_shared_interests(self, phone: str) -> List[str]:
        user = self.get_user(phone)
        if not user:
            return []
        return parse_csv(user["profile_interests"])
