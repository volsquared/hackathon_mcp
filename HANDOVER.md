# Session Handover

Date: 2026-05-08

## Current Focus

Active work is still split across:

- `mcp/` for the Python banking-agent runtime, prompts, and Streamlit UI
- `java/` for workshop orchestration, exercise YAML, scaffolds, participant `/workshop` UI, and facilitator `/admin`

The thread today moved from participant-page rendering into facilitator reset mechanics and the underlying state model.

## What Changed Today

### `java` participant page rendering

The `Stage Guidance` / post-apply guidance rendering bug shown in screenshot `../Bridge/35.jpg` was fixed in:

- `java/src/main/java/com/hackathon/banking/resource/ParticipantPageResource.java`

Root cause:

- `pre_exercise_check` content used `renderRichText(...)`
- `post_apply_guidance` and the sidebar helper used raw `esc(...)`
- so markdown-like multiline content rendered as one escaped paragraph with visible backticks and collapsed numbering

What changed:

- `post_apply_guidance` now renders through `renderRichText(...)`
- sidebar helper copy in `Stage Guidance` now also renders through `renderRichText(...)`
- `renderRichText(...)` was extended to support simple ordered and unordered list blocks
- CSS was updated so rich-text `ol` / `ul` blocks render cleanly

Result:

- `ex-003` guidance now shows proper numbered steps and inline code formatting for:
  - `config/app.yaml`
  - `.env`
  - `api_base`
  - `llm-ready`

Verification:

- `mvn -q -DskipTests compile` passed in `java/`

### `java` workflow content validation fix

The failing Quarkus boot/test issue was traced to workflow validation:

- `ex-give-it-a-brain` defined 6 `current_system_points`
- validator hard-limit is 5 in `WorkflowConfigService`

Fix made in:

- `java/data/exercises/ex-003-give-it-a-brain/exercise.yaml`

Change:

- merged the two separate wiring bullets into one:
  - `Cortex gateway and Gemini API key not wired together`

This removes the startup validation failure without weakening the validator.

### `java` admin rewind feature

A new facilitator operation was added to rewind participant progress so a chosen stage becomes active again.

Added files / endpoints:

- `java/src/main/java/com/hackathon/banking/workshop/admin/AdminResetToStageRequest.java`
- `POST /api/admin/participants/reset-to-stage`

Main code paths:

- `java/src/main/java/com/hackathon/banking/resource/AdminResource.java`
- `java/src/main/java/com/hackathon/banking/workshop/admin/AdminService.java`
- `java/src/main/java/com/hackathon/banking/workshop/progress/ProgressRepository.java`

Admin page UI:

- `/admin` top `Progress` panel now includes:
  - stage dropdown
  - reason box
  - `Reset To Stage` button

Current semantics:

- stages before `X`: preserved as-is
- stage `X`: reset to active (`UNLOCKED` / `IDLE`)
- stages after `X`:
  - `CHALLENGE` mode: reset to `LOCKED`
  - `OPEN` mode: reset to fresh `UNLOCKED`
- stage-level adjustments for `X` and later are deactivated
- participant totals are recomputed
- admin audit log gets a `reset_to_stage` record

Compile verification:

- `mvn -q -DskipTests compile` passed in `java/`

## Critical Finding: DB Rewind Is Not Workspace Rewind

This is the most important result from today.

The new admin rewind currently rewinds database progress state, but it does **not** fully rewind the participant filesystem state.

Observed failure mode:

- facilitator reset progress to `ex-system-is-blind`
- participant state in Java showed the earlier exercise correctly
- after rebooting the Python app, it still came up `llm-ready`

Why:

- rewinding to `ex-002` recopies only the base scaffold for `ex-002`
- `ex-002` owns `app/agent/nodes/tool_decision.py`
- `ex-003` previously wrote `config/app.yaml` and `.env`
- those later file changes remain in the Python workspace
- the Python runtime reads the real files, not the Java DB notion of exercise position

So the current feature is:

- **progress rewind**

not:

- **workspace checkpoint restore**

This mismatch matters especially for:

- `.env`
- `config/app.yaml`
- any future stage that mutates files not owned by earlier stages

## Architectural Discussion Reached Today

We discussed whether to keep stage-specific file copies such as `init/` folders under scaffolds.

Conclusion:

- that would solve some rollback problems
- but it creates a serious sync/drift burden as real files evolve
- it is too easy for workshop scaffolds/checkpoints to go stale relative to actual source

We also discussed using Git branches per stage.

Conclusion:

- branches/tags are a much better **authoring** source of truth than hand-maintained scaffold snapshots
- but they are the wrong **participant delivery** surface if exposed directly, because they leak the answer key too easily

Best current direction:

- use Git branches/tags internally as authoritative authoring checkpoints
- generate workshop scaffolds/snippets/checkpoints from that source
- do not expose those branches directly to participants

The strongest reset model for later work is probably:

1. restore a canonical baseline participant workspace
2. replay completed stages before target `X`
3. make stage `X` active
4. clear DB progress for `X` and later

That would give a real checkpoint restore, not just DB rewind.

## Recommended Next Step

Do **not** treat the current `reset-to-stage` feature as complete workshop checkpoint restore.

The next real design decision should be about workspace authority and reset strategy:

Option A:

- canonical baseline + replay of earlier completed stages

Option B:

- generated per-stage checkpoint snapshots from internal Git branches/tags

Option C:

- hand-maintained per-stage `init`/restore copies

Recommendation:

- prefer `A` or `B`
- avoid `C` unless the workshop stays very small and stable

## Practical Reminder

If you use the new admin rewind right now:

- the Java DB/progress state will move back
- the Python workspace may still contain later-stage file mutations
- therefore the runtime behavior may not match the rewound stage until workspace restore logic exists
