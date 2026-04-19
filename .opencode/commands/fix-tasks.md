---
description: "Break one finalized investigation into fix tasks"
argument-hint: "<investigation path or bug id>"
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool opencode --phase fix-tasks --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Read `AGENTS.md`, `.workflow/procedures/fix-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, and the resolved `INVESTIGATION.md`.

Then execute `.workflow/procedures/fix-tasks.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --tool opencode --phase fix-tasks`. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the task plan. Treat the resolved `INVESTIGATION.md` and each generated task file as authoritative if a `codex exec` review conflicts with them.

User arguments: `$ARGUMENTS`
