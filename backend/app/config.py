import os
from pathlib import Path
from dotenv import load_dotenv

# Load from backend/.env or root .env
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip() or os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("XAI_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b").strip()
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()


def get_llm_config() -> tuple[str, str, str]:
    """
    Returns (api_key, base_url, model_name) with automatic routing:
    - Keys starting with 'gsk_' or model 'openai/gpt-oss-120b' route to Groq Cloud endpoint.
    - Keys starting with 'xai-' route to xAI Grok Cloud endpoint.
    - Explicit LLM_BASE_URL / GROQ_BASE_URL / XAI_BASE_URL takes precedence if set.
    """
    api_key = (
        os.getenv("XAI_API_KEY", "").strip()
        or os.getenv("GROQ_API_KEY", "").strip()
    )
    explicit_base = (
        os.getenv("LLM_BASE_URL", "").strip()
        or os.getenv("GROQ_BASE_URL", "").strip()
    )
    model_name = os.getenv("LLM_MODEL", "").strip() or "openai/gpt-oss-120b"

    if explicit_base and explicit_base != "https://api.x.ai/v1":
        base_url = explicit_base
    elif api_key.startswith("gsk_") or "gpt-oss" in model_name.lower():
        base_url = "https://api.groq.com/openai/v1"
    elif api_key.startswith("xai-"):
        base_url = "https://api.x.ai/v1"
    else:
        base_url = os.getenv("XAI_BASE_URL", "https://api.groq.com/openai/v1").strip()

    return api_key, base_url, model_name

