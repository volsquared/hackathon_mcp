# Workshop Workflow SRS (v2)

## Hackathon Context

This workshop is a hands-on hackathon for engineers running locally on each participant's machine.
The core teaching goal is to help participants understand how an LLM-enabled application evolves from:

- brittle deterministic routing
- to tool-aware LLM routing
- to prompt tuning
- to eval-driven improvement
- to more advanced concepts such as ontology and workflow hardening

Each stage is intentionally designed to expose the limitation of the previous one.
Participants should feel the problem first, then implement the fix.

### Two Codebases

**Java project** -- stable workshop host. Serves the participant-facing guide, stage progression,
the seeded banking API, and local progress tracking. Participants do not edit this.

**Python project** -- the exercise surface. Participants edit this during the workshop.
Contains the Streamlit UI, agent graph, LLM integration, prompts, and eval runner.


## Purpose

Define a configurable, local-first workshop progression system for the Java-hosted workshop guide.

This is not a workflow engine. It is a narrow workshop progression tracker that runs on one machine
per participant, with no central server, no multi-user coordination, and no network dependency.


## Goals

- Allow facilitators to run the workshop in `open` or `challenge` mode
- Make the stage sequence configurable via YAML without code changes
- Persist participant progress across Java app restarts (SQLite)
- Let facilitators override participant state via a local admin page when needed
- Keep scoring auditable even when overrides are used
- Support config changes between workshop runs without rework


## Non-Goals

- A central server, leaderboard, or network-based score aggregation
- Multi-participant synchronisation or winner determination by the system
- A generic workflow or BPM engine
- Replacing the Python exercise surface or eval runner
- A real authentication or identity system
- Anything not needed for a single-day, single-machine hackathon


## Core Design Principles

1. Separate static workflow definition (YAML config) from mutable participant state (SQLite).
2. Store awarded score explicitly -- never derive it from current stage status.
3. Treat facilitator overrides as auditable events appended to a log, not silent mutations.
4. Keep completion rules to a small, bounded set of local verification types.
5. Prefer configuration over code for stage definitions and unlock rules.


## Operating Modes

### Open Mode

- All stages visible and accessible immediately
- Progress may still be tracked, but unlock logic is not enforced
- Scoring is informational only

### Challenge Mode

- Stage access controlled by unlock rules
- Completion, skip, and facilitator override actions affect participant state
- Scores are recorded and visible to the participant


## Identity

On first launch the Java app generates a stable local UUID (`participant_id`) and stores it in
SQLite. The participant also enters their name, stored as `display_name`.

`participant_id` is the durable identity used in all internal references. `display_name` is metadata
only -- it can be changed without affecting progress records. This prevents state collisions on
reset or re-run without adding any auth complexity.

One participant per machine. No password, no token.


## High-Level Architecture

### Static Workflow Definition

Loaded from a profile-specific workflow file at startup.

Current v1 runtime profiles:

- `open` -> `data/workflow-open.yaml`
- `challenge` -> `data/workflow-challenge.yaml`

Profile selection is resolved from `workshop.profile` / `WORKSHOP_PROFILE`.

Contains:

- workshop id and title
- mode: `open` or `challenge`
- scoring enabled flag
- ordered stages array

### Mutable Participant State

Persisted in a profile-specific SQLite database.

Current v1 runtime files:

- `open` -> `data/progress-open.db`
- `challenge` -> `data/progress-challenge.db`

Contains:

- participant display name
- workflow id and version it was created against
- stage states
- awarded scores
- timestamps

### Override Log

Appended to a profile-specific JSONL log on every facilitator action.

Current v1 runtime files:

- `open` -> `data/overrides-open.jsonl`
- `challenge` -> `data/overrides-challenge.jsonl`

Each entry contains:

- timestamp
- participant display name
- target stage id
- action taken
- reason
- old values
- new values


## Configuration

Workflow is defined in a profile-specific YAML file. No code change is required to modify stages within a profile.

