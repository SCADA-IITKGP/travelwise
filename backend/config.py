import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

APP_ENV = os.getenv("APP_ENV", "development")

DEFAULT_LLM_BASE_URL = "https://103.42.50.41:1034/v1"
DEFAULT_LLM_MODEL = "Qwen/Qwen3-8B"
DEFAULT_EMBEDDING_BASE_URL = "https://103.42.50.41:1035/v1"
DEFAULT_EMBEDDING_MODEL = "bge-small-en-v1.5"


def _default_ca_cert(filename: str) -> str:
    candidate = ROOT / "certs" / filename
    return str(candidate) if candidate.is_file() else ""


_raw_llm_key = os.getenv("LLM_API_KEY") or os.getenv("QWEN_API_KEY") or ""
LLM_MODE = (os.getenv("LLM_MODE") or ("hosted" if _raw_llm_key else "mock")).lower()
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or os.getenv("QWEN_BASE_URL") or DEFAULT_LLM_BASE_URL).rstrip("/")
LLM_API_KEY = _raw_llm_key
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("QWEN_MODEL") or DEFAULT_LLM_MODEL
LLM_CA_CERT_FILE = os.getenv("LLM_CA_CERT_FILE") or os.getenv("QWEN_CA_CERT") or _default_ca_cert("vm04-ca.crt")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_TOKENS = min(1024, max(1, int(os.getenv("LLM_MAX_TOKENS", "512"))))

EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "hybrid").lower()
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", DEFAULT_EMBEDDING_BASE_URL).rstrip("/")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
EMBEDDING_CA_CERT_FILE = os.getenv("EMBEDDING_CA_CERT_FILE") or _default_ca_cert("vm02-ca.crt")
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
EMBEDDING_BATCH_SIZE = min(16, max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))))
EMBEDDING_MAX_TOKENS = min(512, max(1, int(os.getenv("EMBEDDING_MAX_TOKENS", "512"))))
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))

TEAM_TOKEN_QUOTA = int(os.getenv("TEAM_TOKEN_QUOTA", "100000"))
MAX_AGENT_STEPS = min(10, max(1, int(os.getenv("MAX_AGENT_STEPS", "10"))))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "app.db"))
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(DATA_DIR / "policies")))
INGESTION_DIR = Path(os.getenv("INGESTION_DIR", str(DATA_DIR / "ingested_policies")))
