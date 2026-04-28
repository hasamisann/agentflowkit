---
name: plan-tasks
description: Explicit Codex workflow skill invoked as $plan-tasks. Break one finalized cycle document into atomic implementation tasks for the active or specified cycle.
---

This repository skill is designed for explicit Codex invocation as `$plan-tasks`.

Read `AGENTS.md`, `.workflow/procedures/plan-tasks.md`, `.workflow/procedures/review-loop.md`, `.workflow/project_context.md`, `.workflow/templates/task_template.md`, `.workflow/templates/dependencies_template.md`, `.workflow/templates/github-actions/ci.yml`, and the resolved `CYCLE.md`.

Before substantive work, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --interface codex-cli --phase plan-tasks --arguments "<restate the current user request faithfully>"`.

Do not rerun `prepare` after you fix your own review findings. In the same invocation, reuse the existing review state and rerun `finish`.

Rerun `prepare` only if the latest user input supplies manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds.

If review output unexpectedly returns to `round 1/<N>` after a prior round in the same invocation, stop and verify whether the review state was reset before continuing.

Then execute `.workflow/procedures/plan-tasks.md` exactly.

Before you stop, run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" finish --interface codex-cli --phase plan-tasks`. Use the same `finish` command for repeated self-fix review rounds within the same invocation; do not rerun `prepare` unless one of the reset conditions applies. Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the plan.
