---
name: plan-tasks
description: Break one finalized cycle document into atomic implementation tasks.
argument-hint: [cycle path or active cycle]
disable-model-invocation: true
hooks:
  Stop:
    - hooks:
        - type: command
          command: python "$CLAUDE_PROJECT_DIR/.workflow/scripts/review_driver.py" finish --tool claude --phase plan-tasks --hook-event Stop
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool claude --phase plan-tasks --session-id "${CLAUDE_SESSION_ID}" --arguments "$ARGUMENTS"`

Do not rerun `prepare` after you fix your own review findings. In the same invocation, reuse the existing review state and let the existing Stop hook rerun `finish`.

Rerun `prepare` only if the latest user input supplies manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds.

If review output unexpectedly returns to `round 1/<N>` after a prior round in the same invocation, stop and verify whether the review state was reset before continuing.

Read `CLAUDE.md`, `.workflow/procedures/plan-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/project_context.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, `.workflow/templates/github-actions/ci.yml`, and the resolved `CYCLE.md`.

Then execute `.workflow/procedures/plan-tasks.md` exactly.

Use the existing Stop hook `finish` pass for repeated self-fix review rounds. Do not call `prepare` again unless one of the reset conditions applies.

User arguments: $ARGUMENTS
