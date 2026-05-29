Merged Workshop Plan
====================

Core principle:
Each stage solves the problem revealed by the previous stage.
"Great, that worked. Now we can clearly see the next limitation."

Audience: engineers, some off code for a while.
Calibration: scaffolded but not babied.
- Read and trace the pipeline: fine, no hand-holding
- Edit .env and config/app.yaml: trivial
- Edit YAML prompt files: comfortable, can go deep
- Add eval test cases in Python: fine with the shape provided
- Extend a tool parameter: fine with scaffold
- Build new chains from scratch during workshop: too slow, avoid
- Debug LangChain internals: wrong rabbit hole, avoid


BEFORE STAGE 0: PARTICIPANT SETUP
---------------------------------

Exercise:
Set up the repo from `cmd`, then open it in VS Code.

Objective:
Participants should start from a consistent editor/interpreter environment before touching the app.

Ask:
Create the local `.venv` and install dependencies from `cmd`, then open the repo in VS Code and confirm it is using the venv interpreter.

How To Do It:

Option A: `cmd`

1. Create the venv:
   `py -3.11 -m venv .venv`
   This creates a repo-local Python environment in `.venv`.
2. Activate the environment:
   `.venv\Scripts\activate.bat`
   After activation, your prompt should show `(.venv)` at the start.
3. Install dependencies:
   `py -3.11 -m pip install -r requirements.txt`
   This installs Streamlit, LangChain, and the other Python packages used by the app.

Option B: PowerShell

1. Create the venv:
   `py -3.11 -m venv .venv`
   This creates a repo-local Python environment in `.venv`.
2. Activate the environment:
   `.venv\Scripts\Activate.ps1`
   After activation, your prompt should show `(.venv)` at the start.
   If PowerShell blocks script execution, run:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
   then retry the activation command.
3. Install dependencies:
   `py -3.11 -m pip install -r requirements.txt`
   This installs Streamlit, LangChain, and the other Python packages used by the app.

Then:

1. Launch VS Code
   Open VS Code only after the venv and dependencies exist, so interpreter discovery is easier.
2. Open the `mcp` folder in VS Code
   Open the repo root, not an inner folder like `app/`.
3. Install the Microsoft Python extension
   Accept the recommended extension prompt if VS Code shows it.
4. If needed, run `Python: Select Interpreter`
   Use `Ctrl+Shift+P` to open the command palette, then search for `Python: Select Interpreter`.
5. Choose `.venv\Scripts\python.exe`
   This ensures the editor, terminal, and language server all use the repo-local environment.
6. Open a new integrated terminal if VS Code needs to re-detect the environment
   The new terminal should activate the venv automatically if VS Code picked up the workspace settings.

Relevant files:

- `.vscode/settings.json`
- `.vscode/extensions.json`
- `README.md`

Success Criteria:

- VS Code is using the repo-local interpreter
- the terminal activates `.venv`
- imports resolve cleanly in the editor
- the participant can run the app from VS Code


WORKSHOP PROGRESS DB VERIFICATION
---------------------------------

Use this when verifying that the Java workshop foundation created and preserved the
local participant state in SQLite.

Database paths:

- `C:\Users\upadh\git\hackathon\java\data\progress-open.db`
- `C:\Users\upadh\git\hackathon\java\data\progress-challenge.db`

Use the database that matches the active workshop mode:

- `OPEN` -> `progress-open.db`
- `CHALLENGE` -> `progress-challenge.db`

Open the SQLite shell from the Java repo:

1. `sqlite3 data\progress-open.db` or `sqlite3 data\progress-challenge.db`
2. `.tables`
3. `.headers on`
4. `.mode column`

Core verification queries:

```sql
SELECT participant_id, display_name, workflow_id, workflow_version, created_at, updated_at
FROM participant_progress;

SELECT participant_id, stage_id, status, completed_at
FROM stage_state
ORDER BY stage_id;
```

Expected Tranche 1 result:

