"""Database connection and table management."""
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from ..utils import utc_now_iso
from .queries import (
    ConversationStateQueries,
    MatchQueries,
    ProfileQueries,
    UserQueries,
)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.log = logging.getLogger("orbit.db")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

        # Initialize query objects
        self.users = UserQueries(self.conn)
        self.profiles = ProfileQueries(self.conn)
        self.matches = MatchQueries(self.conn)
        self.conversation_state = ConversationStateQueries(self.conn)

    def _init_tables(self) -> None:
        """Initialize all database tables."""
        self.conn.executescript(
            """
            -- Users table
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                chat_id INTEGER,
                name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                dating_enabled BOOLEAN DEFAULT 1,
                status TEXT DEFAULT 'onboarding'
            );

            -- Profiles table with natural language summaries
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
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

            -- Matches table
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_a_id INTEGER NOT NULL,
                user_b_id INTEGER NOT NULL,
                bilateral_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending_a',
                user_a_decision TEXT DEFAULT 'pending',
                user_b_decision TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (user_a_id) REFERENCES users(id),
                FOREIGN KEY (user_b_id) REFERENCES users(id)
            );

            -- Conversation state table
            CREATE TABLE IF NOT EXISTS conversation_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                current_node TEXT,
                context TEXT,
                match_in_progress INTEGER,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (match_in_progress) REFERENCES matches(id)
            );

            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number);
            CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
            CREATE INDEX IF NOT EXISTS idx_matches_users ON matches(user_a_id, user_b_id);
            CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
            """
        )
        self.conn.commit()
        self.log.info("Database initialized at %s", self.db_path)

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
