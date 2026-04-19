---
description: "Break one finalized cycle document into atomic tasks"
argument-hint: "[cycle path or active cycle]"
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool opencode --phase plan-tasks --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Read `AGENTS.md`, `.workflow/procedures/plan-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/project_context.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, `.workflow/templates/github-actions/ci.yml`, and the resolved `CYCLE.md`.

Then execute `.workflow/procedures/plan-tasks.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --tool opencode --phase plan-tasks`. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the task plan. Treat the active `CYCLE.md` and each generated task file as authoritative if a `codex exec` review conflicts with them.

User arguments: `$ARGUMENTS`