- `participant_progress` contains exactly one participant row
- `workflow_id` matches the active workflow
- `workflow_version` matches the active workflow version
- `stage_state` may still be empty in Tranche 1

Restart verification:

1. stop the Java app
2. start the Java app again
3. re-run:

```sql
SELECT participant_id, workflow_id, workflow_version, created_at, updated_at
FROM participant_progress;
```

The `participant_id` should remain unchanged across restarts. That confirms identity
is bootstrap-only and survives restart correctly.


WORKSHOP YAML GUARDRAILS
------------------------

Use these rules when adding or editing Java workshop exercise YAML. Most of the
recent EX-08 startup failures were new exercise-config validation failures, not
broad app regressions.

Validation constraints currently observed:

- `concepts_covered` must contain at most 6 entries
- `current_system_points` must contain at most 5 entries
- recognition-mode `code_options[].overlay` must define `router`
  even if it is the same value as the base overlay
- YAML plain scalars containing `:` should be quoted, or moved to a block scalar

Overlay source-of-truth rule:

- the Java workshop applies the inline `code_options[].overlay` block from
  `exercise.yaml`
- `overlays/opt_*.json` files are snippet/reference files shown in the UI
- do not assume snippet files are what gets applied at runtime

Overlay/runtime wiring rule:

- Java writes `.workshop/overlay_config.json`
- Java injects `exercise_id` and `option_applied` when writing that file
- Python fixed-state branches that gate on `config.overlay.exercise_id` depend on
  that injected value, not on anything written inline in the exercise overlay

Text-preservation rule:

- preserve spec-authored participant-facing text verbatim by default
- extra implementation wording is allowed only as an addition around the spec text
- do not rewrite curated spec prose unless explicitly asked


BACKEND VERIFICATION SCRIPT (T1–T6)
------------------------------------

A reusable bash script for verifying the Java workshop backend end-to-end.

Location: `C:\Users\upadh\git\hackathon\bridge\verify.sh`

What it covers:
- T1: startup, SQLite bootstrap, restart persistence
- T2: stage unlock, skip, complete, reopen, score recomputation
- T3: admin mutations, reason enforcement, audit log
- T4: recognition flow (select → apply → finish), interaction state transitions
- T5: file_contains (sync), script_exit_code (async), eval_case_passes (async),
      pending-state polling, duplicate verify rejection, timeout
- T6: informational only — lists known gaps, does not assert pass/fail

Usage:

```bash
# Full run — wipes DB and bootstraps fresh
bash verify.sh

# Skip DB wipe (resume from existing state)
bash verify.sh --no-wipe
```

The script pauses at exactly two points requiring a manual restart:
1. After wiping the active profile database (`progress-open.db` or `progress-challenge.db`) — restart the Java app, then press Enter
2. After adding T5 test stages to `workflow.yaml` — restart the Java app, then press Enter

The script manages `workflow.yaml` backup/restore and creates/deletes its own test
fixture automatically. When the run ends, `workflow.yaml` is restored to the original
single-stage config and all temporary files are cleaned up.

Prerequisites:
- Java app running at `http://localhost:8080`
- `sqlite3` binary at `C:\Users\upadh\git\sqllite3\sqlite3.exe`
- Git Bash or WSL for running bash


FACILITATOR ADMIN CONTROLS
--------------------------

Use these after the Java workshop progression system is enabled. The admin surface is
for facilitator recovery and score correction, not for normal participant flow.

Admin entry points:

- UI: `http://localhost:8080/admin`
- Swagger: `http://localhost:8080/q/swagger-ui`

Core admin read endpoints:

- `GET /api/admin/progress`
  - returns participant progress plus score adjustments
- `GET /api/admin/history`
  - returns append-only override history from `data/overrides.jsonl`

Core admin mutation endpoints:

- `POST /api/admin/stages/{stageId}/unlock`
  - force-unlocks a locked stage
