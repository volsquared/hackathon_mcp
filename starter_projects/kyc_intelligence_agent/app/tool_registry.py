from __future__ import annotations

from typing import Callable

from app.config_loader import load_yaml_config
from app.tools import get_kyc_documents, get_kyc_status


ToolFunction = Callable[..., dict]


TOOLS: dict[str, ToolFunction] = {
    "get_kyc_status": get_kyc_status,
    "get_kyc_documents": get_kyc_documents,
}


def build_tool_descriptions() -> dict[str, str]:
    payload = load_yaml_config("tool_descriptions.yaml")
    status_description = str(payload.get("get_kyc_status") or "").strip()
    documents_description = str(payload.get("get_kyc_documents") or "").strip()
    if not status_description or not documents_description:
        raise ValueError("tool_descriptions.yaml must define both get_kyc_status and get_kyc_documents.")
    return {
        "get_kyc_status": status_description,
        "get_kyc_documents": documents_description,
    }
