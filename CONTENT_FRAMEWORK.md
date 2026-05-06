# Workshop Content Framework

This document describes how workshop content is currently structured across the Java workshop engine and the `mcp` Python project.

It is intended as a handoff for content-design agents so they can propose new exercises that fit the existing system rather than inventing a parallel model.

## High-Level Model

The workshop currently uses a **manifest + exercise library** structure:

- A top-level workflow manifest defines the workshop identity and mode.
- The manifest composes a list of child exercises via `exercise_refs`.
- Each exercise lives in its own folder and is defined by a single `exercise.yaml`.
- Each exercise provides:
  - participant-facing metadata
  - recognition-mode answer options
  - scaffold assets
  - snippet/diff assets
  - optional pre-exercise guidance
  - optional post-apply guidance
  - optional observation-check questions

The workshop is currently focused on `learning_mode: recognition`.

## Current File Layout

Top-level workflow manifests:

- `java/data/workflow-open.yaml`
- `java/data/workflow-challenge.yaml`

Exercise library root:

- `java/data/exercises/`

Current sample exercises:

- `java/data/exercises/ex-001-evidence-routing/`
- `java/data/exercises/ex-004-explain-why/`

Typical exercise folder structure:

```text
ex-001-some-exercise/
  exercise.yaml
  scaffolds/
    base/
      ...
    opt_a/
      ...
    opt_b/
      ...
  diffs/
    opt_a.diff
    opt_b.diff
```

## Workflow Manifest Format

The workflow manifest defines the workshop-level runtime profile and the ordered list of exercises.

Example:

```yaml
workflow_id: hackathon-workshop
title: Hackathon Workshop
version: v1-open
mode: open
learning_mode: recognition
scoring_enabled: true
verification:
  python_project_path: ../../mcp
exercise_refs:
  - exercises/ex-001-evidence-routing/exercise.yaml
  - exercises/ex-004-explain-why/exercise.yaml
```

### Manifest Fields

- `workflow_id`
  Stable workshop identity.
- `title`
  Participant-visible workshop title.
- `version`
  Used for workflow versioning and mismatch detection in participant progress.
- `mode`
  Currently `open` or `challenge`.
- `learning_mode`
  Currently expected to be `recognition`.
- `scoring_enabled`
  Enables scoring for the workshop.
- `verification.python_project_path`
  Points from the Java manifest location to the Python project being used by the exercises.
- `exercise_refs`
  Ordered list of child exercise YAML files.

### Important Manifest Rules

- The position in `exercise_refs` controls exercise order.
- Parent manifests currently compose content; they do not override child exercise fields.
- A workflow cannot define both `stages:` and `exercise_refs:` at the same time.
- `workflow-open.yaml` and `workflow-challenge.yaml` can point at the same exercise library but use different versions, mode labels, or future subsets.

## Exercise YAML Format

Each exercise is a single stage in the current workshop model.

Example:

```yaml
id: ex-evidence-routing
title: Run It, Then Break It
description: Choose the routing fix that best addresses the first observed limitation.
unlock_after: []
points: 10
attempt_penalty: 2
allow_skip: true
completion_rule: manual
scaffold:
  files:
    - source: stage_0_note.txt
      target: .workshop/stage_0_note.txt
code_options:
  - id: opt_a
    label: Add evidence from raw transactions
    scaffold_dir: scaffolds/opt_a
    correct: true
    feedback: Correct. This option adds transaction-level evidence...
    snippets:
      - label: prompt/router.py
        path: diffs/opt_a_router.diff
      - label: prompt/evidence.py
        path: diffs/opt_a_evidence.diff
confirmation:
  trigger_function: placeholder
  output_file: .workshop/stage_0_complete.json
pre_exercise_check:
  title: Inspect The Baseline Behavior
  instructions: Run the Python app or playground before you choose any option...
  expected_behavior: You should see that the flow leans on stale summaries...
post_apply_guidance: Run the Python app or playground now...
observation_check:
  required: false
  questions:
    - id: obs_stage0_1
      prompt: What changed after you ran the updated Python flow?
      correct_option_id: a
      explanation: The updated route now pulls in transaction-level evidence...
      options:
        - id: a
          label: The output now includes transaction evidence...
        - id: b
          label: Only the formatting changed...
```

