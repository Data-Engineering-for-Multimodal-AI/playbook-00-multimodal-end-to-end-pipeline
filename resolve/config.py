"""Paths and settings (environment variables override the defaults)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("RESOLVE_DATA", ROOT / "data"))
MULTIMODAL = DATA / "multimodal"
ANALOG = DATA / "analog"
OUTPUT = Path(os.environ.get("RESOLVE_OUTPUT", ROOT / "output"))
SCHEMAS = ROOT / "schemas"
IMAGES_PER_READING = 2
FUSION_TIMEOUT_S = 5.0   # a reading waits this long (in data time) for its images, then fuses without them
# Optional LLM planner: any OpenAI-compatible chat API (for example a local Ollama server)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