Current v1 runtime profiles:

- `open` -> `data/workflow-open.yaml`
- `challenge` -> `data/workflow-challenge.yaml`

The active profile is selected at startup through `workshop.profile` / `WORKSHOP_PROFILE`.
Each profile resolves its own workflow file, participant progress database, and override log.

### Top-Level Fields

- `workflow_id`
- `title`
- `version`
- `mode`: `open` or `challenge`
- `learning_mode`: `recognition` -- only valid value in v1. `construction` is not supported and will cause a hard startup failure if set. Stage-level `learning_mode` override is not supported in v1; the field is reserved for future use.
- `scoring_enabled`
- `verification.python_project_path` -- absolute or relative path to the Python project root; used as cwd for all subprocess verification and scaffold file copy targets
- `stages`

### Runtime Profile Resolution

The workshop runtime profile is an operational selector, not a YAML field.

- `workshop.profile=open` resolves:
  - `data/workflow-open.yaml`
  - `data/progress-open.db`
  - `data/overrides-open.jsonl`
- `workshop.profile=challenge` resolves:
  - `data/workflow-challenge.yaml`
  - `data/progress-challenge.db`
  - `data/overrides-challenge.jsonl`

This separation is intentional. Open-mode participant state must not collide with challenge-mode participant state.

### Per-Stage Fields

- `id`
- `title`
- `description`
- `order`
- `learning_mode` (reserved) -- not supported in v1; presence in a stage config causes a hard startup failure
- `unlock_after` -- array of stage ids; all must satisfy the unlock condition before this stage unlocks (see Unlock Model)
- `points`
- `attempt_penalty` -- points deducted per wrong option selection in recognition mode; floor is `0`
- `allow_skip`
- `completion_rule`
- `scaffold` -- defines which files are in play for this stage; `base` and option directories must all contain these files (see Scaffold Model)
- `code_options` -- single-select options for recognition mode; see Recognition Mode
- `confirmation` -- recognition mode only; defines the proof-of-run file Java checks at Finish; mandatory for recognition mode stages; see Recognition Mode
- `resources`
- `exercises`

### Per-Exercise Fields

- `id`
- `title`
- `instructions`
- `files_to_edit`
- `expected_outcome`
- `verification`
- `optional`
- `tags`

### Completion Rule Types

Bounded set for v1:

- `manual` -- participant clicks "mark complete"
- `file_contains` -- Java checks a local file for a string
- `script_exit_code` -- Java runs a local script and checks exit code
- `eval_case_passes` -- Java invokes the Python eval runner via subprocess and checks result
- `facilitator_approval` -- requires the facilitator to approve via the admin page

New rule types can be added later without changing the persistence schema.


## Learning Modes

v1 supports `recognition` mode only. `construction` mode is reserved for a future version
and causes a hard startup failure if set. Per-stage `learning_mode` override is not supported
in v1.


### Recognition Mode

Participants identify the correct concept by selecting from options, then witness the correct
implementation applied to the Python project.

**Stage flow:**

1. Stage unlocks. Java copies `base` scaffold files into the Python project (see Scaffold Model).
   This gives the participant the broken/incomplete starting state.
2. Participant reads instructions in the Java UI. Attempt clock starts (`attempt_started_at` recorded).
3. Participant sees the options panel. Each option shows a syntax-highlighted diff read from
   the pre-generated diff file `data/scaffolds/stage_{id}/diffs/opt_{x}.diff` (see Scaffold
   Model). Participant selects one option and presses Confirm.
   - Wrong -> "Incorrect" feedback. Attempt counter increments. Penalty recorded against score.
     Participant reselects.
   - Correct -> "Apply Code" button enables.
4. Participant presses Apply Code. Java copies the correct option's files into the Python project,
   overwriting the base files. UI shows "Ready -- start your Python app."
5. Participant starts the Python app and exercises the relevant functionality.
   The Python scaffold writes a confirmation file to `.workshop/{stage_id}_complete.json`
   when the target function is called (see Confirmation File).
