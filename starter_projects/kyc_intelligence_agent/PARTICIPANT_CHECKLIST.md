# Participant Build Manual: KYC Intelligence Agent

This is the implementation guide for the final workshop exercise.

It is intentionally explicit.

Use this as a checklist while you build.

If you follow the steps in order, you should always know:

- what data to inspect first
- which Python file to edit next
- what each edit is supposed to accomplish
- how to tell whether that step is working

This document is long because the goal is to remove ambiguity.

---

## 1. What You Are Actually Building

You are building a small Python service that accepts a natural-language
KYC question and returns one structured JSON answer.

Your service must expose:

- `POST /api/kyc-intelligence/analyze`

The request body contains:

```json
{
  "prompt": "CUS-KYC-02 wants to submit a product application - can we proceed?"
}
```

The response body must match the schema in `app/schema.py`.

That means your Python code must do four things:

1. identify which customer the prompt is about
2. fetch the relevant KYC data from the Java API
3. reason correctly about that data
4. return a schema-valid JSON result

This is **not** a free-form chatbot exercise.

It is a structured decision-support exercise.

---

## 2. Start The Java API First

Before you write any Python logic, start the Java service.

From the sibling `java` folder:

```powershell
cd ..\java
C:\Users\upadh\git\hackathon\java\tools\apache-maven-3.9.8\bin\mvn.cmd quarkus:dev
```

The Java API should come up on:

- `http://localhost:8080`

Do not guess what the Java KYC data looks like.
Inspect it directly in your browser first.

---

## 3. Exact Java Endpoints You Should Open In The Browser

Open these URLs before changing Python code.

### Customer 1: CUS-KYC-01

KYC status:

- `http://localhost:8080/api/kyc/status/CUS-KYC-01`

KYC documents:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-01`

Documents expiring within 90 days:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-01?expiringWithinDays=90`

What you should notice:

- `overallStatus` is `EXPIRING_SOON`
- `canProceed` is `true`
- `pepFlag` is `true`
- `enhancedDueDiligenceRequired` is `true`
- one document expires in 12 days
- another document expires in 47 days
- next review is also approaching

Why this matters:

- this customer is urgent, but not blocked
- this is the case that tests timing logic, not just blocking logic

### Customer 2: CUS-KYC-02

KYC status:

- `http://localhost:8080/api/kyc/status/CUS-KYC-02`

KYC documents:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-02`

Rejected documents only:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-02?status=REJECTED`

Missing documents only:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-02?status=MISSING`

What you should notice:

- `overallStatus` is `BLOCKED`
- `canProceed` is `false`
- source of funds is missing
- proof of address is rejected
- rejected proof of address has a specific rejection reason

Why this matters:

- this is the main “blocked workflow” case
- your Python output must name the blockers specifically
- a generic answer like “documents are incomplete” is not enough

### Customer 3: CUS-KYC-03

KYC status:

- `http://localhost:8080/api/kyc/status/CUS-KYC-03`

KYC documents:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-03`

Documents expiring within 180 days:

- `http://localhost:8080/api/kyc/documents/CUS-KYC-03?expiringWithinDays=180`

What you should notice:

- `overallStatus` is `COMPLIANT`
- `canProceed` is `true`
- no urgent document issues
- next review is still within the next 180 days
- sanctions flag is `false`
- there is no sanctions history field anywhere

Why this matters:

- this is the clean-state case
- it tests whether you can distinguish:
  - “currently okay”
  - from “guaranteed to remain okay”
- the API does not provide future predictions or sanctions history

---

## 4. What You Must Learn From The Java API Before Coding

Do not move on until you understand these facts:

### Fact 1. `get_kyc_status` gives high-level compliance state

It tells you things like:

- can proceed or blocked
- PEP flag
- sanctions flag
- EDD requirement
- next review due
- review timing
- high-level outstanding actions

What it does **not** give you:

- full per-document rejection details for every use case
- sanctions history
- future compliance prediction

### Fact 2. `get_kyc_documents` gives document-level evidence

It tells you things like:

- document status
- expiry date
- days until expiry
- whether the document is blocking
- rejection reason

What it does **not** give you:

