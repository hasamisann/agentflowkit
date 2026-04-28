---
description: "Investigate one bug and stop for approval"
argument-hint: "[bug summary]"
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --interface opencode --phase investigate --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review. Do not rerun `prepare` for approval-only finalization after the user simply approves the draft.

Read `AGENTS.md`, `.workflow/procedures/investigate.md`, `.workflow/procedures/review-loop.md`, `.workflow/project_context.md`, and `.workflow/templates/investigation_template.md`.

Then execute `.workflow/procedures/investigate.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --interface opencode --phase investigate`. On the draft pass, resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the investigation. Treat the provided workflow documents and the investigation draft as authoritative if a `codex exec` review conflicts with them. After explicit user approval, run the same `finish` command again without rerunning `prepare`; the driver will accept only the status-only finalization change and will reject any additional content edits until the review state is reset.

User arguments: `$ARGUMENTS`
