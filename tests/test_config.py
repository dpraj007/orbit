import pytest
import os
from unittest.mock import patch

from src.config import Config, _get_env


class TestGetEnv:
    def test_returns_value(self):
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            assert _get_env("TEST_VAR") == "test_value"

    def test_returns_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _get_env("MISSING_VAR", "default") == "default"

    def test_raises_on_missing_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="Missing required env var"):
                _get_env("MISSING_VAR")


class TestConfig:
    def test_from_env(self):
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "test-topic",
            "KAFKA_CONSUMER_GROUP": "test-group",
            "KAFKA_CLIENT_ID": "test-client",
            "KAFKA_SASL_USERNAME": "user",
            "KAFKA_SASL_PASSWORD": "pass",
            "SERIES_BASE_URL": "https://api.example.com/",
            "SERIES_API_KEY": "api-key",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()

        assert cfg.ingress_mode == "kafka"
        assert cfg.kafka_bootstrap == "localhost:9092"
        assert cfg.kafka_topic == "test-topic"
        assert cfg.kafka_group == "test-group"
        assert cfg.kafka_sasl_username == "user"
        assert cfg.series_base_url == "https://api.example.com"  # Trailing slash stripped
        assert cfg.log_level == "DEBUG"

    def test_default_values(self):
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "test-topic",
            "KAFKA_CONSUMER_GROUP": "test-group",
            "KAFKA_CLIENT_ID": "test-client",
            "KAFKA_SASL_USERNAME": "user",
            "KAFKA_SASL_PASSWORD": "pass",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()

        assert cfg.kafka_security_protocol == "SASL_SSL"
        assert cfg.kafka_sasl_mechanism == "PLAIN"
        assert cfg.request_timeout == 10.0
        assert cfg.max_retries == 3
        assert cfg.poll_interval_sec == 3.0
        assert cfg.log_level == "INFO"

    def test_api_mode_does_not_require_kafka_env(self):
        env = {
            "INGRESS_MODE": "api",
            "SERIES_BASE_URL": "https://api.example.com",
            "SERIES_API_KEY": "key",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = Config.from_env()

        assert cfg.ingress_mode == "api"
        assert cfg.kafka_bootstrap == ""
        assert cfg.kafka_topic == ""
