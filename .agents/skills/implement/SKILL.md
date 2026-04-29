---
name: implement
description: Shared workflow skill. Implement one task or one requested wave from workflow task files.
---

This repository skill is shared by Codex, Claude Code, and OpenCode. Codex invokes it as `$implement`; Claude reads it through `.claude/skills`; OpenCode slash commands delegate to it.

Read `AGENTS.md`, `.workflow/procedures/implement.md`, `.workflow/procedures/review-loop.md`, the resolved task file, and the relevant `dependencies.md` file when the request targets a wave.

Before substantive work, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --phase implement --arguments "<restate the current user request faithfully>"`.

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Then execute `.workflow/procedures/implement.md` exactly.

For every resolved task file, after Verify and before marking the task `DONE`, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" review-task --task-file "<resolved-task-file>"`. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the task.

Use the current user request as the concrete target for this skill.
