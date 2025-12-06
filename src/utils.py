import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def setup_logger(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger("orbit")


def chunk_text(text: str, max_len: int = 4000) -> List[str]:
    if len(text) <= max_len:
        return [text]
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def shared_interests(a: Iterable[str], b: Iterable[str]) -> List[str]:
    set_a = {x.strip().lower() for x in a if x}
    set_b = {x.strip().lower() for x in b if x}
    return sorted(set_a.intersection(set_b))


def backoff(retry: int, base: float = 0.5, cap: float = 8.0) -> float:
    return min(cap, base * (2 ** retry)) + (0.05 * retry)


def parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def to_csv(values: Iterable[str]) -> str:
    return ", ".join(sorted({v.strip() for v in values if v and v.strip()}))
