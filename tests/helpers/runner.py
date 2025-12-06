"""Test runner for executing events through the graph."""
import logging
from dataclasses import dataclass
from typing import Any, Optional

from src.agent import build_graph
from src.kafka import KafkaEvent
from src.db import Database
from tests.helpers.api_stub import APICall, SeriesAPIStub


@dataclass
class RunResult:
    """Result of running an event through the graph."""
    response: str
    db_state: dict  # Snapshot of user, profile, conversation_state
    api_calls: list[APICall]
    trace: list[str]  # Node transitions
    error: Optional[str] = None


class TestRunner:
    """Executes events through the graph and captures results."""

    def __init__(self, db: Database, api_stub: SeriesAPIStub):
        self.db = db
        self.api = api_stub
        self.graph = build_graph(db, api_stub)
        self.log = logging.getLogger("test.runner")
        self.traces: list[str] = []

    def run_event(self, event: dict) -> RunResult:
        """Process single event, return structured result."""
        self.api.reset()  # Clear API call history

        try:
            kafka_event = KafkaEvent.from_dict(event)
            data = kafka_event.data

            phone = data.from_phone
            chat_id = data.chat_id
            text = (data.text or "").strip()
            chat_handles = data.chat_handles or []

            if not phone or chat_id is None:
                return RunResult("", {}, [], [], "Missing phone or chat_id")

            # Skip group messages for now (unless @orbit is mentioned)
            is_group = len(chat_handles) > 2
            if is_group and "@orbit" not in text.lower():
                return RunResult("", {}, [], [], None)  # Skipped

            initial_state = {
                "phone_number": phone,
                "chat_id": chat_id,
                "message": text,
                "db_updates": [],
            }

            result = self.graph.invoke(initial_state)

            # Capture DB state after run
            user = self.db.users.get_by_phone(phone)
            profile = None
            conv_state = None

            if user:
                profile_row = self.db.profiles.get_by_user_id(user["id"])
                profile = dict(profile_row) if profile_row else None
                conv_row = self.db.conversation_state.get_by_user_id(user["id"])
                conv_state = dict(conv_row) if conv_row else None

            return RunResult(
                response=result.get("response", ""),
                db_state={
                    "user": dict(user) if user else None,
                    "profile": dict(profile) if profile else None,
                    "conversation_state": dict(conv_state) if conv_state else None,
                },
                api_calls=self.api.calls.copy(),
                trace=self.traces.copy(),
                error=result.get("error"),
            )

        except Exception as exc:
            self.log.exception("Event processing failed")
            return RunResult("", {}, [], [], str(exc))

    def run_conversation(self, events: list[dict]) -> list[RunResult]:
        """Run a sequence of events, returning all results."""
        return [self.run_event(e) for e in events]

