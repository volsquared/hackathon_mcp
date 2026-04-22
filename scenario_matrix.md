# Scenario Matrix

This file defines the scenario design for the workshop dataset and prompt/eval coverage.

The goal is not just "more customers." The goal is a test bed with:

- clear happy paths
- deliberate ambiguity
- competing signals
- boundary cases
- prompts that should fail cleanly

These scenarios should drive:

- Java seed data design
- prebuilt chain design
- prompt examples and anti-examples
- ontology terms
- eval cases


## Suggested Data Shape

Keep the structured fields simple. Add a small amount of verbose free text so prompt behavior can become more interesting without turning the schema into a full enterprise model.

### Core structured fields

- `customer_id`
- `full_name`
- `segment`
- `status`
- `risk_rating`
- `total_spend`
- `fraud_flag_count`
- `alert_count`
- `primary_pattern`

### Useful verbose fields

- `analyst_note`
  Short human summary of why this customer matters.
- `case_context`
  Free text describing the situation or recent activity.
- `service_summary`
  Customer-service style explanation of what is going on.
- `risk_commentary`
  Risk-team style interpretation of the same signals.

Status: facilitator and data-design artifacts only. Not returned by the Java API.
Not present in raw_result. Not referenceable in prompts.

Reason: if these fields are API-returned, the model will paraphrase the commentary
instead of reasoning over structured signals. That shortcuts the prompt engineering
exercise and makes ontology and format work look more powerful than it really is.

If a future workshop wants a deliberate "case notes" exercise, add it intentionally
as a separate design choice, not by default.


## Scenario Table

| Scenario ID | Scenario Name | Core Pattern | Why It Exists | Good Prompt Types | Bad / Boundary Prompt Types | Suggested Free Text Angle |
|---|---|---|---|---|---|---|
| S01 | Clean Fraud Happy Path | High risk, confirmed fraud, matching alert | Baseline single-tool and answer-generation success case | `Show fraud for CUS007`, `Summarize the fraud risk for CUS007` | Should not require comparison or multi-step reasoning | Strong risk-team note with clear escalation language |
| S02 | Suspicious But Benign | High spend, no fraud, no alerts, low risk | Prevent over-triggering on "looks suspicious" behavior | `Show spending for CUS010`, `Is CUS010 risky?` | Should not trigger fraud workflow just because spend is high | Analyst note says unusual spend is seasonal and expected |
| S03 | Mixed Signal Low Risk | One fraud flag, low risk rating, no severe alert | Test whether prompts overstate risk | `Show flagged transactions for CUS011`, `Summarize the account for CUS011` | Should not automatically call customer high risk | Commentary explains why the case is still monitored but not escalated |
| S04 | Alert Without Fraud Confirmation | Active alert, no confirmed fraud, medium risk | Distinguish suspicious activity from confirmed fraud | `Show alerts for CUS012`, `Review the profile and alerts for CUS012` | Should not answer as if fraud is confirmed | Service summary explains the alert in plain language |
| S05 | High Risk No Current Alerts | High risk profile, no active alerts | Ensure profile and alerts are not treated as interchangeable | `What is the risk rating for CUS013?`, `Does CUS013 have active alerts?` | Should not invent alerts because risk is high | Risk commentary explains historical reasons for high risk |
| S06 | Similar Alerts Different Outcomes A | Alert pattern shared with another customer, but low business impact | Useful for compare scenarios | `Compare alerts for CUS014 and CUS015` | Should not collapse both customers into one narrative | Analyst note highlights low-severity operational impact |
| S07 | Similar Alerts Different Outcomes B | Similar alert pattern, but high business impact and escalation | Useful for compare scenarios | `Compare alerts for CUS014 and CUS015`, `Who needs review first?` | Should not treat similar alerts as identical outcomes | Risk note recommends human review |
| S08 | Spending Heavy, Stable Customer | Very high spend, stable pattern, no alerts | Good for "behaviour" ontology without fraud | `Describe spending behaviour for CUS016` | Should not trigger fraud or alert chain | Case context explains normal business-related spending rhythm |
| S09 | Low Spend, High Risk Customer | Low spend, high risk, one severe alert | Forces participants to avoid equating spend with risk | `Summarize risk and alerts for CUS017` | Should not describe behavior as safe just because spend is low | Commentary contrasts low volume with high signal severity |
| S10 | Full Picture One Customer | Profile + alerts + spending all relevant | Main scenario for `get_full_picture` | `Give me the full picture for CUS018`, `Summarize risk, alerts, and spend for CUS018` | Should not route to a single-tool path | Analyst note provides compact cross-signal summary |
| S11 | Compare Customers Happy Path | Two customers with intentionally contrastive signals | Main scenario for `compare_customers` | `Compare the spending and alerts for CUS019 and CUS020` | Should not route to a single-customer chain | Free text highlights key contrast in one sentence each |
| S12 | Comparison Out Of Scope | Query asks for unsupported comparison dimension | Force clean refusal or fallback | `Compare customer behaviour for CUS019 and CUS020 over the last quarter` | Should fail cleanly if time-window support does not exist | Context note mentions missing time-sliced support |
| S13 | Out-of-domain Refusal | Prompt is entirely off-topic for the banking assistant | Test clean refusal for non-banking queries | `What is the interest rate on savings accounts?`, `When does the branch open?` | Must return no tool and refuse cleanly, not guess | None — no customer context exists |
| S14 | Missing Customer ID | In-domain prompt but no valid CUS### identifier | Test behavior when the scaffold cannot extract a customer | `Show me fraud for John`, `Is this customer high risk?` | Must ask for clarification or fail cleanly, never guess a customer mapping | None — no customer context exists |
| S15 | Multi-intent Out Of Scope | Prompt asks for two independent tool families with no prebuilt chain | Force clean unsupported-workflow response | `Show me the fraud and spending summary for CUS007` | Must not return a partial answer or silently drop one half | Analyst note explains the two-tool gap |