## Exercise Field Reference

### Core identity and sequencing

- `id`
  Stable exercise identifier. Must be unique across the workshop.
- `title`
  Short participant-visible exercise title.
- `description`
  Required participant-visible brief shown near the top of the exercise card.
- `unlock_after`
  List of prerequisite exercise ids. Empty list means this is a root exercise.

### Scoring and progression

- `points`
  Max points available for the exercise.
- `attempt_penalty`
  Deduction per wrong submitted option.
- `allow_skip`
  Whether the participant may skip the exercise.
- `completion_rule`
  Current samples use `manual`.

Supported completion rules in code:

- `manual`
- `file_contains`
- `script_exit_code`
- `eval_case_passes`
- `facilitator_approval`

### Scaffold

The `scaffold.files` block defines files copied into the participant workspace when the stage unlocks.

Example:

```yaml
scaffold:
  files:
    - source: stage_0_note.txt
      target: .workshop/stage_0_note.txt
```

Important behavior:

- The source file is looked up in the exercise's `scaffolds/base/` folder.
- Each option-specific scaffold directory must also contain matching files with the same names.
- When the correct option is applied, the engine copies the selected option's scaffold files into the participant workspace.

## Recognition Options

`code_options` are the core of the recognition exercise flow.

Each option includes:

- `id`
  Stable option id such as `opt_a`.
- `label`
  Participant-visible answer label.
- `scaffold_dir`
  Option-specific scaffold directory, typically `scaffolds/opt_a`.
- `correct`
  Exactly one option must be `true`.
- `feedback`
  Explanation shown after the participant submits that option.
- `snippets`
  One or more code or diff snippets shown in the UI for comparison.

### Recognition Flow in the UI

The intended participant sequence is:

1. Read the exercise brief.
2. If present, run the `pre_exercise_check`.
3. Review the option snippets.
4. Choose an option locally.
5. Press `Submit Selection` to score the choice.
6. Read the feedback.
7. Once the correct answer is confirmed, press `Apply`.
8. Run the Python app or playground again using the applied scaffold.
9. Complete the optional or required `observation_check`.
10. Press `Finish`.

Important scoring behavior:

- Only `Submit Selection` affects scoring.
- Re-submitting the same wrong option does not deduct points twice.
- `Apply` is only available after the correct option has been submitted.
- `Finish` is only available after `Apply`.

## Pre-Exercise Check

`pre_exercise_check` is optional and is intended for “before vs after” exercises.

It is content-only. It does **not** currently persist state and does **not** gate progression. Its purpose is to tell the participant what to run before making a choice and what failure mode to observe.

Example:

```yaml
pre_exercise_check:
  title: Inspect The Baseline Behavior
  instructions: Run the Python app or playground before you choose any option.
  expected_behavior: You should see the static routing logic fail in this way.
```

Use it when the participant needs to observe the bad baseline first.

Do not use it when the exercise can be understood entirely from the snippets and description.

## Post-Apply Guidance

`post_apply_guidance` is optional guidance shown after the participant presses `Apply`.

Its purpose is to direct the participant to run the Python app or playground again and inspect the changed behavior.

Example:

```yaml
post_apply_guidance: Run the Python app again. Compare the output and look for the new evidence path before you finish.
```

This is the “after” side of the before/after flow.

## Observation Check

`observation_check` is optional and appears after the stage is in `APPLIED` state.

It is meant to confirm that the participant noticed the intended effect of the exercise.

Example:

```yaml
observation_check:
  required: false
  questions:
    - id: obs_stage0_1
      prompt: What changed after you ran the updated Python flow?
      correct_option_id: a
      explanation: The updated route now pulls in transaction-level evidence...
      options:
        - id: a
          label: The output now includes transaction evidence...
        - id: b
          label: Only the formatting changed...
```

### Observation Check Rules

