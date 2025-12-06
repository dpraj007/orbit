"""Utility package for shared helpers."""
import logging
import sys
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Get current UTC time as ISO format string."""
    return datetime.now(timezone.utc).isoformat()


def setup_logger(level: str = "INFO") -> logging.Logger:
    """Configure and return the root logger for the application."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Return orbit logger
    logger = logging.getLogger("orbit")
    logger.setLevel(log_level)
    return logger


__all__ = ["utc_now_iso", "setup_logger"]
