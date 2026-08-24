# llm.py
# The LLM client as a reusable dependency: configured in one place, injected
# into any route, and swappable in tests via app.dependency_overrides.
import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Optional: any OpenAI-compatible endpoint. Unset means api.openai.com.
LLM_BASE_URL = os.getenv("LLM_BASE_URL")


@lru_cache  # one client for the whole app, like a connection pool
def get_llm_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return AsyncOpenAI(base_url=LLM_BASE_URL, api_key=api_key)
