from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import os
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_CONFIG_PATH = PROJECT_ROOT / "config" / "app.yaml"
DOTENV_PATH = PROJECT_ROOT / ".env"
OVERLAY_CONFIG_PATH = PROJECT_ROOT / ".workshop" / "overlay_config.json"


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_base: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


@dataclass(frozen=True)
class OverlayLLMSettings:
    enabled: bool | None = None
    provider: str | None = None
    model: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None


@dataclass(frozen=True)
class OverlaySettings:
    router: str = "deterministic"
    tool_descriptions: str = "default"
    system_prompt: str = "default"
    format: str = "default"
    ontology: str = "none"
    exercise_id: str | None = None
    option_applied: str | None = None
    confirmation_output_file: str | None = None
    confirmation_trigger_function: str | None = None
    confirmation_selected_tool: str | None = None
    confirmation_matched_keyword: str | None = None
    llm: OverlayLLMSettings = OverlayLLMSettings()


@dataclass(frozen=True)
class AppConfig:
    llm: LLMSettings
    overlay: OverlaySettings


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


def _load_overlay_payload(overlay_path: Path = OVERLAY_CONFIG_PATH) -> dict[str, Any]:
    if not overlay_path.exists():
        return {}
    loaded = json.loads(overlay_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _parse_overlay_settings(payload: dict[str, Any]) -> OverlaySettings:
    llm_payload = payload.get("llm", {})
    if not isinstance(llm_payload, dict):
        llm_payload = {}

    return OverlaySettings(
        router=str(payload.get("router") or "deterministic"),
        tool_descriptions=str(payload.get("tool_descriptions") or "default"),
        system_prompt=str(payload.get("system_prompt") or "default"),
        format=str(payload.get("format") or "default"),
        ontology=str(payload.get("ontology") or "none"),
        exercise_id=str(payload["exercise_id"]) if payload.get("exercise_id") is not None else None,
        option_applied=str(payload["option_applied"]) if payload.get("option_applied") is not None else None,
        confirmation_output_file=str(payload["confirmation_output_file"]) if payload.get("confirmation_output_file") is not None else None,
        confirmation_trigger_function=str(payload["confirmation_trigger_function"]) if payload.get("confirmation_trigger_function") is not None else None,
        confirmation_selected_tool=str(payload["confirmation_selected_tool"]) if payload.get("confirmation_selected_tool") is not None else None,
        confirmation_matched_keyword=str(payload["confirmation_matched_keyword"]) if payload.get("confirmation_matched_keyword") is not None else None,
        llm=OverlayLLMSettings(
            enabled=_parse_bool(llm_payload.get("enabled")) if "enabled" in llm_payload else None,
            provider=str(llm_payload["provider"]) if llm_payload.get("provider") is not None else None,
            model=str(llm_payload["model"]) if llm_payload.get("model") is not None else None,
            api_base=str(llm_payload["api_base"]) if llm_payload.get("api_base") is not None else None,
            api_key_env=str(llm_payload["api_key_env"]) if llm_payload.get("api_key_env") is not None else None,
        ),
    )


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

    overlay_payload = _load_overlay_payload()
    overlay = _parse_overlay_settings(overlay_payload)

    llm = LLMSettings(
        enabled=_parse_bool(
            os.getenv("LLM_ENABLED"),
            overlay.llm.enabled if overlay.llm.enabled is not None else _parse_bool(llm_payload.get("enabled"), False),
        ),
        provider=str(os.getenv("LLM_PROVIDER") or overlay.llm.provider or llm_payload.get("provider") or "openai"),
        model=str(os.getenv("LLM_MODEL") or overlay.llm.model or llm_payload.get("model") or "gpt-4.1-mini"),
        api_base=os.getenv("LLM_API_BASE") or overlay.llm.api_base or llm_payload.get("api_base"),
        api_key_env=str(os.getenv("LLM_API_KEY_ENV") or overlay.llm.api_key_env or llm_payload.get("api_key_env") or "OPENAI_API_KEY"),
    )

    return AppConfig(llm=llm, overlay=overlay)