6. Participant returns to Java UI and presses Finish.
   - Confirmation file exists and is valid -> stage completes. Score awarded (see Scoring).
   - Confirmation file missing or invalid -> error shown. Stage remains open. Participant retries.
7. Admin can override Finish via the admin page, bypassing the confirmation file check.

**Wrong answer handling:**

Penalty is deducted per wrong selection, configured per stage via `attempt_penalty`.
`score_awarded` floor is `0` -- penalties cannot produce a negative stage score.
Attempt count is stored on the stage state record.

**Code options schema:**

```yaml
code_options:
  - id: opt_a
    label: Replace regex router with hardcoded if/else
    correct: false
  - id: opt_b
    label: Pass tool definitions to LLM and let it select
    correct: true
  - id: opt_c
    label: Add a keyword lookup table before the LLM call
    correct: false
```

- Exactly one option has `correct: true` per stage (single-select)
- `correct` flags are never exposed to the participant UI -- server-side only
- Option labels must be written as plausible, peer-level distractors.
  Labels that are obviously wrong defeat the teaching purpose.

**Confirmation file:**

```yaml
confirmation:
  trigger_function: handle_tool_routing_request
  output_file: .workshop/stage_2_complete.json
```

The confirmation file is written by the Python scaffold when `trigger_function` is called.
It is not written by the participant manually.

File contents must include:

- `stage_id`
- `timestamp`
- `function_name`

Java validates all three at Finish -- wrong `stage_id` rejected, `function_name` mismatch
rejected, timestamp unreasonably old flagged as warning but not blocked.

Confirmation files from prior stages are never deleted. They are an on-disk audit trail.
Java checks only the confirmation file for the current stage at Finish.

Participants cannot game progression by copying scaffold files forward. Java's stage state
is the source of truth -- file state in the Python project is untrusted input that is only
evaluated when a stage is in a valid completable state.

The confirmation file mechanism is not tamper-proof -- a participant could write the file
manually. This is acceptable for a workshop context where a facilitator is present.

**Recognition mode interaction state machine:**

Each recognition mode stage tracks an `interaction_state`:

```
idle -> selecting -> correct_selected -> applied -> completed
```

State definitions:

- `idle` -- stage just unlocked, no interaction yet
- `selecting` -- participant has begun selecting; `attempt_started_at` set on first `/select` call
- `correct_selected` -- correct option confirmed; no further selection permitted; awaiting Apply Code
- `applied` -- scaffold files copied into Python project; awaiting confirmation file
- `completed` -- confirmation validated or admin override; terminal state

Allowed transitions:

```
idle             -> selecting         (first /select call)
selecting        -> selecting         (wrong answer, retry)
selecting        -> correct_selected  (correct answer)
correct_selected -> applied           (/apply)
applied          -> completed         (/finish success or admin override)
ANY              -> completed         (admin override)
```

Disallowed transitions -- must return `409 Conflict`:

- `/apply` when `interaction_state != correct_selected`
- `/finish` when `interaction_state != applied`
- `/select` when `interaction_state == correct_selected` or `completed`
- any action when `interaction_state == completed`

API contracts:

`POST /api/stages/{stageId}/select`
- allowed when `interaction_state in {idle, selecting}`
- first call sets `attempt_started_at`, transitions to `selecting`
- wrong answer: increment `attempt_count`, remain `selecting`
- correct answer: set `selected_option_id`, transition to `correct_selected`

`POST /api/stages/{stageId}/apply`
- allowed when `interaction_state == correct_selected`
- copies scaffold files, sets `code_applied_at`, transitions to `applied`
- calling again after already applied returns `409`

`POST /api/stages/{stageId}/finish`
- allowed when `interaction_state == applied`
- validates confirmation file; success transitions to `completed`, failure remains `applied`

Scoring mutations only occur at transition to `completed`. No score is written before that point.

