from __future__ import annotations

import re

from app.config_loader import load_yaml_config
from app.schema import KycAnalysisResponse


CUSTOMER_ID_PATTERN = re.compile(r"CUS-KYC-\d{2}", re.IGNORECASE)


def extract_customer_id(prompt: str) -> str | None:
    match = CUSTOMER_ID_PATTERN.search(prompt or "")
    return match.group(0).upper() if match else None


def load_system_prompt_config() -> dict:
    return load_yaml_config("system_prompt.yaml")


def load_output_rules() -> dict:
    return load_yaml_config("output_rules.yaml")


def analyze_prompt(prompt: str) -> KycAnalysisResponse:
    raise NotImplementedError(
        "Implement the KYC intelligence layer: load the YAML prompt/config surfaces, choose tools, enforce epistemic boundaries, and return the required schema."
    )