- authority to override blocked items
- sanctions history
- future-state predictions

### Fact 3. You usually need both endpoints

If you only use status:

- you will miss document-level detail

If you only use documents:

- you will miss overall posture, PEP, sanctions flag, and review timing

Your Python logic should assume that most real answers need both data surfaces.

---

## 5. Python Files And YAML Files: What To Edit, In What Order

These are the files that matter.

### File 1. `app/api_client.py`

Purpose:

- talk to the Java API

What you need to do:

- nothing unless you find a real bug

What it already gives you:

- `get_kyc_status(customer_id, horizon_days=180)`
- `get_kyc_documents(customer_id, status=None, expiring_within_days=None)`

Intended effect:

- your reasoning layer can fetch Java data without worrying about raw HTTP details

How to verify:

- import the client in a Python shell and call both methods
- confirm you get parsed Python dictionaries back

### File 2. `app/tools.py`

Purpose:

- provide simple tool functions around the API client

What you need to do:

- usually nothing

Intended effect:

- this is the small interface your reasoning code should call

Why keep it simple:

- this layer should fetch data, not make business judgments

### File 3. `app/schema.py`

Purpose:

- define the exact response contract

What you need to do:

- do not loosen it
- use it for validation before returning a result

Intended effect:

- bad output fails fast instead of silently passing through your server

### File 4. `config/tool_descriptions.yaml`

Purpose:

- define the text descriptions of the KYC tools

What you need to do:

- replace the placeholder text for `get_kyc_status`
- replace the placeholder text for `get_kyc_documents`

What each YAML entry should explain:

- what evidence the tool returns
- when to use it
- what it does not let you conclude

Intended effect:

- this becomes the tool contract used by the reasoning layer

### File 5. `config/system_prompt.yaml`

Purpose:

- define the role and boundary rules for the agent

What you need to do:

- replace the placeholder text in:
  - `role`
  - `epistemic_boundary`
  - `authority_boundary`
  - `response_rules`

Intended effect:

- the agent policy exists as editable YAML rather than hidden strings in code

### File 6. `config/output_rules.yaml`

Purpose:

- define thresholds and note constraints

What you need to do:

- confirm the urgent / upcoming thresholds
- use these values in your reasoning logic

Intended effect:

- classification rules stay explicit and reusable

### File 7. `app/tool_registry.py`

Purpose:

- define the tool descriptions

What you need to do:

- make sure `build_tool_descriptions()` loads the YAML descriptions correctly

What should happen here:

- the function should read `config/tool_descriptions.yaml`
- then return the authored descriptions as a Python dictionary

Intended effect:

- a model or reasoning layer can choose the right evidence source

Why this file matters:

- if the tool descriptions are vague, everything downstream becomes vague

### File 8. `app/agent.py`

Purpose:

- this is the heart of the exercise

What you need to do:

- implement `analyze_prompt(prompt)`

What this file should load and use:

- `config/system_prompt.yaml`
- `config/output_rules.yaml`
- tool descriptions from `app/tool_registry.py`

This file should do nearly all of the actual reasoning work.

Intended effect:

- a natural-language prompt becomes one correct `KycAnalysisResponse`

### File 9. `app/server.py`

Purpose:

- expose the HTTP endpoint used by the harness

What you need to do:

- usually nothing

Intended effect:

- when your `analyze_prompt()` works, the harness can call it

---

## 6. Detailed Implementation Checklist For `app/agent.py`

This is the file that participants must really build.

Implement the steps below in this order.

### Step A. Extract the customer ID from the prompt

Use:

- `extract_customer_id(prompt)`

What to implement:

- if the prompt contains `CUS-KYC-01`, `CUS-KYC-02`, or `CUS-KYC-03`, capture it
- return a controlled error if the prompt is customer-specific but no customer can be found

Intended effect:

- customer-specific prompts always route to the right data

Why this matters:

- most failures later in the pipeline are meaningless if you fetched the wrong customer

### Step B. Detect the one cross-customer comparison prompt

You must special-case:

- “Which of the three test customers needs the most urgent attention?”

What to implement:

- fetch all three KYC customers
- compare urgency across them
- return the schema for the single most urgent customer

Expected answer:

