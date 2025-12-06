import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _get_env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


@dataclass
class Config:
    ingress_mode: str
    kafka_bootstrap: str
    kafka_topic: str
    kafka_group: str
    kafka_client_id: str
    kafka_sasl_username: str
    kafka_sasl_password: str
    kafka_security_protocol: str = "SASL_SSL"
    kafka_sasl_mechanism: str = "PLAIN"

    series_base_url: str = ""
    series_api_key: str = ""
    series_sender_number: str = ""

    openrouter_api_key: str = ""
    openrouter_model: str = "x-ai/grok-4.1-fast"

    request_timeout: float = 10.0
    max_retries: int = 3
    stale_threshold_min: int = 45
    poll_interval_sec: float = 3.0
    db_path: str = "./orbit.db"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        if load_dotenv:
            env_path = Path(".env")
            if env_path.exists():
                load_dotenv(env_path)
        ingress_mode = os.environ.get("INGRESS_MODE", "api").lower()
        use_kafka = ingress_mode == "kafka"
        return cls(
            ingress_mode=ingress_mode,
            kafka_bootstrap=_get_env("KAFKA_BOOTSTRAP_SERVERS") if use_kafka else "",
            kafka_topic=_get_env("KAFKA_TOPIC") if use_kafka else "",
            kafka_group=_get_env("KAFKA_CONSUMER_GROUP") if use_kafka else "",
            kafka_client_id=_get_env("KAFKA_CLIENT_ID") if use_kafka else "",
            kafka_sasl_username=_get_env("KAFKA_SASL_USERNAME") if use_kafka else "",
            kafka_sasl_password=_get_env("KAFKA_SASL_PASSWORD") if use_kafka else "",
            kafka_security_protocol=os.environ.get("KAFKA_SECURITY_PROTOCOL", "SASL_SSL"),
            kafka_sasl_mechanism=os.environ.get("KAFKA_SASL_MECHANISM", "PLAIN"),
            series_base_url=os.environ.get("SERIES_BASE_URL", "").rstrip("/"),
            series_api_key=os.environ.get("SERIES_API_KEY", ""),
            series_sender_number=os.environ.get("SERIES_SENDER_NUMBER", ""),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            openrouter_model=os.environ.get("OPENROUTER_MODEL", "x-ai/grok-4.1-fast"),
            request_timeout=float(os.environ.get("REQUEST_TIMEOUT_SEC", "10")),
            max_retries=int(os.environ.get("MAX_RETRIES", "3")),
            stale_threshold_min=int(os.environ.get("STALE_THRESHOLD_MIN", "45")),
            poll_interval_sec=float(os.environ.get("POLL_INTERVAL_SEC", "3")),
            db_path=os.environ.get("DATABASE_PATH", "./orbit.db"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
