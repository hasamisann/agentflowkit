---
name: fix-tasks
description: Break one finalized investigation into atomic fix tasks.
argument-hint: <investigation path or bug id>
disable-model-invocation: true
hooks:
  Stop:
    - hooks:
        - type: command
          command: python "$CLAUDE_PROJECT_DIR/.workflow/scripts/review_driver.py" finish --tool claude --phase fix-tasks --hook-event Stop
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool claude --phase fix-tasks --session-id "${CLAUDE_SESSION_ID}" --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Read `CLAUDE.md`, `.workflow/procedures/fix-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, and the resolved `INVESTIGATION.md`.

Then execute `.workflow/procedures/fix-tasks.md` exactly.

User arguments: $ARGUMENTS