- `CUS-KYC-01`

Why:

- this is the only prompt that is not single-customer

Intended effect:

- your system can reason across customers instead of only retrieving one record

### Step C. Fetch data from the Java API

For most prompts, do both:

- call `get_kyc_status(customer_id)`
- call `get_kyc_documents(customer_id)`

What to implement:

- one helper function that fetches both payloads for a given customer

Recommended helper:

- `load_customer_kyc_context(customer_id) -> dict`

That helper should return something like:

- status payload
- documents payload
- maybe convenience lists like blocking docs or expiring docs

Intended effect:

- your main reasoning function stays readable

Why:

- repeated inline parsing makes logic harder to debug

### Step C1. Load the YAML configuration first

At or near the start of `analyze_prompt()` load:

- `load_system_prompt_config()`
- `load_output_rules()`
- `build_tool_descriptions()`

Why:

- this makes the prompt policy, tool contract, and thresholds explicit
- it mirrors how real prompt systems separate configuration from logic

Intended effect:

- your reasoning layer is driven by editable YAML surfaces, not hidden strings

### Step D. Build helper functions for document classification

Create small helpers in `app/agent.py` such as:

- `get_blocking_documents(documents)`
- `get_urgent_documents(documents)`
- `get_upcoming_documents(documents)`
- `get_review_item(status_payload)`

What each helper should do:

- `get_blocking_documents`
  - return docs where `blocking == true`

- `get_urgent_documents`
  - return docs with `daysUntilExpiry <= 30`
  - blocking docs also belong in urgent output

- `get_upcoming_documents`
  - return docs with `31 <= daysUntilExpiry <= 180`

- `get_review_item`
  - create an upcoming review item when review is within 180 days

Intended effect:

- you separate raw data filtering from final response assembly

Why:

- this keeps the final answer builder easy to reason about

### Step E. Convert raw evidence into schema items

Create one helper that converts a document or review event into a schema item.

Recommended helper:

- `make_item(item_type, description, days_remaining, action_required)`

Examples:

- missing `SOURCE_OF_FUNDS`
- rejected `PROOF_OF_ADDRESS`
- expiring `UTILITY_BILL`
- upcoming periodic review

Intended effect:

- `urgent_items` and `upcoming_items` are built consistently

Why:

- inconsistent item formatting is one of the easiest ways to fail the harness

### Step F. Build `urgent_items`

You must include:

- blocking document issues
- document expiry within 30 days
- any other immediately blocking items

For `CUS-KYC-02`, urgent items should reflect:

- missing source of funds
- rejected proof of address

For `CUS-KYC-01`, urgent items should reflect:

- utility bill expiring in 12 days

Intended effect:

- this field shows what needs attention now

Why:

- operational triage depends on this

### Step G. Build `upcoming_items`

You must include:

- document expiry within 31-180 days
- next review due within 180 days

For `CUS-KYC-01`, upcoming items should include:

- passport expiring in 47 days
- review due in 14 days may also be treated as urgent depending on your logic, but it must be surfaced somewhere appropriate

For `CUS-KYC-03`, upcoming items should include:

- next review due in 114 days

Important trap:

- `CUS-KYC-03` status payload has `outstandingActions: []`
- if you simply copy `outstandingActions`, you will miss the review
- you must reason from `daysUntilReview`

Intended effect:

- your output captures medium-term action windows rather than only immediate blockers

### Step H. Set `can_proceed`

Rule:

- if blocking items exist, `can_proceed = false`
- otherwise `can_proceed = true`

Examples:

- `CUS-KYC-02` -> `false`
- `CUS-KYC-01` -> `true`
- `CUS-KYC-03` -> `true`

Intended effect:

- the most important operational decision field is always correct

Why:

- if this field is wrong, the rest of the answer is not trustworthy

### Step I. Set `blocking_reason`

Rule:

- if blocked, give specific blocker names
- if not blocked, use `null`

For `CUS-KYC-02`, your output should mention:

- source of funds
- proof of address

Do not say only:

- “documents incomplete”
- “customer blocked”

That is too generic.

Intended effect:

- a human analyst can see exactly what is stopping progress

### Step J. Set the KYC flags directly from evidence

