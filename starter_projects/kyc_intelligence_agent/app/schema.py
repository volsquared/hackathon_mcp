from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class KycItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: str
    description: str
    days_remaining: int | None
    action_required: str


class KycAnalysisResponse(BaseModel):
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