The UI reflects backend state -- it does not enforce transitions itself:

| `interaction_state` | UI behaviour                        |
|---------------------|-------------------------------------|
| `idle`              | options panel shown, selectable     |
| `selecting`         | options panel shown, selectable     |
| `correct_selected`  | Apply Code button enabled           |
| `applied`           | Finish button enabled               |
| `completed`         | all controls locked                 |

The backend enforces all transitions. The UI suggests; the backend decides.


### Construction Mode

> **Not supported in v1.**
>
> `learning_mode: construction` in `workflow.yaml` causes a hard startup failure in v1.
>
> Construction mode is deferred to a future version. It will require a separate interaction
> state machine, different scoring model, and different verification flow. It is not a
> trivial extension of recognition mode.


## Scaffold Model

### Directory Layout

Each stage has a `base` directory and one directory per option. All are stored under
`data/scaffolds/stage_{id}/` alongside `workflow.yaml`.

```
data/
  workflow.yaml
  scaffolds/
    stage_1/
      base/
        agent.py
      opt_a/
        agent.py
      opt_b/
        agent.py
      opt_c/
        agent.py
    stage_2/
      base/
        routing.py
        tools.py
      opt_a/
        routing.py
        tools.py
      opt_b/
        routing.py
        tools.py
```

### Base Directory

The `base` directory is the common starting point all options diverge from. It represents the
broken or incomplete state the participant will see and reason about.

Java copies `base` files into the Python project at **stage unlock**. This gives the participant
a clean, deterministic starting point before they engage with any options.

### Option Directories

Each option directory contains the complete replacement files for that variant.

Java uses option directories for one purpose only: **Apply** -- when the participant presses
Apply Code after correct selection, Java copies the correct option's files into the Python
project, overwriting the `base` files.

Diffs are not generated at runtime by Java. They are pre-generated by a Python setup script
and stored on disk. Java reads and renders them. See Diff Pre-Generation below.

### Diff Pre-Generation

Diffs are generated by `tools/generate_diffs.py`, a Python script using `difflib` (stdlib, no
dependencies). The facilitator runs this script once after editing scaffolds, before the
workshop starts.

The script:

1. Reads `workflow.yaml` to discover all stages and options
2. For each option, iterates over all files listed in `scaffold.files`, diffs each against
   its `base` counterpart using `difflib.unified_diff`
3. Concatenates all per-file diff output into a single string and writes it as one file per option

The output artifact is always one `.diff` file per option. There is never a separate diff file
per source file. A stage with three options and two source files produces three diff files, not six.

Output layout -- one `.diff` file per option:

```
data/
  scaffolds/
    stage_2/
      base/
        routing.py
        tools.py
      opt_a/
        routing.py
        tools.py
      opt_b/
        routing.py
        tools.py
      diffs/
        opt_a.diff
        opt_b.diff
```

Java reads `diffs/opt_{x}.diff` and renders it as a syntax-highlighted diff block in the
options panel. Java does not generate, parse, or interpret diff content -- it reads and displays.

If a diff file is missing at Java startup, that is a hard startup failure. Facilitator must
re-run `generate_diffs.py`.

`generate_diffs.py` must be re-run whenever:

- any `base` file is edited
- any option file is edited
- a new option or stage is added

It is idempotent -- safe to re-run at any time. It overwrites existing diff files.

### YAML Schema

```yaml
scaffold:
  files:
    - source: routing.py        <- filename, relative to the stage scaffold dir
      target: src/routing.py    <- target path relative to python_project_path
    - source: tools.py
      target: src/tools.py

code_options:
  - id: opt_a
    label: Replace regex router with hardcoded if/else
    scaffold_dir: scaffolds/stage_2/opt_a
    correct: false
  - id: opt_b
    label: Pass tool definitions to LLM and let it select
    scaffold_dir: scaffolds/stage_2/opt_b
    correct: true
  - id: opt_c
    label: Add a keyword lookup table before the LLM call
    scaffold_dir: scaffolds/stage_2/opt_c
    correct: false
```

