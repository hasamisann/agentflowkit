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

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Read `CLAUDE.md`, `.workflow/procedures/plan-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/project_context.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, `.workflow/templates/github-actions/ci.yml`, and the resolved `CYCLE.md`.

Then execute `.workflow/procedures/plan-tasks.md` exactly.

User arguments: $ARGUMENTS
