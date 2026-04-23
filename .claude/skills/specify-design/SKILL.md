---
name: specify-design
description: Grill the plan, then create one combined cycle document and stop for user approval.
argument-hint: [feature summary]
disable-model-invocation: true
hooks:
  Stop:
    - hooks:
        - type: command
          command: python "$CLAUDE_PROJECT_DIR/.workflow/scripts/review_driver.py" finish --tool claude --phase specify-design --hook-event Stop
---

Review state setup:
Do not run `prepare` at skill start. Start with the `grill-me` phase in `.workflow/procedures/specify-design.md`.

Only when the user explicitly asks to start drafting `CYCLE.md`, and immediately before the first draft-side effect, run:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool claude --phase specify-design --session-id "${CLAUDE_SESSION_ID}" --arguments "$ARGUMENTS"`

Do not rerun `prepare` after you fix your own review findings. In the same invocation, reuse the existing review state and let the existing Stop hook rerun `finish`.

Rerun `prepare` only if the latest user input supplies manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds after drafting has started.

Do not rerun `prepare` for approval-only finalization after the user simply approves the draft.

If review output unexpectedly returns to `round 1/<N>` after a prior round in the same invocation, stop and verify whether the review state was reset before continuing.

Read `CLAUDE.md`, `.workflow/procedures/specify-design.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/cycle_template.md`, `.workflow/templates/manifest_template.md`, and `.workflow/templates/cycle_index_template.md`.

Then execute `.workflow/procedures/specify-design.md` exactly.

Use the existing Stop hook `finish` pass for both stages: it safely no-ops during grill-me-only turns, handles repeated self-fix review rounds during drafting without rerunning `prepare`, then after explicit user approval validates the status-only finalization without rerunning `prepare`.

User arguments: $ARGUMENTS