`scaffold.files` defines which files are in play for this stage. The same list applies to
`base`, every option directory, and the Apply Code copy. All option directories must contain
every file listed in `scaffold.files`.

### Add / Remove / Rearrange

**Add an option:** create a new `opt_x` directory with the variant files, add one YAML entry.

**Remove an option:** delete the YAML entry and the directory.

**Rearrange options:** reorder YAML entries. Display order follows YAML order.

**Add a stage:** add a new stage entry in YAML, create `base` and option directories under
`data/scaffolds/stage_{id}/`. Everything else picks it up automatically.

### Diff Generation

Diffs are pre-generated by a Python utility script and stored as static files.
Java reads and renders them -- no diff library required, no runtime generation.

**Script:** `tools/generate_diffs.py`

Run by the facilitator after any changes to scaffold files:

```
python tools/generate_diffs.py
```

Output layout:

```
data/
  scaffolds/
    stage_2/
      diffs/
        opt_a.diff
        opt_b.diff
        opt_c.diff
```

Each diff file is a unified diff of the option files against `base`, generated via Python's
stdlib `difflib.unified_diff`. One diff file per option, covering all files in `scaffold.files`
concatenated into a single output.

Java validates at startup that a diff file exists for every option in every recognition mode
stage. A missing diff file is a hard startup failure -- same rule as missing scaffold files.

Facilitators must re-run `generate_diffs.py` after editing any `base` or option scaffold files.
Stale diffs are not detected automatically.




## Progress Model

### Participant Record

- `participant_id` (UUID, generated at first launch, immutable)
- `display_name` (mutable label, does not affect identity)
- `workflow_id`
- `workflow_version`
- `mode`
- `learning_mode`
- `total_score`
- `workshop_started_at` (set when first stage unlocks -- tiebreaker start)
- `workshop_finished_at` (set when final stage completes -- tiebreaker end)
- `created_at`
- `updated_at`

Participant progress identity in v1 is defined by:

- `workflow_id`
- `workflow_version`
- `mode`
- `learning_mode`

If a stored participant record does not match the currently loaded workflow identity on these fields,
the app must surface a workflow mismatch condition rather than silently treating the state as compatible.

### Stage State Record

- `stage_id`
- `status` -- `locked`, `unlocked`, `completed`, `skipped`
- `interaction_state` -- `idle`, `selecting`, `correct_selected`, `applied`, `completed`; recognition mode only, null for other modes
- `selected_option_id` (nullable) -- id of the confirmed correct option; set at transition to `correct_selected`
- `code_applied_at` (nullable timestamp) -- when Apply Code was pressed
- `verification_pending` (boolean) -- true while an async verification subprocess is running
- `attempt_count` -- number of wrong option selections in recognition mode
- `attempt_started_at` -- when the participant first engaged with this stage's options
- `unlocked_at`
- `completed_at`
- `skipped_at`
- `score_awarded`
- `score_source` -- `automatic`, `skip`, `facilitator_override`, `bonus`, `penalty`
- `completion_source` -- `automatic`, `manual`, `facilitator_override`
- `last_error`
- `override_reason`

Note: there is no `overridden` status. Override origin is captured in `score_source`
and `completion_source`. Status only reflects the current stage outcome.


## Scoring Model

- A completed stage awards its configured `points` minus accumulated attempt penalties
- Attempt penalty: `attempt_count * attempt_penalty` deducted from `points`; floor is `0`
- A skipped stage awards `0` by default
- The facilitator may set the awarded score for any stage via the admin page
- Bonus or penalty adjustments are stored as explicit adjustment records (see Adjustment Record below)
- Total score is the sum of all active `score_awarded` values plus all active adjustment amounts
- Score is never recomputed from status -- it is always the stored value

### Tiebreaker

