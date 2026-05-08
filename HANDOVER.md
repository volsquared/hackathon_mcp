# Session Handover

Date: 2026-05-07

## Current Focus

Active work is split across:

- `mcp/` for the Python banking-agent runtime, prompts, and Streamlit UI
- `java/` for workshop orchestration, exercise YAML, scaffolds, and participant `/workshop` UI

The live thread now has two parts:

1. the participant experience for `ex-002` and `ex-003`
2. groundwork for the next exercise around deliberate LLM tool-selection misfires caused by weak `tools.yaml`

## What Changed Today

### `java` participant page

`ParticipantPageResource.java` was iterated heavily and is now materially ahead of the old handover state.

Current participant-page state:

- lower `Hackathon Workshop` summary panel removed
- hero renamed to `GenAI Lab`
- `Recognition` and `Open Mode` / `Challenge Mode` moved into the top hero card
- `Learning Intent` reduced to two lanes
- `Your Assignment` made the visual centerpiece
- `Pre-Exercise Check` made more generic and YAML-driven
- duplicate precheck instruction rendering removed
- `What this exercise teaches` formatting tightened
- Routing/learning content is rendered through reusable JS block functions inside `ParticipantPageResource.java`

Also fixed:

- visible formatting issues in the left learning column
- the old broken/odd system-point marker issue
- duplicate `Pre-Exercise Check` content

### `java` exercise content

`ex-002-system-is-blind` was refined:

- prompt pair now teaches a cleaner wording contrast around:
  - `Show me the risk profile for CUS001`
  - `Show me the risk situation for CUS001`

`ex-003-give-it-a-brain` was updated to reflect the real intended participant flow:

- participants must replace two things after apply:
  - `api_base` in `config/app.yaml` with the bank-supplied Cortex URL
  - `GEMINI_API_KEY` in `.env` with the real workshop key
- stage scaffold no longer copies `tool_decision.py`
- `opt_a` now teaches Cortex + Gemini key wiring, not the older direct OpenAI path
- wrong options were updated to fail for Cortex-relevant reasons

Updated files for `ex-003` include:

- `java/data/exercises/ex-003-give-it-a-brain/exercise.yaml`
- `java/data/exercises/ex-003-give-it-a-brain/scaffolds/base/...`
- `java/data/exercises/ex-003-give-it-a-brain/scaffolds/opt_a/...`
- `java/data/exercises/ex-003-give-it-a-brain/scaffolds/opt_b/...`
- `java/data/exercises/ex-003-give-it-a-brain/scaffolds/opt_c/...`
- `java/data/exercises/ex-003-give-it-a-brain/scaffolds/opt_d/...`

### workflow ordering

The active workflow files now keep only live exercises:

- `ex-002-system-is-blind`
- `ex-003-give-it-a-brain`

`ex-001` and `ex-004` were removed from the active workflow for now.

## `mcp` Runtime Changes

Two small but important product changes were made for the next exercise work:

### Visible routing reasoning

In `mcp/app/ui.py`, the visible Routing Trace now shows:

- `routing_mode`
- `matched_keyword`
- `selected_tool`
- `decision_source`
- `fallback`
- `tool_reasoning`

This matters because the next exercise likely depends on participants seeing why the model chose the wrong tool.

### LLM tool-choice reasoning is now required

In `mcp/app/llm/factory.py`:

- `ToolChoiceSchema.reasoning` is now required and non-empty
- the chooser prompt explicitly instructs the model to return one short sentence explaining the decisive boundary

This was done so future tool-routing exercises do not depend on optional/null reasoning.

## Important Findings For The Next Exercise

The next exercise is the deliberate misfire / weak `tools.yaml` exercise.

Key findings:

### 1. `tools.yaml` is the right main lever

Tool selection loads descriptions from:

- `mcp/prompts/tools.yaml`

So the exercise can be scaffolded primarily around prompt-contract quality rather than code changes.

### 2. Current weak `system.yaml` is a confounder

Current `mcp/prompts/system.yaml` says to prefer the most comprehensive tool when in doubt.

That means a misfire toward `get_full_picture` may be caused partly by system prompt policy, not just weak `tools.yaml`.

For a clean exercise:

- keep a fixed neutral/strong system prompt
- vary only `tools.yaml`

Otherwise the teaching point is muddy.

### 3. Legacy deterministic routing is still a confounder

The app still has deterministic keyword fallback for words like:

- `risk`
- `profile`
- `alert`
- `transaction`
- `spend`
- `summary`

So prompts containing those words can collapse into deterministic routing if the LLM call fails.

This matters because:

- `Which customer is riskier right now, CUS017 or CUS018?`

is not a clean prompt for the new exercise unless the LLM path is definitely working.

Safer prompt candidates for tomorrow:

- `Between CUS017 and CUS018, who deserves closer scrutiny right now?`
- `Looking at CUS017 and CUS018 together, who should an analyst review first?`
- `Which of CUS017 and CUS018 looks more concerning at the moment?`

### 4. Live model validation is currently blocked from this shell

Direct LLM tests from this environment currently fail with:

- `SSL: CERTIFICATE_VERIFY_FAILED`
- then `APIConnectionError`

As a result:

- the app falls back to deterministic routing in shell-based tests
- I could not honestly validate “candidate weak `tools.yaml` set misfires consistently on the actual model” from this shell

This is the main blocker for finishing the next exercise spec properly.

## Candidate `tools.yaml` Degraded Sets Prepared

These were prepared as starting points for tomorrow, but not yet validated on a working live LLM path:

### Set A: Minimal overlap

- `get_customer_profile`: "Get information about a customer."
- `get_full_picture`: "Get a complete view of a customer."
- `compare_customers`: "Compare two customers."

### Set B: Comprehensiveness trap

- `get_customer_profile`: "Get customer information, including risk details."
- `get_full_picture`: "Get the fullest customer information available."
- `compare_customers`: "Look at two customers together."

### Set C: Boundary blur

- `get_customer_profile`: "Use for customer status, risk, and general customer questions."
- `get_full_picture`: "Use for broad questions about a customer."
- `compare_customers`: "Use when looking at two customers."

These are not yet confirmed stable enough for workshop use.

## Claude / SRS State

A detailed note for Claude was prepared covering:

- why `tools.yaml` is the right lever
- why `tool_reasoning` needed to be surfaced
- why live validation must be empirical, not assumed on paper
- why the weak system prompt is a confounder
- why deterministic keywords contaminate certain prompt choices

That note is complete. The missing input for Claude is the live observed misfire behavior from an actually working LLM path.

## Verification Status

Verified today:

- `java` Maven compile passed after the participant page and exercise changes
- `mcp` edited Python files parse cleanly (`ui.py`, `factory.py`)

Not yet verified:

- stable live LLM misfire behavior for candidate degraded `tools.yaml` sets

## Recommended Next Step Tomorrow

1. Re-read this file.
2. Start from the next-exercise thread, not the ex-002/ex-003 UI thread.
3. Validate the LLM path in a working runtime where outbound TLS is not blocked.
4. Keep `system.yaml` fixed and neutral.
5. Test the candidate degraded `tools.yaml` sets against a pinned two-customer prompt that avoids deterministic keywords.
6. Record:
   - selected tool
   - visible `tool_reasoning`
   - whether the misfire is stable enough for workshop use
7. Only then finalize the SRS for the deliberate misfire exercise.

## Most Important Practical Reminder

Do not let the next exercise accidentally demonstrate:

- weak `system.yaml`
- deterministic fallback keywords
- or broken network/TLS

when the intended teaching point is:

- ambiguous tool descriptions cause wrong LLM tool selection

