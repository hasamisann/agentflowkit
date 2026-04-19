---
name: fix-tasks
description: Break one finalized investigation into atomic fix tasks. Use when the user wants a bug-fix task breakdown.
---

Read `AGENTS.md`, `.workflow/procedures/fix-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, and the resolved `INVESTIGATION.md`.

Before substantive work, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool codex --phase fix-tasks --arguments "<restate the current user request faithfully>"`.

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Then execute `.workflow/procedures/fix-tasks.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --tool codex --phase fix-tasks`. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the task breakdown.