Score is the primary ranking dimension. When two participants have equal `total_score`,
rank is determined by elapsed workshop time: `workshop_finished_at - workshop_started_at`.
Lower elapsed time wins. This value is derived at ranking time -- it is not stored as a field.

### Adjustment Record

Bonus and penalty adjustments are stored as first-class records, not derived from stage state.

Each adjustment record contains:

- `adjustment_id` (UUID)
- `participant_id`
- `stage_id` (nullable -- null means global, not tied to a stage)
- `amount` (positive for bonus, negative for penalty)
- `source` -- `bonus` or `penalty`
- `reason`
- `created_at`
- `active` (boolean)

Stage-linked adjustments (`stage_id` non-null) are deactivated (`active: false`) when their
stage is reopened. They do not contribute to `total_score` while inactive.
Global adjustments (`stage_id` null) are always active unless explicitly reversed.

### Score Lifecycle Under Mutation

**Reopen:** When a facilitator reopens a completed or skipped stage, `score_awarded` is set to `0`
and `score_source` is cleared. All adjustment records linked to that stage are set `active: false`.
The facilitator must re-award score explicitly if appropriate. Prior adjustment records are preserved
in the log.

**Reset:** A full progress reset clears all stage states and scores atomically and deactivates all
adjustment records. Override log entries are preserved. `total_score` returns to `0` after reset.

These rules are enforced by the service layer, not left to the caller.


## Unlock Model

### Open Mode

All stages are visible and accessible immediately.

### Challenge Mode

A stage unlocks when its `unlock_after` condition is satisfied, or the facilitator explicitly
unlocks it.

`unlock_after` semantics are ALL -- every listed prerequisite must satisfy the unlock condition.

A prerequisite satisfies the unlock condition if:

- its status is `completed`, OR
- its status is `skipped` AND `allow_skip` was `true` on that stage

A prerequisite with `allow_skip: false` that is skipped via facilitator override does NOT
automatically satisfy the unlock condition. The facilitator must also explicitly unlock the
downstream stage.


## Skip Model

- Skip is stage-level and explicit -- not a hidden side effect
- Skip policy is configurable per stage via `allow_skip`
- Skipping unlocks downstream stages when allowed
- Skipped stages award `0` by default
- Skip reason is recorded if provided


## Facilitator Override

The facilitator accesses a local admin page (served by the Java app) while sitting with the participant.

### Facilitator Must Be Able To

- Unlock a stage
- Mark a stage completed
- Mark a stage skipped
- Set awarded score for a stage
- Add bonus or penalty points
- Reset participant progress
- Reopen a completed or skipped stage
- View participant progress and override history

### Override Requirements

- Every override requires a reason (free text, mandatory field)
- Every override is appended to `data/overrides.jsonl` with timestamp and old/new values
- Overrides do not erase prior log entries
- Participant state after override must be internally consistent
- State change and audit log write are both required. If the JSONL append fails, the state
  change must be rolled back and the override must be rejected with an error. A state change
  without an audit record is not permitted.


## Verification

Java reads the configured `completion_rule` for the stage and executes it locally.

### Verification Sources

- Local file inspection (`file_contains`)
- Local subprocess call (`script_exit_code`, `eval_case_passes`)
- Facilitator approval via admin page
- Participant self-declaration (`manual`)

### Verification Execution Constraints

All subprocess-based verification rules (`script_exit_code`, `eval_case_passes`) must observe:

- **Working directory**: always the Python project root, configured at startup via
  `verification.python_project_path` in `workflow.yaml`. Never derived from cwd at runtime.
- **Timeout**: configurable per completion rule via `timeout_seconds`, default `30`.
  If the subprocess exceeds the timeout it is killed and the verification result is `passed: false`
  with `message: "timeout"`. The stage remains in its prior status.
- **Non-determinism**: `eval_case_passes` may produce variable output. The verification contract
  is exit code only -- `0` = passed, non-zero = failed. The eval runner is responsible for
  deterministic exit codes; the Java layer does not interpret stdout beyond storing it as `evidence`.

