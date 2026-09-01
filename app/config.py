"""Configuration and mode detection.

The app runs in one of two modes and says so loudly, because the single
most dangerous failure at a hackathon demo is not knowing whether what you
just saw came from the live API or from a fixture.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

FIXTURES = ROOT / "fixtures"
STATIC = ROOT / "static"

PC_BASE = os.getenv("PERFECTCORP_BASE_URL", "https://yce-api-01.makeupar.com").rstrip("/")
PC_KEY = os.getenv("PERFECTCORP_API_KEY", "").strip()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5").strip()

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY", "").strip()

XANO_INSTANCE_BASE_URL = os.getenv("XANO_INSTANCE_BASE_URL", "").strip().rstrip("/")
XANO_API_GROUP_BASE = os.getenv("XANO_API_GROUP_BASE", "").strip()
XANO_TOKEN = os.getenv("XANO_PERSONAL_ACCESS_TOKEN", "").strip()

# Four or fewer keeps us in the cheaper SD tier (9 units vs 12).
# Never mix SD and HD concern names in one request - the API 400s.
CONCERNS = ["wrinkle", "pore", "texture", "acne"]

# Force fixtures even when a key is present. Use this while iterating on UI
# so you don't quietly burn your ~83-111 lifetime analyses.
FORCE_FIXTURE = os.getenv("GLOWPROOF_FORCE_FIXTURE", "").lower() in ("1", "true", "yes")

LIVE_SKIN = bool(PC_KEY) and not FORCE_FIXTURE

# Anthropic wins if both are present; otherwise whichever key exists.
# Neither means the canned routine, which is honest but identical for everyone.
LLM_PROVIDER = ("anthropic" if ANTHROPIC_KEY
                else "gemini" if GEMINI_KEY
                else None)
LIVE_LLM = LLM_PROVIDER is not None

# Both the instance host and the API group path are required to call the
# generated /scans endpoints. The personal access token is separate (it's
# for Xano's own CLI/MCP admin surface) and only needed here if you turn on
# auth for those endpoints, so it is not part of this check.
LIVE_XANO = bool(XANO_INSTANCE_BASE_URL and XANO_API_GROUP_BASE)


def mode_banner() -> str:
    skin = "LIVE" if LIVE_SKIN else "FIXTURE"
    llm = LLM_PROVIDER or "CANNED"
    history = "XANO" if LIVE_XANO else "IN-MEMORY"
    return f"skin-analysis={skin}  routine={llm}  history={history}"