## Per-Scenario Detail

### S01 Clean Fraud Happy Path

- Purpose:
  - baseline routing success
  - baseline grounded answer success
- Should support:
  - `get_transactions`
  - possibly `get_customer_profile_and_alerts` if the prompt asks for both
- Should teach:
  - what a confident, grounded answer looks like

### S02 Suspicious But Benign

- Purpose:
  - prevent prompts from equating high spend with fraud
- Should support:
  - spending summary
  - profile lookup
- Should teach:
  - why scenario design matters more than row count

### S03 Mixed Signal Low Risk

- Purpose:
  - create tension between isolated fraud signals and overall customer risk
- Should support:
  - transactions
  - profile
- Should teach:
  - why ontology needs terms like `suspicious` vs `confirmed fraud`

### S04 Alert Without Fraud Confirmation

- Purpose:
  - alert-focused but not fraud-confirmed
- Should support:
  - alerts
  - profile + alerts chain
- Should teach:
  - why prompt wording can cause overstatement

### S05 High Risk No Current Alerts

- Purpose:
  - separate risk profile from current alert state
- Should support:
  - customer profile
- Should teach:
  - why "risk" and "alerts" are different ontology concepts

### S06 and S07 Similar Alerts Different Outcomes

- Purpose:
  - two-customer compare case with superficially similar inputs but different implications
- Should support:
  - compare chain
- Should teach:
  - why compare workflows and evals need scenario design, not random data

### S08 Spending Heavy, Stable Customer

- Purpose:
  - support "behaviour" language without fraud or alerts
- Should support:
  - spending summary
- Should teach:
  - why `behaviour` must be explicitly defined

### S09 Low Spend, High Risk Customer

- Purpose:
  - inverse of the intuitive but wrong "big spend means high risk" assumption
- Should support:
  - profile
  - alerts
- Should teach:
  - why prompts need examples and anti-examples

### S10 Full Picture One Customer

- Purpose:
  - justify a prebuilt `get_full_picture` chain
- Should support:
  - profile + alerts + spending
- Should teach:
  - multi-step workflow without asking participants to build orchestration

### S11 Compare Customers Happy Path

- Purpose:
  - justify a prebuilt `compare_customers` chain
- Should support:
  - side-by-side customer comparison
- Should teach:
  - how prompt routing boundaries change when multiple customer IDs appear

### S10 and S11 Routing Boundary

Explicit decision:
- one customer, full picture phrasing -> get_full_picture
- two customers -> compare_customers
- "give me the full picture for CUS014 and CUS015" must either map to compare_customers
  or fail cleanly — it must never silently drop one customer

### Stage 2 Deliberate Misfire Anchor

Stage 2 uses S11 (Compare Customers Happy Path).
The compare_customers tool description in tools.yaml is intentionally weakened so it
under-triggers or misroutes on a natural comparison prompt.
Participants diagnose the misfire by reading tools.yaml and fix the description.
This is the only deliberately degraded part of the scaffold.

### S12 Comparison Out Of Scope

- Purpose:
  - force a clean failure for unsupported compare prompts
- Should support:
  - no tool / fallback
- Should teach:
  - not every failure is a prompt problem; sometimes the workflow is not supported

### S13 Out-of-domain Refusal

- Purpose:
  - test clean refusal for queries outside the banking analytics domain
- Should support:
  - no tool
- Should teach:
  - the model must refuse cleanly, not attempt to map to a banking tool
  - this is different from S12, which is still in-domain but unsupported workflow

### S14 Missing Customer ID

- Purpose:
  - test behavior when the prompt is in-domain but no CUS### identifier exists
- Should support:
  - clarification request or clean failure
- Should teach:
  - the app depends on a structured identifier
  - ambiguous references must not be guessed
  - this reveals the scaffold's dependency on the CUS### pattern

### S15 Multi-intent Out Of Scope

- Purpose:
  - test behavior when a prompt spans two independent tool families with no prebuilt chain
- Should support:
  - unsupported-workflow response, not a partial answer
- Should teach:
  - not every failure is a prompt problem; some are workflow gaps
  - this sets up the conversation about when to build new chains versus when to refuse


## Prompt Design Implications

This matrix should be reflected in:

- `prompts/tools.yaml`
  - examples
  - anti-examples
  - boundary cases
- `prompts/system.yaml`
  - routing rules
  - no-guessing rules
- `prompts/ontology.yaml`
  - terms such as `behaviour`, `risk profile`, `alert posture`, `suspicious`, `confirmed fraud`
- `prompts/format.yaml`
  - role-specific framing for risk vs service audiences


## Eval Design Implications

At minimum, the eval corpus should cover:

- single-tool happy paths
- chained happy paths
- compare happy paths
- suspicious-but-benign false-positive protection
- mixed-signal cases
- out-of-scope compare prompts
- prompts that should refuse rather than guess

## Facilitator Notes

- Keep scenario count manageable. Around 12-15 designed scenarios is enough.
- Do not overcomplicate the raw schema.
- Complexity should come from signal interaction and wording ambiguity, not from dozens of columns.
- A few well-written free-text fields are useful if they create better prompt behavior and audience-specific formatting exercises.