- `POST /api/admin/stages/{stageId}/complete`
  - force-completes a stage as facilitator override
- `POST /api/admin/stages/{stageId}/skip`
  - force-skips a stage as facilitator override
- `POST /api/admin/stages/{stageId}/reopen`
  - reopens a completed or skipped stage
- `POST /api/admin/stages/{stageId}/score`
  - overrides the stored score for a completed or skipped stage
- `POST /api/admin/stages/{stageId}/adjustment`
  - adds a stage-linked bonus or penalty adjustment
- `POST /api/admin/participants/adjustment`
  - adds a participant-level bonus or penalty adjustment
- `POST /api/admin/participants/reset`
  - resets participant progress to initial workflow state

Important semantics:

- Every admin mutation requires `reason`
- `/score` is stage-specific
- `/score` only accepts:
  - `scoreSource: facilitator_override`
- `/adjustment` is for:
  - `source: bonus`
  - `source: penalty`
- Reopening a stage:
  - resets that stage score to `0`
  - deactivates stage-linked adjustments for that stage
  - does not re-lock downstream stages
- Reset:
  - resets all stage states to the initial workflow state
  - deactivates all adjustments
  - resets `totalScore` to `0`

Example request bodies:

Score override:

```json
{
  "scoreAwarded": 7,
  "scoreSource": "facilitator_override",
  "reason": "manual score correction"
}
```

Stage adjustment:

```json
{
  "amount": 3,
  "source": "bonus",
  "reason": "stage-specific bonus"
}
```

Global adjustment:

```json
{
  "amount": -2,
  "source": "penalty",
  "reason": "global penalty test"
}
```

Reopen / unlock / complete / skip / reset:

```json
{
  "reason": "facilitator override test"
}
```

Recommended verification order:

1. `GET /api/admin/progress`
2. `POST /api/admin/stages/stage-0/complete`
3. `POST /api/admin/stages/stage-0/score`
4. `POST /api/admin/stages/stage-0/adjustment`
5. `POST /api/admin/stages/stage-0/reopen`
6. `POST /api/admin/participants/adjustment`
7. `POST /api/admin/participants/reset`
8. `GET /api/admin/history`

What to verify:

- `totalScore` recomputes after every score-affecting mutation
- stage-linked adjustments become inactive after reopen
- all adjustments become inactive after reset
- every admin mutation produces an audit history entry


PREBUILT INFRASTRUCTURE (facilitator builds before workshop)
------------------------------------------------------------

1. Richer Java seed data
   Not just more rows. Scenarios must include:
   - suspicious-but-benign customers (high spend, no fraud flags)
   - mixed-signal customers (one fraud flag, low risk rating)
   - similar alerts with different outcomes
   - customers where spending, alerts, and fraud signals conflict
   - edge cases designed to make routing decisions non-trivial
   Target: 15-20 customers, varied risk ratings, segments, statuses

2. Three prebuilt chains in tool_execution.py + tools.yaml
   - get_customer_profile_and_alerts (already exists)
   - get_full_picture: profile + alerts + spending for one customer
   - compare_customers: profile + alerts for two customers side by side

3. Ground truth eval corpus in app/eval/runner.py
   Written before prompt tuning begins. Treat as the specification.
   Must cover:
   - correct tool/chain selection across natural language variants
   - out-of-scope prompts that must return no tool
   - chain boundary cases (two customer IDs -> compare chain, not profile chain)
   - answer property checks (should_contain, should_not_contain)
   - prompts that should compare but must not trigger single-customer chains
   Target: 15-20 cases

4. Richer starter prompts in prompts/
   - system.yaml: give the model a real role, constraints, and tone
   - tools.yaml: one tool should have a deliberately weak description (Stage 2 setup)
   - ontology.yaml: stub with real terms but incomplete definitions (Stage 6 setup)
   - format.yaml: basic output shape, no audience framing yet (Stage 4 setup)


LIVE DEMO PROMPTS (facilitator use — weak vs strong prompt before/after)
-------------------------------------------------------------------------

