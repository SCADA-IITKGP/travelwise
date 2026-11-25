import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
APP_ENV = os.getenv("APP_ENV", "development")
LLM_MODE = os.getenv("LLM_MODE", "mock").lower()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_CA_CERT_FILE = os.getenv("LLM_CA_CERT_FILE", "")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_TOKENS = min(1024, max(1, int(os.getenv("LLM_MAX_TOKENS", "512"))))
TEAM_TOKEN_QUOTA = int(os.getenv("TEAM_TOKEN_QUOTA", "100000"))
MAX_AGENT_STEPS = min(10, max(1, int(os.getenv("MAX_AGENT_STEPS", "10"))))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "app.db"))
POLICY_DIR = Path(os.getenv("POLICY_DIR", str(DATA_DIR / "policies")))
INGESTION_DIR = Path(os.getenv("INGESTION_DIR", str(DATA_DIR / "ingested_policies")))
