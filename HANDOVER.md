# Session Handover

Date: 2026-05-16

## Current State

The workshop is still using the overlay-driven runtime model:

- `mcp/`
  - stable Python runtime
  - Streamlit UI
  - router, tool execution, response formatting
  - runtime behavior selected from `mcp/.workshop/overlay_config.json`
- `java/`
  - workshop orchestration
  - participant `/workshop` UI
  - exercise YAML definitions
  - participant progress DB
  - writes overlay state into `mcp/.workshop/overlay_config.json`

Current exercise set in both workflow manifests:

- `java/data/exercises/ex-002-system-is-blind`
- `java/data/exercises/ex-003-give-it-a-brain`
- `java/data/exercises/ex-004-ai-chose-wrong`

Workflow manifests now reference all three and were bumped to:

- `java/data/workflow-open.yaml`
  - `version: v3-open`
- `java/data/workflow-challenge.yaml`
  - `version: v3-challenge`

## Important Changes From This Session

### EX-03 LLM profile parameterization

EX-03 was parameterized so the applied overlay can be driven by one workshop-level profile instead of hardcoding one provider path.

Files:

- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowConfigService.java`
- `java/data/exercises/ex-003-give-it-a-brain/exercise.yaml`

Behavior:

- default behavior remains Cortex/Gemini
- single env var override supported:
  - `WORKSHOP_LLM_PROFILE=gpt`
  - supported values:
    - `cortex` / `gemini`
    - `gpt` / `openai`

Important detail:

- the actual runtime overlay written by Java is still resolved from exercise YAML
- display-only JSON snippets do not resolve placeholders automatically

Also added:

- startup log line for resolved LLM profile in `WorkflowConfigService.java`

### Observation check UI fix

The participant observation-check section no longer disappears after `Finish`.

File:

- `java/src/main/resources/META-INF/resources/workshop.js`

Behavior now:

- editable while stage is `UNLOCKED` and `APPLIED`
- visible read-only after terminal state:
  - `COMPLETED`
  - `SKIPPED`

### `.gitignore`

Selective workshop runtime ignores now include:

- `.workshop/overlay_config.json`
- `.workshop/*_complete.json`

File:

- `mcp/.gitignore`

## EX-04 Status

### What was implemented

A new exercise was added:

- `java/data/exercises/ex-004-ai-chose-wrong/exercise.yaml`

Supporting assets were added:

- `java/data/exercises/ex-004-ai-chose-wrong/overlays/base.json`
- `java/data/exercises/ex-004-ai-chose-wrong/overlays/opt_a.json`
- `java/data/exercises/ex-004-ai-chose-wrong/overlays/opt_b.json`
- `java/data/exercises/ex-004-ai-chose-wrong/overlays/opt_c.json`
- `java/data/exercises/ex-004-ai-chose-wrong/overlays/opt_d.json`

New runtime asset packs:

- `mcp/runtime_assets/tool_descriptions/ambiguous_v1.yaml`
- `mcp/runtime_assets/tool_descriptions/clear_disambiguated_v1.yaml`
- `mcp/runtime_assets/tool_descriptions/keyword_heavy_v1.yaml`
- `mcp/runtime_assets/tool_descriptions/example_anchored_v1.yaml`
- `mcp/runtime_assets/system_prompts/neutral_tool_routing_v1.yaml`
- `mcp/runtime_assets/system_prompts/precision_tool_preference_v1.yaml`

Router choice:

- `semantic_with_descriptions`

This is deliberate and correct.
`semantic_v1` does not pass tool descriptions into the LLM tool-choice call, so the exercise would be invalid if it used that router.

### EX-04 redesign that happened today

The original two-customer comparison premise was invalid for the current model/tool surface.

Observed failure of original premise:

- prompt variants containing two customer IDs consistently selected:
  - `compare_customers`
- even when the ambiguous description pack was weakened
- the model keyed strongly on the two-customer shape, so the intended misroute did not happen

Because of that, EX-04 was redesigned around a single-customer ambiguity:

- ambiguous pair is now:
  - `get_customer_profile_and_alerts`
  - `get_full_picture`

New teaching point:

- ambiguous descriptions make the model choose the narrower profile+alerts tool
- corrected descriptions should push it to `get_full_picture` when the prompt implies escalation or full review

Current EX-04 confirmation gate:

- `selected_tool: get_full_picture`

### Current EX-04 pinned prompt

Base-state validation prompt to test tomorrow:

```text
I need to decide whether CUS017 should be escalated. Give me what I need to review first.
```

Out-of-distribution follow-up prompt after the correct fix:

```text
Full risk review of CUS017 before I escalate it.
```

### What still needs validation

EX-04 is structurally implemented but NOT production-ready yet.

It still needs live model validation.

Specifically, base `ambiguous_v1` must be tested to see whether it misroutes the pinned prompt to the narrower tool:

- desired wrong base selection:
  - `get_customer_profile_and_alerts`
- desired correct post-fix selection:
  - `get_full_picture`

Tomorrow’s first task is to validate EX-04 base state with the pinned prompt above and capture:

1. `selected_tool`
2. `tool_reasoning`
3. whether the answer is truly full-evidence review or just profile + alerts

If base still chooses `get_full_picture`, EX-04 needs another redesign/tightening before release.

## Open Items Not Yet Actioned

### AdminPageResource.java — HTML still inline

`java/src/main/java/com/hackathon/banking/resource/AdminPageResource.java`
returns a full HTML page (including inline CSS and ~140 lines of JavaScript)
as a Java text block.

Fix: move to `src/main/resources/META-INF/resources/admin.html`.
Quarkus serves that directory as static assets automatically.
The `/admin` endpoint can then redirect or read from classpath.

This is isolated, carries no risk to workshop flow, and was not prioritised
this session. Still needs doing.

### EX-03 confirmation criteria — still unresolved

Currently any real non-fallback run satisfies EX-03 completion.
The open question from the previous session: should EX-03 add a specific
`selected_tool` gate (e.g. requiring the LLM to actually pick a banking tool)
or a `matched_keyword` gate?

No decision was made this session. Carry forward.

## Known Good Compile State

Java compile passed after this session’s changes:

```powershell
C:\Users\upadh\git\hackathon\java\tools\apache-maven-3.9.8\bin\mvn.cmd -q -DskipTests compile
```

This compile passed after:

- EX-03 profile parameterization
- observation check visibility fix
- EX-04 initial implementation
- EX-04 redesign to single-customer ambiguity

## Operational Notes

### Clean reset procedure

For a clean workshop reset:

In `java/data`:

- delete `progress-open.db`
- optionally delete `progress-challenge.db`
- optionally delete `overrides-open.jsonl`
- optionally delete `overrides-challenge.jsonl`

In `mcp/.workshop`:

- delete `overlay_config.json`
- delete `*_complete.json`

Recommended order:

1. start Java
2. open `/workshop` once
3. confirm Java recreated `mcp/.workshop/overlay_config.json`
4. start or restart Streamlit

### LLM profile switching

Default workshop behavior:

- Cortex/Gemini

To override EX-03/EX-04 applied overlays to GPT/OpenAI before starting Java:

```powershell
$env:WORKSHOP_LLM_PROFILE = "gpt"
```

To return to default workshop behavior:

```powershell
Remove-Item Env:WORKSHOP_LLM_PROFILE -ErrorAction SilentlyContinue
```

### Streamlit restarts

When runtime asset files under `mcp/runtime_assets/` change:

- restart Streamlit before retesting

Java restart is not always required for asset-file-only changes, but is required when:

- changing Java code
- changing workflow manifests
- changing Java exercise YAML and wanting fresh workshop state

## Recommended Next Step Tomorrow

1. Restart Streamlit.
2. Reach EX-04 base state with no option applied.
3. Run:

```text
I need to decide whether CUS017 should be escalated. Give me what I need to review first.
```

4. Capture:
   - `selected_tool`
   - `tool_reasoning`
   - whether response uses full activity evidence or only profile + alerts
5. Decide whether `ambiguous_v1` is now good enough or EX-04 needs another redesign.
