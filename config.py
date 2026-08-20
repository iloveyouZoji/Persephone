# Central configuration loader: YAML file + environment variable overrides.
import os
import yaml
from dataclasses import dataclass, field
from typing import List, Any

def _split_list_env(val: str):
    return [p.strip() for p in val.split(",")] if val else []

def _to_bool(val: Any):
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    v = str(val).lower()
    return v in ("1", "true", "yes", "on")

@dataclass
class Config:
    # Twilio
    TWILIO_ACCOUNT_SID: str = None
    TWILIO_AUTH_TOKEN: str = None
    TWILIO_NUMBER: str = None

    # App / DB
    DATABASE_URL: str = "sqlite:///polls.db"
    ADMIN_API_KEY: str = "changeme"
    PORT: int = 5000
    LOG_LEVEL: str = "INFO"

    # Poll behaviour
    POLL_OPT_OUT_KEYWORDS: List[str] = field(default_factory=lambda: ["STOP", "UNSUBSCRIBE", "QUIT", "END"])
    POLL_DEFAULT_TEMPLATE: str = "{question}\n{choices}\nReply with the code (e.g. A)"
    ALLOW_SENDING: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

def _load_yaml(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

def load_config(config_file: str = None) -> Config:
    # 1) start with defaults
    cfg = Config()

    # 2) read YAML file (if provided or env)
    path = config_file or os.getenv("CONFIG_FILE")
    if path:
        data = _load_yaml(path)
        if isinstance(data, dict):
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)

    # 3) override from env variables (if set)
    env_map = {
        "TWILIO_ACCOUNT_SID": str,
        "TWILIO_AUTH_TOKEN": str,
        "TWILIO_NUMBER": str,
        "DATABASE_URL": str,
