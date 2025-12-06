import pytest
from src.utils import (
    shared_interests,
    parse_csv,
    to_csv,
    backoff,
    chunk_text,
    safe_json,
)


class TestSharedInterests:
    def test_basic_overlap(self):
        assert shared_interests(["hiking", "cooking"], ["cooking", "reading"]) == ["cooking"]

    def test_case_insensitive(self):
        assert shared_interests(["Hiking", "COOKING"], ["cooking", "hiking"]) == ["cooking", "hiking"]

    def test_no_overlap(self):
        assert shared_interests(["hiking"], ["cooking"]) == []

    def test_empty_lists(self):
        assert shared_interests([], []) == []
        assert shared_interests(["hiking"], []) == []

    def test_whitespace_handling(self):
        assert shared_interests([" hiking "], ["hiking"]) == ["hiking"]


class TestParseCsv:
    def test_basic(self):
        assert parse_csv("a, b, c") == ["a", "b", "c"]

    def test_empty(self):
        assert parse_csv("") == []
        assert parse_csv(None) == []

    def test_whitespace(self):
        assert parse_csv("  a  ,  b  ") == ["a", "b"]


class TestToCsv:
    def test_basic(self):
        result = to_csv(["b", "a", "c"])
        assert result == "a, b, c"

    def test_deduplicates(self):
        result = to_csv(["a", "a", "b"])
        assert result == "a, b"

    def test_empty(self):
        assert to_csv([]) == ""


class TestBackoff:
    def test_exponential_growth(self):
        assert backoff(0) == pytest.approx(0.5, rel=0.1)
        assert backoff(1) == pytest.approx(1.05, rel=0.1)
        assert backoff(2) == pytest.approx(2.1, rel=0.1)

    def test_cap(self):
        assert backoff(10) <= 8.5  # cap + small jitter


class TestChunkText:
    def test_short_text(self):
        assert chunk_text("hello", 100) == ["hello"]

    def test_long_text(self):
        text = "a" * 100
        chunks = chunk_text(text, 30)
        assert len(chunks) == 4
        assert "".join(chunks) == text


class TestSafeJson:
    def test_valid_dict(self):
        assert safe_json({"a": 1}) == '{"a": 1}'

    def test_non_serializable(self):
        result = safe_json(object())
        assert "object" in result
