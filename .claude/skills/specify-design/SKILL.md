---
name: specify-design
description: Create one combined cycle document and stop for user approval.
argument-hint: [feature summary]
disable-model-invocation: true
hooks:
  Stop:
    - hooks:
        - type: command
          command: python "$CLAUDE_PROJECT_DIR/.workflow/scripts/review_driver.py" finish --tool claude --phase specify-design --hook-event Stop
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool claude --phase specify-design --session-id "${CLAUDE_SESSION_ID}" --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review. Do not rerun `prepare` for approval-only finalization after the user simply approves the draft.

Read `CLAUDE.md`, `.workflow/procedures/specify-design.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/cycle_template.md`, `.workflow/templates/manifest_template.md`, and `.workflow/templates/cycle_index_template.md`.

Then execute `.workflow/procedures/specify-design.md` exactly.

Use the existing Stop hook `finish` pass for both stages: first to complete the DRAFT content review loop, then after explicit user approval to validate the status-only finalization without rerunning `prepare`.

User arguments: $ARGUMENTS