### Verification Latency Model

`manual` and `file_contains` are synchronous -- result returned inline in the HTTP response.

`script_exit_code` and `eval_case_passes` are potentially slow. These are executed
asynchronously. The `POST /api/stages/{stageId}/verify` call returns immediately with status
`pending`. The participant UI polls `GET /api/progress` until the stage state updates.
A verification in progress is visible as `verification_pending: true` on the stage state record.

If `POST /api/stages/{stageId}/verify` is called while `verification_pending` is already `true`,
the server returns `409 Conflict` with the current pending state. No new subprocess is started.

The participant UI polls `GET /api/progress` every 1 second while `verification_pending: true`,
backing off to every 2 seconds after 10 seconds have elapsed.

### Verification Result Shape

- `passed` (boolean)
- `message`
- `checked_at`
- `evidence` (string -- stdout snippet, matched string, or empty)

Java stores the result and updates stage state accordingly.


## API Requirements

The Java app exposes local HTTP APIs used by both the participant UI and the admin page.

### Participant APIs

- `GET /api/workshop` -- returns workflow definition for current mode
- `GET /api/progress` -- returns participant progress, stage states, and scores
- `POST /api/stages/{stageId}/verify` -- runs configured local verification
- `POST /api/stages/{stageId}/skip` -- requests skip when permitted
- `POST /api/stages/{stageId}/select` -- submits selected option id in recognition mode; returns correct/incorrect and updated attempt count
- `POST /api/stages/{stageId}/apply` -- applies scaffold files to Python project; only valid after correct option selected
- `POST /api/stages/{stageId}/finish` -- checks confirmation file and completes stage in recognition mode

### Facilitator Admin APIs

- `POST /api/admin/stages/{stageId}/unlock`
- `POST /api/admin/stages/{stageId}/complete`
- `POST /api/admin/stages/{stageId}/skip`
- `POST /api/admin/stages/{stageId}/score`
- `POST /api/admin/participants/reset`
- `GET /api/admin/progress`
- `GET /api/admin/history`

Every mutating admin request must include `reason`. Score override requests must also include
`score_awarded` and `score_source`.

Admin routes are served under `/api/admin` and must not be linked or exposed in the participant UI.
No authentication is required in v1. This is intentional -- the security model is social contract:
one person per machine, facilitator acts in person. The route separation is a footgun guard,
not an access control boundary. Do not describe it as secure.


## UI Requirements

### Participant UI

- Open mode: all stages visible, all tutorial content shown, optional progress markers
- Challenge mode: clearly shows locked / unlocked / completed / skipped states, current score,
  completion status per stage, skip option where permitted

### Facilitator Admin Page

Served at `/admin`. Accessible locally.

Must support:

- View participant progress and current score
- Override any stage (unlock, complete, skip, adjust score)
- View override history
- Reset all progress


## Consistency Rules

The service layer must enforce these invariants. Any operation that would violate them must be
rejected, not silently allowed.

**Status/timestamp alignment:**
- `status=completed` requires `completed_at` non-null; `skipped_at` must be null
- `status=skipped` requires `skipped_at` non-null; `completed_at` must be null
- `status=locked` or `status=unlocked` requires both `completed_at` and `skipped_at` null

**Verification/status alignment:**
- `verification_pending=true` cannot coexist with `status=completed` or `status=skipped`

**Interaction/status alignment (recognition mode):**
- `status=completed` requires `interaction_state=completed`
- `interaction_state=completed` requires `status=completed`
- `status in {locked, unlocked}` requires `interaction_state != completed`

**Score/status/source alignment:**
- `score_source=automatic` is only valid when `status=completed`
- `score_source=skip` is only valid when `status=skipped` and `score_awarded=0`
- `score_awarded` non-zero on a `locked` stage is only valid if set by facilitator override

**Override log:**
- Entries are append-only -- no deletes, no in-place updates

