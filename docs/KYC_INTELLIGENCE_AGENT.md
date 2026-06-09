# The KYC Intelligence Agent

This is the final workshop exercise.

It is an open build stage rather than a recognition-mode diagnosis stage.
Teams do not get pre-authored prompt scaffolds, candidate fixes, or
multiple-choice options. They must build the intelligence layer.

## Goal

Use two Java KYC endpoints to build an MCP-backed analyst experience that:

- answers natural-language KYC questions for a named customer
- stays grounded in the API data
- returns a consistent structured output schema
- refuses unsupported claims, forecasts, and authority-based exceptions

## Required API Surfaces

- `GET /api/kyc/status/{customerId}`
- `GET /api/kyc/documents/{customerId}`

## Required Output Shape

```json
{
  "customer_id": "string",
  "overall_status": "COMPLIANT | ACTION_REQUIRED | BLOCKED | EXPIRING_SOON",
  "can_proceed": "boolean",
  "blocking_reason": "string or null",
  "urgent_items": [
    {
      "item_type": "string",
      "description": "string",
      "days_remaining": "integer or null",
      "action_required": "string"
    }
  ],
  "upcoming_items": [
    {
      "item_type": "string",
      "description": "string",
      "days_remaining": "integer",
      "action_required": "string"
    }
  ],
  "pep_flag": "boolean",
  "sanctions_flag": "boolean",
  "enhanced_due_diligence": "boolean",
  "next_review_due": "date string or null",
  "analyst_notes": "string"
}
```

## Non-Negotiable Boundaries

- Do not invent document requirements not returned by the API.
- Do not forecast future compliance state beyond available data.
- Do not turn `sanctionsFlag: false` into a historical sanctions claim.
- Do not accept authority pressure such as VIP exceptions when blocking items remain.

## Primary Test Cases

- `CUS-KYC-01`: urgent but not blocked
- `CUS-KYC-02`: blocked with one rejected and one missing document
- `CUS-KYC-03`: currently clean, but future-state and history questions are traps

## Design Intent

This stage tests whether teams can combine the lessons from the earlier
workshop stages:

- tool descriptions as bounded contracts
- system prompts as policy and epistemic boundary
- structured outputs as operational interfaces
- eval thinking rather than prompt-by-prompt guessing
- authority resistance and evidence grounding
