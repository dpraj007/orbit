"""Pytest configuration and fixtures."""
import pytest

from src.db import Database
from tests.helpers.api_stub import SeriesAPIStub
from tests.helpers.event_builder import build_event
from tests.helpers.runner import TestRunner


@pytest.fixture
def db_fx(tmp_path):
    """In-memory SQLite database for isolation."""
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def api_stub():
    """Fresh API stub per test."""
    return SeriesAPIStub()


@pytest.fixture
def runner(db_fx, api_stub):
    """Test runner with fresh DB and API stub."""
    return TestRunner(db_fx, api_stub)


@pytest.fixture
def event_fx():
    """Factory for building test events."""
    return build_event

