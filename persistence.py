# persistence.py
from pathlib import Path
import os
import csv

def _resolve_csv_dir(csv_dir=None):
    """Prefer caller-provided path; else env; else /client_configs."""
    if csv_dir:
        return Path(csv_dir)
    env_dir = os.getenv("CSV_DIR")
    return Path(env_dir) if env_dir else Path("/client_configs")

CSV_DIR = Path(os.getenv("CSV_DIR", "/app/client_configs"))
CSV_DIR.mkdir(parents=True, exist_ok=True)