- `required: true` means the participant must answer before `Finish`.
- `required: false` means the participant may answer or skip.
- Questions are currently single-answer multiple choice.
- Observation checks are intentionally simple. They are not currently used for branching or bonus scoring.

## Confirmation Block

Current recognition stages still define:

```yaml
confirmation:
  trigger_function: placeholder
  output_file: .workshop/stage_0_complete.json
```

This remains part of the content model even though the current participant flow is centered on selection, apply, run, observe, and finish.

Content authors should preserve this block unless the engine is deliberately refactored.

## Path Resolution Rules

Paths in child exercise YAMLs are authored relative to the exercise folder.

Examples:

- `scaffold_dir: scaffolds/opt_a`
- `path: diffs/opt_a.diff`

The Java loader resolves these to absolute paths internally, so downstream code can treat them uniformly.

This means content authors should write clean relative paths in YAML; they do not need to author absolute paths.

## Validation Rules Content Authors Must Respect

These are the practical rules that matter when authoring new exercises:

- Every exercise must have:
  - `id`
  - `title`
  - `description`
  - `completion_rule`
- Exercise ids must be unique.
- Exercise order comes from the manifest, not the child YAML.
- `unlock_after` ids must point at real exercises.
- Unlock dependencies must be acyclic.
- Recognition exercises must define:
  - `scaffold.files`
  - `code_options`
  - `confirmation.trigger_function`
  - `confirmation.output_file`
- Each recognition exercise must have exactly one correct option.
- Every option must include at least one snippet.
- All referenced scaffold and diff/snippet files must exist on disk.
- If `pre_exercise_check` is present with content, it should include both:
  - `instructions`
  - `expected_behavior`
- If `observation_check` is present:
  - each question id must be unique within the stage
  - each option id must be unique within the question
  - each question must have at least two options

## Open vs Challenge Mode

The same exercise library can be used in both modes.

Current manifests:

- `workflow-open.yaml`
- `workflow-challenge.yaml`

Current practical meaning:

- `open`
  More permissive workshop profile.
- `challenge`
  Gated progression through `unlock_after` chains.

The exercises themselves should usually be reusable across both modes. Differences between modes should come from:

- manifest selection
- exercise ordering
- versioning
- future curation decisions

## Authoring Guidance for New Exercises

When proposing new exercises, agents should stay within the current framework and optimize for participant learning.

### A strong exercise usually has:

- a clear failure mode that the participant can observe
- one correct intervention
- two or more plausible but wrong distractors
- feedback that teaches why each distractor is wrong
- a meaningful before/after contrast
- an observation check that reinforces the intended lesson

### Good exercise themes for this framework

This framework is especially well-suited to:

- prompt-routing mistakes
- stale summary vs fresh evidence conflicts
- missing retrieval/evidence wiring
- explanation quality mistakes
- weak tool-selection logic
- incorrect trust ordering between sources
- reasoning that looks polished but is grounded in the wrong inputs

### Less suitable exercise themes

This framework is less suited to exercises that require:

- long free-form coding from scratch
- deep branching scenarios
- multiple correct answers
- highly dynamic sandbox state tracking
- open-ended grading without a clear recognition pattern

## Suggested Prompt to Give Another Agent

If you want Claude or GPT to suggest new exercises, give them this document and ask them to produce proposals in this shape:

```text
For each proposed exercise, provide:
- exercise id
- title
- one-sentence learning objective
- participant description
- unlock_after suggestion
- pre_exercise_check
- 2-4 code options with one correct answer
- feedback for each option
- post_apply_guidance
- observation_check
- required scaffold assets
- required diff/snippet assets
- why this exercise fits the current recognition-mode workshop
```

## Current Reality Check

This document describes the framework as it exists now, not a future idealized architecture.

Important current realities:

- the system is built around recognition-mode exercises
- the exercise library is composed through `exercise_refs`
- content is YAML-driven
- manifests control ordering
- child exercises are self-contained
- before/after exercises are now supported through `pre_exercise_check` plus `post_apply_guidance`
- the content model should stay simple unless there is a strong reason to expand it
