from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import yaml

from app.config import AppConfig, load_app_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ASSETS_DIR = PROJECT_ROOT / "runtime_assets"
logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _load_registry_dir(relative_dir: str) -> dict[str, dict[str, Any] | None]:
    base_dir = RUNTIME_ASSETS_DIR / relative_dir
    registry: dict[str, dict[str, Any] | None] = {}
    if not base_dir.exists():
        return registry
    for path in sorted(base_dir.glob("*.yaml")):
        if path.stem == "none":
            registry[path.stem] = None
        else:
            registry[path.stem] = _load_yaml(path)
    return registry


TOOL_DESCRIPTION_REGISTRY = _load_registry_dir("tool_descriptions")
SYSTEM_PROMPT_REGISTRY = _load_registry_dir("system_prompts")
FORMAT_CONFIG_REGISTRY = _load_registry_dir("format_configs")
ONTOLOGY_REGISTRY = _load_registry_dir("ontologies")


def load_active_config() -> AppConfig:
    return load_app_config()


def _resolve_registry_payload(
    *,
    registry_name: str,
    registry: dict[str, dict[str, Any] | None],
    active_key: str,
    default_key: str,
) -> dict[str, Any] | None:
    if active_key in registry:
        return registry[active_key]
    if active_key == default_key:
        return registry.get(default_key)
    available = ", ".join(sorted(registry.keys())) or "(empty)"
    message = f"Unknown {registry_name} overlay '{active_key}'. Available: {available}."
    logger.error(message)
    raise KeyError(message)


def get_tool_description_payload(config: AppConfig | None = None) -> dict[str, Any]:
    active = (config or load_active_config()).overlay.tool_descriptions
    payload = _resolve_registry_payload(
        registry_name="tool_descriptions",
        registry=TOOL_DESCRIPTION_REGISTRY,
        active_key=active,
        default_key="default",
    )
    return payload or {}


def get_system_prompt_payload(config: AppConfig | None = None) -> dict[str, Any]:
    active = (config or load_active_config()).overlay.system_prompt
    payload = _resolve_registry_payload(
        registry_name="system_prompt",
        registry=SYSTEM_PROMPT_REGISTRY,
        active_key=active,
        default_key="default",
    )
    return payload or {}


def get_format_payload(config: AppConfig | None = None) -> dict[str, Any]:
    active = (config or load_active_config()).overlay.format
    payload = _resolve_registry_payload(
        registry_name="format",
        registry=FORMAT_CONFIG_REGISTRY,
        active_key=active,
        default_key="default",
    )
    return payload or {}


def get_ontology_payload(config: AppConfig | None = None) -> dict[str, Any] | None:
    active = (config or load_active_config()).overlay.ontology
    return _resolve_registry_payload(
        registry_name="ontology",
        registry=ONTOLOGY_REGISTRY,
        active_key=active,
        default_key="none",
    )
