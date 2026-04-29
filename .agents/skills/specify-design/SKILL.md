---
name: specify-design
description: Shared workflow skill. Grill the plan, then create one combined cycle document and stop for user approval when starting a new cycle or defining a new feature.
---

This repository skill is shared by Codex, Claude Code, and OpenCode. Codex invokes it as `$specify-design`; Claude reads it through `.claude/skills`; OpenCode slash commands delegate to it.

Read `AGENTS.md`, `.workflow/procedures/specify-design.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/cycle_template.md`, `.workflow/templates/manifest_template.md`, and `.workflow/templates/cycle_index_template.md`.

Do not run `prepare` at skill start. Start with the `grill-me` phase in `.workflow/procedures/specify-design.md`.

Only when the user explicitly asks to start drafting `CYCLE.md`, and immediately before the first draft-side effect, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --phase specify-design --arguments "<restate the current user request faithfully>"`.

Do not rerun `prepare` after you fix your own review findings. In the same invocation, reuse the existing review state and rerun `finish`.

Rerun `prepare` only if the latest user input supplies manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds after drafting has started.

Do not rerun `prepare` for approval-only finalization after the user simply approves the draft.

If review output unexpectedly returns to `round 1/<N>` after a prior round in the same invocation, stop and verify whether the review state was reset before continuing.

Then execute `.workflow/procedures/specify-design.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --phase specify-design`. During grill-me-only turns this safely no-ops because no review state exists yet. Use the same `finish` command for repeated self-fix review rounds within the same drafting invocation; do not rerun `prepare` unless one of the reset conditions applies. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the draft.
