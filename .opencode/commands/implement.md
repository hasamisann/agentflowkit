---
description: "Implement one task or one requested wave"
argument-hint: "<task-file> | wave <N> | bug <bug-id> wave <N>"
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool opencode --phase implement --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Read `AGENTS.md`, `.workflow/procedures/implement.md`, `.workflow/procedures/review-loop.md`, the resolved task file, and the relevant `dependencies.md` file when the input targets a wave.

Then execute `.workflow/procedures/implement.md` exactly.

For every resolved task file, after Verify and before marking the task `DONE`, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" review-task --tool opencode --task-file "<resolved-task-file>"`. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the task. If a `codex exec` review conflicts with the task file, always treat the task file as correct.

User arguments: `$ARGUMENTS`
