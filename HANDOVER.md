# Session Handover

Date: 2026-05-11

## Current State

The workshop platform has been repivoted from scaffold/file-copy semantics to an overlay-driven runtime model.

Current split of responsibilities:

- `mcp/`
  - stable Python runtime
  - Streamlit UI
  - routing, tool execution, response formatting
  - runtime behavior selected from `.workshop/overlay_config.json`
- `java/`
  - workshop orchestration
  - participant `/workshop` UI
  - exercise YAML definitions
  - participant progress DB
  - writes overlay state into `mcp/.workshop/overlay_config.json`

The active workshop now only contains:

- `java/data/exercises/ex-002-system-is-blind`
- `java/data/exercises/ex-003-give-it-a-brain`

Removed as part of cleanup:

- `ex-001-evidence-routing`
- `ex-004-explain-why`
- old scaffold-copy trees under `java/data/scaffolds/` and per-exercise scaffold directories that were no longer needed

## Major Architecture Change

### Old model

The workshop previously relied on copying exercise scaffold files into the Python repo to simulate stage changes.

That model caused:

- hidden state
- cross-stage drift
- hard resets
- unclear ownership between Java and Python

### New model

Java `Apply` now writes a declarative overlay file:

- `mcp/.workshop/overlay_config.json`

Python reads that file at startup and resolves runtime behavior from stable registries.

Overlay surfaces currently supported:

- `router`
- `tool_descriptions`
- `system_prompt`
- `format`
- `ontology`
- `llm` settings

Key Python files:

- `mcp/app/config.py`
- `mcp/app/runtime_overlays.py`
- `mcp/app/agent/nodes/tool_decision.py`
- `mcp/app/llm/factory.py`

Key Java files:

- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowDefinition.java`
- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowSummary.java`
- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowConfigService.java`
- `java/src/main/java/com/hackathon/banking/workshop/progress/ProgressRepository.java`

Registry assets live in:

- `mcp/runtime_assets/`

Important rule:

- no stage-specific Python codepaths were introduced
- stage behavior is selected by overlay values and registries, not by exercise ID branches

## Exercise YAML Migration

Both active exercises now use declarative overlay configuration instead of scaffold-copy semantics:

- `java/data/exercises/ex-002-system-is-blind/exercise.yaml`
- `java/data/exercises/ex-003-give-it-a-brain/exercise.yaml`

Each stage now defines:

- `base_overlay`
- `code_options[].overlay`
- `confirmation`

EX-02 base/correct behavior:

- base router: `deterministic`
- correct option: `keyword_extended`

EX-03 base/correct behavior:

- base router: `keyword_extended`
- correct option: `semantic_v1` with LLM/Cortex overlay config

Note:

- EX-03 snippets still reference `config/app.yaml` and `.env` as participant-facing learning material
- runtime behavior itself now comes from overlay config, not copied files

## Confirmation / Finish Flow

### UX model now

The workshop no longer waits for the UI to somehow detect filesystem writes.

Current behavior:

1. participant selects correct option
2. participant clicks `Apply`
3. `Finish` becomes clickable immediately
4. if participant clicks `Finish` too early, backend blocks completion and the UI tells them to run the Python exercise first
5. after a valid run, `Finish` succeeds

### Why this changed

Without websockets or polling, the browser cannot auto-enable `Finish` when a file appears in `.workshop/`.

So the gate moved from button enablement to server-side validation on `Finish`.

### Python confirmation write

Python writes completion files from:

- `mcp/app/confirmation.py`

Triggered from:

- `mcp/app/agent/graph.py`

The completion file is only written when the run satisfies stage confirmation criteria.

It is no longer written for:

- nonsense prompts that hit fallback
- `selected_tool = none`
- `identify_runtime`
- fatal errors
- missing tool results

### Stage-specific confirmation criteria

This was tightened further for EX-02.

EX-02 now only counts as exercised when the repaired route is actually used:

- `selected_tool == get_customer_profile`
- `routing_trace.matched_keyword == risk`

This means:

- `Show me the risk situation for CUS001` counts
- `Show me the risk profile for CUS001` does not
- nonsense does not

These criteria are declared in:

- `java/data/exercises/ex-002-system-is-blind/exercise.yaml`

And are propagated through:

- Java workflow config models
- live overlay payload
- Python confirmation logic

Current confirmation files:

- `.workshop/system_is_blind_complete.json`
- `.workshop/give_it_a_brain_complete.json`

## Open vs Challenge Mode

### Runtime profile

Java still defaults to `open` unless `WORKSHOP_PROFILE=challenge` is explicitly set.

The selector is here:

- `java/src/main/java/com/hackathon/banking/workshop/config/WorkshopRuntimeProfile.java`

And `workflow-open.yaml` is still:

- `mode: open`

### Important fix

Earlier in the refactor, open mode still behaved like challenge mode for stage locking because unlock logic did not branch by mode.

That is now fixed.

Current behavior:

- `open`
  - all stages unlock immediately
- `challenge`
  - `unlock_after` is respected

Implemented in:

- `java/src/main/java/com/hackathon/banking/workshop/progress/ProgressRepository.java`

Specifically:

- `initialStageState(...)`
- `resetLaterStageState(...)`

Important operational note:

- existing rows in `progress-open.db` are not magically rewritten
- after this change, you must reset progress or delete `progress-open.db` to see the corrected open-mode visibility cleanly

## Runtime / Logging Improvements

### Python trace output

The Streamlit-side runtime now emits a coherent per-request trace block to console/logs, bounded by:

```text
==============================================
...
==============================================
```

It includes:

- request phase
- routing phase
- execution phase
- response phase
- result phase
- `py_file` for each step
- full Java HTTP URL for banking calls
- LLM call metadata when LLM routing/answering is active

Key files:

- `mcp/app/trace.py`
- `mcp/app/agent/state.py`
- `mcp/app/agent/graph.py`
- `mcp/app/agent/nodes/tool_decision.py`
- `mcp/app/agent/nodes/tool_execution.py`
- `mcp/app/agent/nodes/response_formatter.py`

### Logging fix

Windows startup log rollover crash was fixed by removing forced eager rollover from:

- `mcp/app/logging_config.py`

## Known Current Behavior

### EX-02

Expected base state:

- `router: deterministic`
- `exercise_id: ex-system-is-blind`

Expected tests:

- `Show me the risk profile for CUS001`
  - succeeds
- `Show me the risk situation for CUS001`
  - fails with fallback in base state
- after correct apply
  - `Show me the risk situation for CUS001` succeeds
  - `How exposed are we with CUS001?` still fails

### EX-03

Expected base state after stage transition:

- `router: keyword_extended`
- `exercise_id: ex-give-it-a-brain`

Correct apply should move runtime toward:

- `router: semantic_v1`
- LLM overlay set for Cortex/Gemini

Note:

- real LLM success still depends on valid workshop URL/key placeholders being replaced in live config/env inputs as instructed by the exercise

## Reset Procedure

For a clean workshop reset:

In `java/data`:

- delete `progress-open.db`
- optionally delete `progress-challenge.db`
- optionally delete `overrides-open.jsonl`
- optionally delete `overrides-challenge.jsonl`

In `mcp/.workshop`:

- delete `overlay_config.json`
- delete `*_complete.json`

Recommended order after cleanup:

1. start Java
2. open `/workshop` once
3. confirm Java recreated `.workshop/overlay_config.json`
4. start or restart Streamlit

If testing `open` mode stage visibility after the latest fix, use a fresh `progress-open.db` or `Reset Progress`.

## Git / Cleanup Notes

The following were intentionally cleaned up and should not be restored unless needed:

- temporary extraction files from `mcp/`
- `mcp/workshop_ui/`
- old scaffold-copy exercise folders
- abandoned exercise directories for EX-01 and EX-04

`.gitignore` in `mcp/` includes:

- `.workshop/overlay_config.json`

## Verification Completed

Verified repeatedly during this session:

- Python compile checks via `.venv\Scripts\python.exe -m py_compile ...`
- Java compile:

```powershell
C:\Users\upadh\git\hackathon\java\tools\apache-maven-3.9.8\bin\mvn.cmd -q -DskipTests compile
```

Compile passed after:

- overlay architecture refactor
- confirmation flow refactor
- EX-02 route-specific confirmation criteria
- open-vs-challenge unlock split

## Recommended Next Steps

1. Do a clean reset with fresh `progress-open.db` and `.workshop/overlay_config.json`.
2. Re-verify `open` mode now shows both stages immediately.
3. Re-apply EX-02 after restart so the latest confirmation criteria are written into the overlay payload.
4. Manually retest:
   - premature `Finish`
   - nonsense prompt
   - `risk profile`
   - `risk situation`
5. Decide whether EX-03 also needs stricter stage-specific confirmation criteria instead of the current generic “real non-fallback run” rule.
