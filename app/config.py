# app/config.py
from pathlib import Path
import os

try:
    # optional, only if python-dotenv is installed
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Project root (folder that contains the "app/" directory)
BASE_DIR = Path(__file__).resolve().parents[1]

# Absolute data root; override with DATA_ROOT env if you want
DEFAULT_DATA_ROOT = BASE_DIR / "data"

class _Settings:
    DATA_ROOT: str = os.getenv("DATA_ROOT", str(BASE_DIR / "data"))
    DATA_URL_PREFIX: str = os.getenv("DATA_URL_PREFIX", "/data")
    API_BASE: str = os.getenv("API_BASE", "https://simfba.azurewebsites.net/api/statistics/interface/v2")
    ADMIN_BEARER_TOKEN: str = os.getenv("ADMIN_BEARER_TOKEN", "changeme")
    PLAYERS_CSV: str = os.getenv("PLAYERS_CSV", "data/playerdetails.csv")
    def __init__(self):
        self.API_BASE = os.getenv(
            "API_BASE",
            "https://simfba.azurewebsites.net/api/statistics/interface/v2",
        )
        # ensure absolute path
        self.DATA_ROOT = os.getenv("DATA_ROOT", str(DEFAULT_DATA_ROOT))
        if not Path(self.DATA_ROOT).is_absolute():
            self.DATA_ROOT = str((BASE_DIR / self.DATA_ROOT).resolve())

        self.ADMIN_BEARER_TOKEN = os.getenv("ADMIN_BEARER_TOKEN", "")
        self.RUN_TOKEN = os.getenv("RUN_TOKEN")  # optional

        print(f"[config] DATA_ROOT = {self.DATA_ROOT}")
        print(f"[config] API_BASE  = {self.API_BASE}")
        print(f"[config] API_BASE  = {self.DATA_URL_PREFIX}")

settings = _Settings()
