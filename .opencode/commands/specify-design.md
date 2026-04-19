---
description: "Create one combined cycle document and stop for approval"
argument-hint: "[feature summary]"
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool opencode --phase specify-design --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review. Do not rerun `prepare` for approval-only finalization after the user simply approves the draft.

Read `AGENTS.md`, `.workflow/procedures/specify-design.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/cycle_template.md`, `.workflow/templates/manifest_template.md`, and `.workflow/templates/cycle_index_template.md`.

Then execute `.workflow/procedures/specify-design.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --tool opencode --phase specify-design`. On the draft pass, resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the draft. Treat the provided workflow documents and the draft itself as authoritative if a `codex exec` review conflicts with them. After explicit user approval, run the same `finish` command again without rerunning `prepare`; the driver will accept only the status-only finalization change and will reject any additional content edits until the review state is reset.

User arguments: `$ARGUMENTS`