**Score totals:**
- `total_score` must equal the sum of all active `score_awarded` values plus all active adjustment amounts at all times. Any mutation to score must update `total_score` in the same atomic transaction.


## YAML Validation

The active profile's workflow YAML is validated at startup before any participant state is loaded.
A validation failure must produce a clear error and halt startup -- not silent corruption.

Required validations:

- All stage `id` values are present, non-empty, and unique
- All `unlock_after` references point to stage ids that exist in the config
- `unlock_after` chains contain no cycles (circular dependency = hard fail)
- `completion_rule` values are from the known bounded set
- `order` values are unique across stages
- `learning_mode` at top level must be `recognition`; any other value is a hard startup failure
- `learning_mode` must not appear at stage level in v1; presence is a hard startup failure
- `verification.python_project_path` is present and non-empty
- Every stage has a `base` scaffold directory containing all files listed in `scaffold.files`
- Every option `scaffold_dir` exists and contains all files listed in `scaffold.files`
- Every recognition mode option has a corresponding `diffs/opt_{x}.diff` file under `data/scaffolds/stage_{id}/diffs/`
- Recognition mode stages have at least one `code_options` entry with `correct: true`
- Recognition mode stages have a `confirmation` block with `trigger_function` and `output_file`

If the active workflow YAML fails validation, the app must not start.
The facilitator must fix the config before participants can proceed.


## Config Evolution

Between workshop runs the facilitator may need to add, remove, reorder, rename,
or repoint stages in `workflow.yaml`.

The workflow definition carries a `version` field.
Participant progress stores the `workflow_version` it was created against.

If the workflow version changes mid-run the system must detect the mismatch on startup and
log a clear warning. The participant's existing progress is preserved unchanged.
The facilitator decides whether to reset or continue. The system does not attempt automatic migration.

Safe changes during a run (no version bump required): changing `title`, `description`, `resources`.
Changes that require a version bump: adding, removing, or reordering stages, changing `id` values.


## Failure Handling

- Verification failure does not alter existing stage state -- the stage remains in its prior status
- A crashed verification script is logged; the facilitator can manually override
- A malformed `workflow.yaml` must produce a clear startup error, not silent corruption
- SQLite write failures are logged; state remains recoverable from last successful write
- The override log is append-only; if writing the audit record fails, the override must be rejected and the state change rolled back


## Observability

The Java app must log:

- Workflow config load (version, stage count, mode)
- Participant progress updates
- Verification attempts and outcomes (passed/failed, rule type, evidence)
- Facilitator overrides (full before/after)
- Score mutations
- Persistence failures

Logs must be sufficient to reconstruct what happened during the workshop without consulting the database.


## Implementation Scope

One phase. Build what is needed for the hackathon.

- YAML-driven workflow definition with startup validation
- Stable local UUID identity generated at first launch
- SQLite participant progress persistence
- Stage unlock logic (`unlock_after`, formalised skip-propagation semantics)
- Stage completion recording (automatic and manual)
- Skip support
- Recognition mode: single-select options panel, attempt penalty scoring, Apply Code scaffold copy, confirmation file check at Finish
- `tools/generate_diffs.py` -- Python setup script using `difflib`; pre-generates all option diffs before workshop start
- Scaffold file copy mechanism (straight file replacement, no diffing at runtime)
- Startup validation of scaffold file existence
- Tiebreaker fields (`workshop_started_at`, `workshop_finished_at`) on participant record
- Local verification runner (subprocess + file inspection, cwd pinned, timeout enforced)
- Async verification with `verification_pending` polling model
- Score lifecycle rules for reopen and reset
- Facilitator admin page with override and history views
- Explicit score awarding and audit log
- Startup version mismatch warning
- Construction mode (placeholder -- not in current scope)


## What Is Explicitly Out Of Scope

- Leaderboard or winner determination -- the facilitator asks participants at the end
- Network-based score collection
- Stage timers
- Authentication
- Workflow version migration tooling
- Analytics or reporting
- Anything requiring a central server
