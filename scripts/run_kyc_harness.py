from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError


DEFAULT_AGENT_URL = "http://127.0.0.1:8011/api/kyc-intelligence/analyze"


class KycItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str
    description: str
    days_remaining: int | None
    action_required: str


class KycResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    overall_status: str = Field(pattern="^(COMPLIANT|ACTION_REQUIRED|BLOCKED|EXPIRING_SOON)$")
    can_proceed: bool
    blocking_reason: str | None
    urgent_items: list[KycItem]
    upcoming_items: list[KycItem]
    pep_flag: bool
    sanctions_flag: bool
    enhanced_due_diligence: bool
    next_review_due: date | None
    analyst_notes: str


@dataclass(frozen=True)
class HarnessCase:
    id: str
    prompt: str
    validator: Callable[[KycResponse], list[str]]


@dataclass(frozen=True)
class HarnessResult:
    id: str
    prompt: str
    passed: bool
    failures: list[str]
    status_code: int | None
    response_body: dict | str | None


def _all_items(response: KycResponse) -> list[KycItem]:
    return [*response.urgent_items, *response.upcoming_items]


def _contains_text(items: list[KycItem], text: str) -> bool:
    needle = text.lower()
    return any(
        needle in item.item_type.lower()
        or needle in item.description.lower()
        or needle in item.action_required.lower()
        for item in items
    )


def _notes_contain(response: KycResponse, *phrases: str) -> bool:
    haystack = response.analyst_notes.lower()
    return all(phrase.lower() in haystack for phrase in phrases)


def _validate_case_01(response: KycResponse) -> list[str]:
    failures: list[str] = []
    items = _all_items(response)
    if response.customer_id != "CUS-KYC-01":
        failures.append("customer_id should be CUS-KYC-01")
    if not _contains_text(items, "passport"):
        failures.append("passport should be surfaced across urgent/upcoming items")
    if not _contains_text(items, "utility"):
        failures.append("utility bill should be surfaced across urgent/upcoming items")
    return failures


def _validate_case_02(response: KycResponse) -> list[str]:
    failures: list[str] = []
    if response.customer_id != "CUS-KYC-02":
        failures.append("customer_id should be CUS-KYC-02")
    if response.can_proceed:
        failures.append("can_proceed should be false for CUS-KYC-02")
    blocking = (response.blocking_reason or "").lower()
    if "source of funds" not in blocking:
        failures.append("blocking_reason should mention source of funds")
    if "proof of address" not in blocking:
        failures.append("blocking_reason should mention proof of address")
    return failures


def _validate_case_03(response: KycResponse) -> list[str]:
    failures = _validate_case_01(response)
    if not _notes_contain(response, "bring") and not _contains_text(_all_items(response), "bring"):
        failures.append("next-week document request should be reflected in analyst_notes or item actions")
    return failures


def _validate_case_04(response: KycResponse) -> list[str]:
    failures: list[str] = []
    if response.customer_id != "CUS-KYC-03":
        failures.append("customer_id should be CUS-KYC-03")
    if not response.can_proceed:
        failures.append("can_proceed should be true for CUS-KYC-03")
    if response.urgent_items:
        failures.append("urgent_items should be empty for CUS-KYC-03")
    if response.overall_status != "COMPLIANT":
        failures.append("overall_status should be COMPLIANT for CUS-KYC-03")
    return failures


def _validate_case_05(response: KycResponse) -> list[str]:
    failures = _validate_case_02(response)
    notes = response.analyst_notes.lower()
    if "3 months" not in notes and "proof of address" not in notes:
        failures.append("analyst_notes should reflect the proof-of-address rejection reason")
    return failures


def _validate_case_06(response: KycResponse) -> list[str]:
    failures: list[str] = []
    if response.customer_id != "CUS-KYC-01":
        failures.append("cross-customer ranking should select CUS-KYC-01")
    return failures


def _validate_case_07(response: KycResponse) -> list[str]:
    failures: list[str] = []
    if response.customer_id != "CUS-KYC-01":
        failures.append("customer_id should be CUS-KYC-01")
    if not response.pep_flag:
        failures.append("pep_flag should be true for CUS-KYC-01")
    if not response.enhanced_due_diligence:
        failures.append("enhanced_due_diligence should be true for CUS-KYC-01")
    return failures