Run these three prompts against prompts/ (weak) and prompts_facilitator/ (strong)
to show participants what prompt quality actually changes. Use them in this order.

Script: scripts/demo_compare.py — output goes to output/cl_1.txt.

1. CUS009's profile says LOW risk but I've heard there was recent fraud activity —
   what do the transactions show and should I be concerned?

   Why: contradiction between profile signal and transaction evidence.
   Weak path calls get_full_picture and underplays the issue — acknowledges fraud
   amounts exist but concludes "monitoring advisable" without urgency.
   Strong path calls get_transactions and makes the contradiction explicit: LOW profile
   rating but multiple fraud-flagged transactions totalling over £2,400 in one week,
   indicating current risk is materially higher than the rating reflects.
   Use this to show: prompt quality changes what the model prioritises, not just
   what it retrieves.

2. Give me the full picture on CUS015 — I need to make a credit line decision.

   Why: multi-signal synthesis on a complex account.
   Both paths call get_full_picture. Use this as the secondary example showing that
   prompt quality affects answer richness and business framing even when tool
   selection is identical. CUS015 has stacked signals: HIGH fraud alert, MEDIUM AML
   alert citing unexplained dormancy, a prior address change, and a spending history
   that dropped from £500/month to near zero in six weeks.

3. Look at the full transaction and alert history for CUS017 and CUS018 — which
   presents more risk right now?

   Why: counter-intuitive comparative reasoning.
   Weak path concludes CUS018 is riskier — anchors on the MEDIUM risk rating and
   prior fraud history.
   Strong path concludes CUS017 is riskier — correctly identifies that CUS018's
   fraud alert is resolved and recent activity is clean, while CUS017 has two
   unresolved fraud-flagged transactions in April and an open MEDIUM alert despite
   a LOW risk rating.
   Use this to show: stronger prompts override stale signals with fresher evidence.

Demo sequence rationale:
  1 → profile vs transaction contradiction (prompt changes prioritisation)
  2 → same tool, richer synthesis (prompt changes answer quality)
  3 → counter-intuitive comparison (prompt changes the conclusion entirely)

Optional alternative demo prompts:
  Use these if you want the contradiction stated explicitly in the user question,
  so the audience can more easily see what the weak and strong prompt sets do with it.
  These are especially useful for a cleaner live demo narrative, even though they may
  reduce the weak-vs-strong gap in some cases by helping both sides frame the task.

  1. CUS018 still has a higher risk rating, but CUS017 has had more recent fraud
     activity - which account is the more immediate concern and why?

  2. CUS015 used to spend normally but has gone quiet - do the alerts and
     transaction history suggest a credit line should be declined or just reviewed?

  3. The alert on CUS009 says low severity and no immediate action, but the recent
     transaction pattern looks different - what changed, and how worried should I be?


WORKSHOP STAGES
---------------

Stage 0: Run It, Then Break It
  Activity:
    Run the app with a supported prompt: "Show fraud for CUS007"
    Then run a natural-language variant the deterministic router mishandles
  Details:
    - Start the Java API first, then run the Streamlit app in this repo
    - Use one prompt that clearly fits the existing scaffold and one that is phrased more naturally
    - Observe both the answer and the `Details` panel in the UI
    - Notice which tool was selected and what tool input was extracted
  Aha: it works, but only because the path is narrow and pre-shaped
  Revealed: deterministic routing is brittle; we need semantic routing

Stage 1: Turn On LLM Mode
  Activity:
    Configure .env and config/app.yaml
    Move the app from deterministic to llm-ready
    Re-run the failing prompt from Stage 0
  Details:
    - Copy `.env.example` to `.env`
    - Add a real API key for the provider you want to use
    - Set `llm.enabled: true` and choose provider/model in `config/app.yaml`
    - Restart Streamlit after making the config change
    - Confirm in the sidebar that the mode changed to `llm-ready`
  Aha: the app now understands natural language phrasing
  Revealed: understanding the question is not enough; answers are still weak and raw

