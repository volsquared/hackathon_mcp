# KYC Intelligence Agent Starter

This is the starter project for the final workshop exercise.

It is intentionally incomplete.

Read `PARTICIPANT_CHECKLIST.md` before you start coding. That file is
the step-by-step implementation guide, including the exact Java browser
URLs to inspect and the exact Python files you are expected to edit.

Important: this starter now uses explicit YAML configuration surfaces.
Participants are expected to author the tool-description and prompt-policy
text in YAML first, then wire and use those YAML files from the Python
reasoning layer.

What you get:

- a thin HTTP endpoint contract
- a Java API client for the KYC endpoints
- Pydantic schema definitions for the required output shape
- YAML config surfaces for tool descriptions, system prompt, and output rules
- tool wrapper functions
- an empty agent implementation skeleton

What you do **not** get:

- completed tool descriptions
- a completed system prompt
- completed prompt templates
- finished routing / reasoning logic

This starter is intended to be completed deterministically in Python.
Author the YAML files as reasoning contracts first, then implement the
same logic in `app/agent.py`. A live LLM call is optional and not
required for the harness.

The YAML config files you are expected to author are:

- `config/tool_descriptions.yaml`
- `config/system_prompt.yaml`
- `config/output_rules.yaml`

The main Python file you are expected to implement is:

- `app/agent.py`

You should also review:

- `app/tool_registry.py`

The intended division of work is:

- YAML files hold editable model-facing configuration
- Python files load those configs, fetch Java data, apply reasoning,
  and return the required schema

## Endpoint Contract

Start a local HTTP server that exposes:

- `POST /api/kyc-intelligence/analyze`

Request body:

```json
{
  "prompt": "CUS-KYC-02 wants to submit a product application - can we proceed?"
}
```

Response body:

```json
{
  "customer_id": "CUS-KYC-02",
  "overall_status": "BLOCKED",
  "can_proceed": false,
  "blocking_reason": "Source of funds declaration missing. Proof of address rejected.",
  "urgent_items": [],
  "upcoming_items": [],
  "pep_flag": false,
  "sanctions_flag": false,
  "enhanced_due_diligence": false,
  "next_review_due": null,
  "analyst_notes": "..."
}
```

## Notes

- The harness expects one schema-shaped result per request.
- For the cross-customer ranking prompt, return the schema for the customer
  you judge needs the most urgent attention. The spec expectation is
  `CUS-KYC-01`.
- `urgent_items` should hold blocking items and anything due within 30 days.
- `upcoming_items` should hold items due within 31-180 days.
- `analyst_notes` should explain the result, but must stay grounded in the API data.
- The Java API does not provide sanctions history.
- The Java API does not provide future compliance predictions.
- A false current sanctions flag is not evidence of a historically clean record.
- A VIP client is still blocked if blocking evidence exists.

## Run

Install Python dependencies from the repo-root `requirements.txt`.
This starter relies on the same `requests` and `pydantic` packages
already used by the main workshop project.

Example from the repo root:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

From this folder:

```powershell
cd starter_projects/kyc_intelligence_agent
py -3.11 run_server.py
```

The default server listens on `http://127.0.0.1:8011`.

Expected first-run behavior:

- the server starts
- the endpoint exists
- the analysis logic is still incomplete until you implement it
- the harness may return `501 not implemented` or failing cases at first

## Harness

From the repo root:

```powershell
.venv\Scripts\python.exe .\scripts\run_kyc_harness.py
```

Override the participant endpoint with:

```powershell
$env:KYC_AGENT_URL = "http://127.0.0.1:8011/api/kyc-intelligence/analyze"
.venv\Scripts\python.exe .\scripts\run_kyc_harness.py
```

Suggested working order:

1. inspect the Java KYC endpoints in the browser
2. fill in `config/tool_descriptions.yaml`
3. fill in `config/system_prompt.yaml`
4. review `config/output_rules.yaml`
5. review `app/tool_registry.py` and confirm it already loads your authored YAML descriptions
6. implement `app/agent.py`
7. run the harness
8. fix one failing case class at a time
