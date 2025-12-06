"""Test configuration loading."""
import pytest
from unittest.mock import patch
from src.config import Config


@pytest.fixture
def set_required_env(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("KAFKA_TOPIC", "test-topic")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "test-group")
    monkeypatch.setenv("KAFKA_CLIENT_ID", "test-client")
    monkeypatch.setenv("KAFKA_SASL_USERNAME", "test-user")
    monkeypatch.setenv("KAFKA_SASL_PASSWORD", "test-pass")


@pytest.mark.unit
class TestConfig:
    def test_config_requires_kafka_vars(self, monkeypatch):
        """Config should fail if required Kafka vars are missing."""
        # Clear all Kafka env vars to ensure test works even with .env file
        kafka_vars = [
            "KAFKA_BOOTSTRAP_SERVERS",
            "KAFKA_TOPIC",
            "KAFKA_CONSUMER_GROUP",
            "KAFKA_CLIENT_ID",
            "KAFKA_SASL_USERNAME",
            "KAFKA_SASL_PASSWORD",
        ]
        for var in kafka_vars:
            monkeypatch.delenv(var, raising=False)
        
        # Prevent .env file from loading
        with patch('src.config.load_dotenv', lambda *args, **kwargs: None):
            with pytest.raises(RuntimeError, match="Missing required env var"):
                Config.from_env()

    def test_config_defaults(self, monkeypatch, set_required_env):
        """Config should use sensible defaults."""
        cfg = Config.from_env()
        assert cfg.log_level == "INFO"
        assert cfg.max_retries == 3
        assert cfg.request_timeout == 10.0
        assert cfg.db_path == "./orbit.db"

    def test_config_custom_values(self, monkeypatch, set_required_env):
        """Config should respect custom env values."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("MAX_RETRIES", "5")
        monkeypatch.setenv("DATABASE_PATH", "/tmp/test.db")

        cfg = Config.from_env()
        assert cfg.log_level == "DEBUG"
        assert cfg.max_retries == 5
        assert cfg.db_path == "/tmp/test.db"

