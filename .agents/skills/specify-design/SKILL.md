---
name: specify-design
description: Grill the plan, then create one combined cycle document and stop for user approval. Use when the user wants to start a new cycle or define a new feature.
---

Read `AGENTS.md`, `.workflow/procedures/specify-design.md`, `.workflow/procedures/review-loop.md`, `.workflow/templates/cycle_template.md`, `.workflow/templates/manifest_template.md`, and `.workflow/templates/cycle_index_template.md`.

Do not run `prepare` at skill start. Start with the `grill-me` phase in `.workflow/procedures/specify-design.md`.

Only when the user explicitly asks to start drafting `CYCLE.md`, and immediately before the first draft-side effect, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --tool codex --phase specify-design --arguments "<restate the current user request faithfully>"`.

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds after drafting has started, run the same `prepare` command again before the next workflow review.

Then execute `.workflow/procedures/specify-design.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --tool codex --phase specify-design`. During grill-me-only turns this safely no-ops because no review state exists yet. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the draft.
