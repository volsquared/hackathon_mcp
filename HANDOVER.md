# Session Handover

Date: 2026-05-06

## Current Focus

The live work is split across:

- `mcp/` for the Python banking-agent runtime and Streamlit UI
- `java/` for the workshop flow, exercise YAML pipeline, and participant `/workshop` page

The immediate product thread is still the participant exercise experience, especially how generic stage content should be rendered without hardcoding one-off layouts for a single exercise.

## Live State Confirmed

### `mcp` runtime

- The current router in `app/agent/nodes/tool_decision.py` is deterministic and keyword-based.
- `routing_trace` is carried in `AgentState` and exposed in the Streamlit `Details` expander.
- LLM answer generation still happens only after a tool result exists and only when the runtime is configured.
- The baseline `ex-system-is-blind` teaching point is therefore still correct: the system does not understand intent; it matches hardcoded keywords.

### `java` workflow pipeline

The YAML-driven fields are wired end-to-end:

- `description`
- `exercise_brief`
- `current_system_points`
- `why_this_matters`
- `context_snippet`
- `pre_exercise_check`
- `post_apply_guidance`
- `observation_check`

Key files:

- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowDefinition.java`
- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowConfigService.java`
- `java/src/main/java/com/hackathon/banking/workshop/config/WorkflowSummary.java`
- `java/src/main/java/com/hackathon/banking/workshop/WorkshopFoundationService.java`
- `java/src/main/java/com/hackathon/banking/workshop/progress/StageProgressView.java`
- `java/src/main/java/com/hackathon/banking/resource/ParticipantPageResource.java`

### Participant page

The current stage page is rendered from JS block functions inside `ParticipantPageResource.java`, including:

- `exerciseBriefBlock`
- `contextSnippetBlock`
- `preExerciseCheckBlock`
- `assignmentBlock`
- `postApplyGuidanceBlock`
- `nextStepsBlock`

This is already more structured than the older handover implied. Some of the earlier “outstanding issues” are stale now.

## Stale Notes Corrected

The previous handover is no longer fully accurate.

- `.info-toggle` CSS is now defined.
- `postApplyGuidanceBlock` already uses `renderRichText(...)`.
- The participant page has moved beyond the earlier simpler callout structure.

Do not rely on the old outstanding-issues list without re-reading the current code.

## Exercise State

Current exercises visible in `java/data/exercises/`:

- `ex-001-evidence-routing`
- `ex-002-system-is-blind`
- `ex-004-explain-why`

`ex-002-system-is-blind` currently teaches:

- the router only follows known keywords
- adding `risk` is a local patch, not real intent understanding
- prompt wording changes still break the system

Important content file:

- `java/data/exercises/ex-002-system-is-blind/exercise.yaml`

Important snippet:

- `java/data/exercises/ex-002-system-is-blind/snippets/current_tool_selection.py`

## UI Direction To Preserve

The main product constraint is unchanged:

- do not let the participant page overfit one exercise
- keep content rendering generic enough for future exercises
- prefer a small set of reusable panel/block types over bespoke stage-specific layout logic

That said, the user wants the main assignment area to feel like the visual centerpiece of the stage. The right way to do that is to strengthen the generic assignment panel, not to bake ex-002-specific assumptions into the framework.

## Workspace Notes

- `mcp/` has local uncommitted changes.
- `java/` is readable, but `git status` is currently blocked by Git `safe.directory` ownership checks for this user.

## Suggested Next Step

If resuming tomorrow:

1. Re-read this file.
2. Re-open `ParticipantPageResource.java`.
3. Treat `assignmentBlock` as the main visual anchor, but keep the block generic.
4. Review current code before trusting any older handover notes.
