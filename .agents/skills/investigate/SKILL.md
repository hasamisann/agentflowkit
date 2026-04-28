---
name: investigate
description: Explicit Codex workflow skill invoked as $investigate. Investigate one bug, capture root cause and reproduction, and stop for user approval.
---

This repository skill is designed for explicit Codex invocation as `$investigate`.

Read `AGENTS.md`, `.workflow/procedures/investigate.md`, `.workflow/procedures/review-loop.md`, `.workflow/project_context.md`, and `.workflow/templates/investigation_template.md`.

Before substantive work, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --interface codex-cli --phase investigate --arguments "<restate the current user request faithfully>"`.

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Then execute `.workflow/procedures/investigate.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --interface codex-cli --phase investigate`. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the investigation.