Stage 2: Diagnose A Deliberate Misfire
  Activity:
    Use the prebuilt get_full_picture or compare_customers workflow
    Run a prompt that should be handled but misroutes due to the weak tool description
    Diagnose why it misfired, then fix the tool description in tools.yaml
  Details:
    - Start from the intentionally weak prompt/tool description provided in the scaffold
    - Run the target prompt and inspect which tool or chain was actually selected
    - Read `prompts/tools.yaml` and identify why the model may have chosen the wrong path
    - Make the smallest prompt change that should correct the routing
    - Re-run the same prompt and compare before/after behavior
  Aha: the capability exists, but prompt guidance decides whether it fires correctly
  Revealed: even with correct routing, answers lack business framing and feel generic

Stage 3: Brief The Model
  Activity:
    Improve system.yaml: add role, constraints, tone, and behavioral rules
    Improve tools.yaml: add examples and anti-examples to each tool
    Re-run the misfiring prompt and compare behavior
  Details:
    - Treat `system.yaml` like the model's job description
    - Make the role specific to the banking use case instead of generic assistant language
    - Add concrete examples in `tools.yaml` that distinguish nearby workflows
    - Add anti-examples so the model can see what should not trigger a tool
    - Re-run both the original misfire and one nearby prompt to check for regressions
  Aha: prompt wording changes routing behavior without touching Python
  Revealed: routing can improve, but the answer shape and tone may still be wrong for the audience

Stage 4: Shape The Answer For The Audience
  Activity:
    Improve format.yaml for two different roles (e.g. risk officer vs customer service)
    Run the same query with each format configuration and compare answers
  Details:
    - Keep the tool result the same and only change the formatting instructions
    - Make one version direct and risk-focused
    - Make the other version clearer and less internal-jargon heavy
    - Compare not just wording but structure, emphasis, and recommendations
    - Check whether the answer still stays grounded in the tool output
  Problem solved:
    The model can now produce answers shaped for the audience instead of just dumping raw findings.
  Aha:
    Same data and same tools produce very different useful outputs depending on briefing.
  New problem revealed:
    Once answer shape is under control, users immediately ask for explanation as well as conclusion.
    The current prompt set can answer, but it does not yet define when or how to provide a short rationale.

Optional Stage 4A: Add Short Rationale Mode
  Activity:
    Compare two prompt sets:
    - baseline prompts that return answer only
    - facilitator prompts that also return a short rationale when the user explicitly asks for it
  Details:
    - Keep the user query the same except for adding a phrase like "and include a short rationale" or "and explain briefly why"
    - Observe that the baseline prompt set answers the question but does not intentionally support a separate rationale field
    - Observe that the facilitator prompt set is explicitly brief by default, but can add a short evidence-based rationale on request
    - Use the `Details` panel to inspect `answer_rationale` when it is present
    - Keep the rationale short and grounded in tool results rather than asking for chain-of-thought
    - Suggested prompt pairs:
      1. `Give me the full picture on CUS015.`
         `Give me the full picture on CUS015 and include a short rationale.`
      2. `Which presents more risk right now, CUS017 or CUS018?`
         `Which presents more risk right now, CUS017 or CUS018, and why?`
      3. `Show fraud for CUS009.`
         `Show fraud for CUS009 and explain briefly why that matters.`
  Problem solved:
    The facilitator prompt set can now add a controlled short rationale on request without changing code or tools.
  Aha:
    Prompt instructions alone can introduce an explanation mode, but only if that mode is specified clearly.
  New problem revealed:
    As soon as rationale is possible, it becomes another behavior that can drift.
    Some answers will be too long, too vague, or insufficiently grounded unless rationale quality is tested explicitly.