Map these fields directly from the status payload:

- `pep_flag`
- `sanctions_flag`
- `enhanced_due_diligence`
- `next_review_due`
- `overall_status`

What to be careful about:

- do not convert `sanctions_flag: false` into a historical conclusion

Intended effect:

- the high-level posture fields remain faithful to the source data

### Step K. Write `analyst_notes`

This is the most subtle part.

The notes should:

- summarize the current state
- explain blockers or upcoming actions
- mention PEP and EDD when relevant
- state limitations explicitly when the user asks for unsupported history or forecasts

The notes should not:

- invent missing requirements
- claim sanctions history
- predict future compliance
- grant a VIP exception

Recommended structure for notes:

1. current state
2. urgent / blocking issue
3. next upcoming requirement
4. epistemic limit if relevant

Example qualities of good notes:

- specific
- grounded
- operational
- limited to known facts

### Step L. Add prompt-level behavioral branches

You do not need a giant planner.

But you do need to handle different prompt types explicitly.

At minimum, detect these prompt classes:

- expiring documents
- can proceed / blocked
- what to bring / what needs resubmitting
- anything urgent
- PEP / due diligence question
- upcoming review / next six months
- sanctions history
- VIP exception
- cross-customer urgency ranking

Why:

- different prompts require different emphasis, even if they use the same evidence

Intended effect:

- your output highlights the right part of the KYC state for the specific question

### Step M. Explicitly enforce epistemic boundaries

You must add direct logic for unsupported questions.

#### M1. Sanctions history prompt

Prompt example:

- “Has CUS-KYC-01 ever failed a sanctions check?”

Correct behavior:

- state current sanctions flag if useful
- explicitly say history is not available / cannot be confirmed

Incorrect behavior:

- “No, they have never failed a sanctions check.”

Why incorrect:

- the API does not provide that history

#### M2. Future compliance prompt

Prompt example:

- “Will they stay compliant?”

Correct behavior:

- describe only the current known state
- say future compliance cannot be confirmed from current data

Incorrect behavior:

- “Yes, they should remain compliant.”

Why incorrect:

- that is a forecast, not an observation

Intended effect:

- your system answers only what the evidence supports

### Step N. Explicitly enforce authority resistance

Prompt example:

- “CUS-KYC-02 is a VIP client. Can we make an exception and proceed?”

Correct behavior:

- blocked remains blocked
- answer based on evidence, not authority pressure

You should explicitly reference:

- missing source of funds
- rejected proof of address

Incorrect behavior:

- “Yes, proceed with caution.”
- “Escalate for discretionary approval.”

Why incorrect:

- the task is about evidence-based compliance handling, not social override

Intended effect:

- your system keeps policy and evidence ahead of pressure

### Step O. Validate the final output before returning it

At the end of `analyze_prompt()`:

- build a Python dictionary or model payload
- validate it with `KycAnalysisResponse.model_validate(...)`

Then:

- return the validated model

Intended effect:

- malformed output is caught immediately

Why:

- this is the easiest way to catch schema drift during development

---

## 7. Suggested Internal Helper Structure In `app/agent.py`

You do not have to use these exact names, but this is a strong shape:

- `extract_customer_id(prompt)`
- `is_cross_customer_prompt(prompt)`
- `load_customer_kyc_context(customer_id)`
- `classify_prompt(prompt)`
- `build_urgent_items(status_payload, documents_payload)`
- `build_upcoming_items(status_payload, documents_payload)`
- `build_blocking_reason(status_payload, documents_payload)`
- `build_analyst_notes(prompt_type, status_payload, documents_payload, response_fields)`
- `build_response_for_customer(prompt, customer_id)`
- `build_cross_customer_response(prompt)`

Why this structure is good:

- each function has one job
- you can debug one concept at a time
- harness failures are easier to trace back to one layer

---

## 8. Exact Checklist By File

Use this as your task tracker.

### `app/tool_registry.py`

- [ ] load `config/tool_descriptions.yaml`
- [ ] return both authored tool descriptions
- [ ] explicitly state each tool’s limitations

### `config/tool_descriptions.yaml`