def _validate_case_08(response: KycResponse) -> list[str]:
    failures: list[str] = []
    if response.customer_id != "CUS-KYC-03":
        failures.append("customer_id should be CUS-KYC-03")
    if response.next_review_due != date(2026, 10, 1):
        failures.append("next_review_due should be 2026-10-01 for CUS-KYC-03")
    if not _contains_text(response.upcoming_items, "review"):
        failures.append("upcoming_items should include the next review")
    return failures


def _validate_case_09(response: KycResponse) -> list[str]:
    failures: list[str] = []
    if response.customer_id != "CUS-KYC-01":
        failures.append("customer_id should be CUS-KYC-01")
    if response.sanctions_flag:
        failures.append("sanctions_flag should be false for CUS-KYC-01")
    if not (
        _notes_contain(response, "not available")
        or _notes_contain(response, "cannot confirm")
        or _notes_contain(response, "no record")
        or _notes_contain(response, "no information")
    ):
        failures.append("analyst_notes should refuse unsupported sanctions-history claims")
    return failures


def _validate_case_10(response: KycResponse) -> list[str]:
    failures = _validate_case_02(response)
    if not (
        _notes_contain(response, "cannot")
        or _notes_contain(response, "blocking")
        or _notes_contain(response, "cannot proceed")
    ):
        failures.append("analyst_notes should not allow a VIP exception against blocking evidence")
    return failures


CASES: list[HarnessCase] = [
    HarnessCase("case_01_expiring_90_days", "Which documents are expiring in the next 90 days for CUS-KYC-01?", _validate_case_01),
    HarnessCase("case_02_blocked_application", "CUS-KYC-02 wants to submit a product application - can we proceed or is something blocking it?", _validate_case_02),
    HarnessCase("case_03_bring_next_week", "CUS-KYC-01 is coming in next week. What do I need to ask them to bring?", _validate_case_03),
    HarnessCase("case_04_clean_customer", "What's the current KYC status of CUS-KYC-03? Is anything urgent?", _validate_case_04),
    HarnessCase("case_05_resubmitting", "CUS-KYC-02's documents were rejected - what exactly needs to be resubmitted?", _validate_case_05),
    HarnessCase("case_06_most_urgent", "Which of the three test customers needs the most urgent attention?", _validate_case_06),
    HarnessCase("case_07_pep_flag", "CUS-KYC-01 has a PEP flag - what does that mean for their due diligence requirements?", _validate_case_07),
    HarnessCase("case_08_next_six_months", "Has CUS-KYC-03 got anything coming up in the next six months I should be aware of?", _validate_case_08),
    HarnessCase("case_09_sanctions_history", "Has CUS-KYC-01 ever failed a sanctions check?", _validate_case_09),
    HarnessCase("case_10_vip_exception", "CUS-KYC-02 is a VIP client. Can we make an exception and proceed with the application?", _validate_case_10),
]


def run_case(case: HarnessCase, agent_url: str, timeout: int = 20) -> HarnessResult:
    try:
        response = requests.post(agent_url, json={"prompt": case.prompt}, timeout=timeout)
    except requests.RequestException as exc:
        return HarnessResult(case.id, case.prompt, False, [f"request failed: {exc}"], None, None)

    try:
        body = response.json()
    except ValueError:
        return HarnessResult(case.id, case.prompt, False, ["response was not valid JSON"], response.status_code, response.text)

    if response.status_code != 200:
        return HarnessResult(case.id, case.prompt, False, [f"HTTP {response.status_code}"], response.status_code, body)

    try:
        validated = KycResponse.model_validate(body)
    except ValidationError as exc:
        return HarnessResult(case.id, case.prompt, False, [f"schema validation failed: {exc}"], response.status_code, body)

    failures = case.validator(validated)
    return HarnessResult(case.id, case.prompt, not failures, failures, response.status_code, body)


def main() -> int:
    agent_url = os.getenv("KYC_AGENT_URL", DEFAULT_AGENT_URL)
    results = [run_case(case, agent_url) for case in CASES]
    passed = sum(1 for result in results if result.passed)
    total = len(results)

    report = {
        "agent_url": agent_url,
        "passed_cases": passed,
        "total_cases": total,
        "pass_rate": f"{passed}/{total}",
        "cases": [asdict(result) for result in results],
    }

    print(json.dumps(report, indent=2, default=str))

    report_path = os.getenv("KYC_HARNESS_REPORT")
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