Stage 5: Write Ground Truth And Measure
  Activity:
    Inspect or extend the prebuilt eval corpus
    Treat cases as the expected behavior specification, not as after-the-fact checks
    Tune prompts to pass failing cases
    Re-run and compare scores
  Details:
    - Read the existing eval cases before editing prompts
    - Treat each failing case as a statement of desired behavior
    - Add at least one case that checks answer content, not just selected tool
    - Add at least one case that checks rationale behavior when the user explicitly asks for explanation
    - Add at least one case that confirms rationale is absent or minimal when the user does not ask for it
    - Use `should_contain` and `should_not_contain` style checks where exact text is too brittle
    - Re-run the eval after each prompt change rather than batching lots of changes together
  Problem solved:
    Prompt behavior is no longer judged by intuition alone; it is turned into an explicit specification.
  Aha:
    Prompt engineering is a proper loop: write -> test -> measure -> improve.
  New problem revealed:
    Even with tests, ambiguous domain language still causes inconsistent routing and interpretation.

Stage 6: Define Ontology
  Activity:
    Use ontology.yaml to define key business terms:
    - behaviour
    - risk profile
    - alert posture
    - spending behaviour
    - comparison request
    - suspicious vs confirmed fraud
  Details:
    - Keep the ontology tied to concepts the app can actually fetch or infer from tool output
    - Define both meaning and usage, not just dictionary-style labels
    - Be explicit where terms are often confused, such as suspicious vs confirmed fraud
    - Use the eval failures from Stage 5 to decide which terms most need definition
    - Avoid turning ontology into a generic glossary detached from app behavior
  Aha: ambiguity is a domain-definition problem, not just a prompt-wording problem
  Revealed: prompts still need to use the ontology consistently through examples

Stage 7: Tune Prompts With Ontology
  Activity:
    Refine system.yaml and tools.yaml using the ontology definitions
    Add ontology-backed examples and anti-examples
    Re-run evals and compare outcomes against Stage 5 baseline
  Details:
    - Revisit the prompts with the ontology terms in front of you
    - Replace vague words with the ontology-backed wording where useful
    - Add examples that exercise the newly defined concepts
    - Add anti-examples that protect workflow boundaries
    - Compare eval results against the earlier baseline, not just against intuition
  Aha: ontology plus prompt tuning improves precision, consistency, and boundary handling
  Revealed: next frontier is broader workflow coverage and harder scenario types

Stage 8: Expand And Harden
  Activity:
    Add more eval cases for edge scenarios
    Extend or add a chain for a more complex workflow
    Or harden for production: error handling, out-of-scope refusals, ambiguous inputs
  Details:
    - Pick one direction rather than trying to do all of them in one session
    - For edge scenarios, prefer cases that stress boundaries rather than just adding volume
    - For workflow expansion, reuse the existing chain pattern instead of redesigning the architecture
    - For hardening, focus on refusal quality, missing inputs, and ambiguous requests
    - Use the same loop from Stage 5: define expected behavior, then implement and verify it
  Aha: the loop (data -> chain -> eval -> prompt) is repeatable and extensible
  No single revealed problem - this is the open frontier


BUILD BACKLOG (this repo)
--------------------------

Priority 1: get_full_picture chain
  - tool_execution.py: add elif for get_full_picture
  - tools.yaml: add entry with use_for, examples, do_not_use_for

Priority 2: compare_customers chain
  - tool_execution.py: add elif for compare_customers (two customer IDs)
  - tools.yaml: add entry with strict boundary conditions

Priority 3: Ground truth eval corpus
  - app/eval/runner.py: expand to 15-20 cases
  - Add should_contain / should_not_contain answer checks

Priority 4: Richer starter prompts
  - system.yaml: real role and constraints
  - tools.yaml: one deliberately weak description for Stage 2
  - ontology.yaml: real terms, incomplete definitions (gap for Stage 6)
  - format.yaml: output shape only, no audience framing (gap for Stage 4)

Priority 5: Java seed data
  - Facilitator prereq, not in this repo
  - Must be co-designed with eval cases and chain boundaries
