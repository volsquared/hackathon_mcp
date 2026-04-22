from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_CONFIG_PATH = PROJECT_ROOT / "config" / "app.yaml"
DOTENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_base: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


@dataclass(frozen=True)
class AppConfig:
    llm: LLMSettings


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _load_dotenv(dotenv_path: Path = DOTENV_PATH) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_app_config(config_path: Path = APP_CONFIG_PATH) -> AppConfig:
    _load_dotenv()

    payload: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            payload = loaded

    llm_payload = payload.get("llm", {})
    if not isinstance(llm_payload, dict):
        llm_payload = {}

    llm = LLMSettings(
        enabled=_parse_bool(os.getenv("LLM_ENABLED"), _parse_bool(llm_payload.get("enabled"), False)),
        provider=str(os.getenv("LLM_PROVIDER") or llm_payload.get("provider") or "openai"),
        model=str(os.getenv("LLM_MODEL") or llm_payload.get("model") or "gpt-4.1-mini"),
        api_base=os.getenv("LLM_API_BASE") or llm_payload.get("api_base"),
        api_key_env=str(os.getenv("LLM_API_KEY_ENV") or llm_payload.get("api_key_env") or "OPENAI_API_KEY"),
    )

    return AppConfig(llm=llm)
