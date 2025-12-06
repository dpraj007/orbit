"""LLM client utilities."""
import os
from pathlib import Path
from typing import Optional

from langchain_openai import ChatOpenAI

try:
    from dotenv import load_dotenv
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

_llm_instance: Optional[ChatOpenAI] = None


def get_llm(temperature: float = 0.4) -> ChatOpenAI:
    """Get or create LLM instance."""
    global _llm_instance

    # Use OpenRouter with OpenAI-compatible interface
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL", "x-ai/grok-2-1212")

    if not _llm_instance:
        _llm_instance = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=temperature,
            max_tokens=1000,
        )

    return _llm_instance


def reset_llm() -> None:
    """Reset LLM instance (useful for testing)."""
    global _llm_instance
    _llm_instance = None