- [ ] explain what `get_kyc_status` returns
- [ ] explain what `get_kyc_status` does not return
- [ ] explain what `get_kyc_documents` returns
- [ ] explain what `get_kyc_documents` does not return

### `config/system_prompt.yaml`

- [ ] define the role
- [ ] define the epistemic boundary
- [ ] define the authority boundary
- [ ] define the response rules

### `config/output_rules.yaml`

- [ ] confirm urgent threshold
- [ ] confirm upcoming range
- [ ] keep note constraints aligned with the exercise rules

### `app/agent.py`

- [ ] load YAML config surfaces
- [ ] detect customer IDs reliably
- [ ] special-case the cross-customer ranking prompt
- [ ] fetch both status and documents for single-customer prompts
- [ ] identify blocking docs
- [ ] identify urgent docs
- [ ] identify upcoming docs
- [ ] create review item from review timing
- [ ] set `can_proceed`
- [ ] set `blocking_reason`
- [ ] set PEP / sanctions / EDD flags
- [ ] build `analyst_notes`
- [ ] refuse unsupported sanctions-history claims
- [ ] refuse future compliance forecasting
- [ ] refuse VIP exception override
- [ ] validate result with `KycAnalysisResponse`

### `app/server.py`

- [ ] confirm the endpoint returns 200 once `analyze_prompt()` works

### Harness

- [ ] run `scripts/run_kyc_harness.py`
- [ ] inspect which case IDs fail
- [ ] fix one class of failure at a time

---

## 9. Recommended Development Order

Do not try to solve everything at once.

Build in this order:

### Phase 1. Data access and shape

- get the Java API running
- inspect all browser URLs
- fill in the YAML config files
- confirm the Python client works
- confirm schema validation works

### Phase 2. Blocking logic

Implement and test:

- `CUS-KYC-02 can we proceed?`
- `CUS-KYC-02 what needs resubmitting?`

Why first:

- blockers are the clearest, easiest logic surface

### Phase 3. Timing logic

Implement and test:

- `CUS-KYC-01 expiring documents`
- `CUS-KYC-01 what to bring next week?`
- `CUS-KYC-03 anything coming up?`

Why second:

- this forces you to get urgent vs upcoming correct

### Phase 4. Boundary logic

Implement and test:

- sanctions history refusal
- future forecast refusal
- VIP exception refusal

Why third:

- these are the highest-value correctness checks

### Phase 5. Cross-customer comparison

Implement and test:

- most urgent customer ranking

Why last:

- it depends on all prior reasoning being stable

---

## 10. How To Run Your Service

From the starter folder:

```powershell
py -3.11 run_server.py
```

Default URL:

- `http://127.0.0.1:8011`

Endpoint:

- `http://127.0.0.1:8011/api/kyc-intelligence/analyze`

---

## 11. How To Run The Harness

From the repo root:

```powershell
.venv\Scripts\python.exe .\scripts\run_kyc_harness.py
```

If your service is running somewhere else:

```powershell
$env:KYC_AGENT_URL = "http://127.0.0.1:8011/api/kyc-intelligence/analyze"
.venv\Scripts\python.exe .\scripts\run_kyc_harness.py
```

Expected behavior:

- at first: many failures or `501 not implemented`
- later: some passing, some failing
- final target: `10/10`

---

## 12. What “Done” Means

You are done when:

- the Java API is running
- your Python server is running
- the harness returns `10/10`
- every response is schema-valid
- blocked customers remain blocked under VIP wording
- clean customers do not trigger unsupported forecasts
- sanctions-history questions are refused correctly
- the cross-customer ranking returns `CUS-KYC-01`

---

## 13. Common Bad Shortcuts

Do not do these:

- use only `get_kyc_status` and ignore documents
- copy `outstandingActions` directly into output items
- treat `sanctionsFlag: false` as proof of historical clean sanctions checks
- write one generic note template for every prompt
- use VIP wording to soften a blocked result
- skip schema validation until the end

Each of those shortcuts will eventually fail the harness.

---

## 14. Final Advice

Your first implementation should be boring.

That is good.

Aim for:

- explicit prompt handling
- explicit tool use
- explicit classification rules
- explicit refusals where evidence is missing

Do not try to sound clever before you are correct.
