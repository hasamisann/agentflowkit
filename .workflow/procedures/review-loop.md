# `codex exec` Review Gate

Use this procedure whenever a workflow step creates one document or completes one implementation task.

## Goal

Do not treat an artifact as complete until every configured `codex exec` review stage reports no blocking findings.

## Authority Order

When the current user request, spec/workflow documents, and review findings conflict, resolve them in this order:

1. Current explicit user instructions
2. Applicable spec and workflow documents
3. `codex exec` review gate findings

Review findings are required to drive changes only when they are valid under the higher-priority sources. If a review finding conflicts with the current user request or an applicable spec/workflow document, report the conflict, follow the higher-priority source, and ask the user when the higher-priority source is ambiguous.

## Required Loop

1. Create or implement the artifact.
2. At the start of artifact creation for that phase, initialize the review state for that phase.
3. If the user provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the review state before the next workflow review.
4. Run the first configured read-only `codex exec` review stage for that artifact.
5. Validate the findings before applying them:
   - `CRITICAL`: must be fixed before completion.
   - `MAJOR`: violates workflow/spec/task requirements or is inappropriate for release quality.
   - `MIDDLE`: acceptable for release, but meaningfully undesirable.
   - `MINOR`: acceptable for release and only lightly undesirable.
6. Fix valid `CRITICAL` and `MAJOR` findings.
7. Optionally fix valid `MIDDLE` and `MINOR` findings.
8. If a blocking finding appears incorrect or ambiguous, stop and ask the user before changing the artifact.
9. Repeat the first stage until its merged review result contains no blocking findings or the target reaches that stage's maximum review turn count.
10. After the first stage passes, run the next configured review stage.
11. If any later stage reports a blocking finding, fix it, reset that target's review rounds, and restart from the first stage.
12. Complete only after the final configured stage reports no blocking findings.
13. If any bounded review stage reaches its turn limit, stop and report the remaining blocking findings instead of continuing to loop.

One review stage round means the driver launches that stage's configured parallel reviewers with reviewer-specific prompts derived from the same target artifact and shared references, each reviewer performs an authority-order review followed by the normal review, and the driver then merges their results into one canonical review result.
The current user request is authoritative over the provided documents, and the provided documents are authoritative over review findings. Reviewers must not emit findings or suggested fixes that conflict with a higher-priority source. If higher-priority sources conflict with each other, reviewers must report that conflict instead of inventing a resolution.
During content review, the phase-defined in-progress status is the correct status for the artifact or task being reviewed. Reviewers must not emit blocking findings that only demand a later allowed status transition before the workflow reaches that transition point.

## Required Review-Gate Settings

- all review-gate settings come from `.workflow/config/codex-review.toml`
- change review-gate settings only in `.workflow/config/codex-review.toml`; that file is the single source of truth for the `codex exec` reviewer model, sandbox, reasoning effort, output schema, prompt transport, document review mode, review stages, stage parallelism, blocking severities, and stage turn limits
- `.workflow/config/codex-review.toml` does not configure human-facing interactive Codex CLI sessions
- write one canonical review log per command invocation under `logs/reviews/`
- overwrite that same canonical review log on each review round during the command invocation
- reviewer-specific raw logs may be written alongside the canonical log as transient diagnostics
- default settings are a `screening` stage with `baseline-high` and `edge-state-verify-high` reviewers for 10 rounds, followed by an unlimited `final-xhigh` stage with `baseline-xhigh`; blocking severities are `["critical", "major"]`

## Helper Script

Use `.workflow/scripts/review_driver.py` instead of hand-assembling review commands.
Do not invoke `codex exec` directly for workflow reviews.
The driver streams reviewer-specific prompts over stdin, inlines document contents for document-phase reviews, fans each review stage round out to that stage's configured reviewer count, applies each reviewer's configured reasoning effort and prompt lens, merges the results, and records diagnostics under `logs/reviews/`.

### Prepare a document-phase review

Run this at the start of artifact creation for the command invocation so the review log path, target scope, and review-round counters are reset:

```bash
python ".workflow/scripts/review_driver.py" prepare --phase plan-tasks --arguments "$ARGUMENTS"
```

For `specify-design`, artifact creation starts only when the workflow begins drafting `CYCLE.md` after `grill-me`, so do not run `prepare` during grill-me-only turns.
Re-run the same `prepare` command before the next workflow review whenever the user supplies manual review feedback or explicitly asks to reset the review rounds.

`prepare` initializes the review state for the current command invocation. In the same invocation, run `prepare` once and preserve that state across subsequent review rounds.

If you fix review findings yourself, do not rerun `prepare`. Reuse the existing review state and rerun `finish` for document phases.

Rerun `prepare` only when the user provides manual review feedback, explicitly asks for re-review after a prior completion, or explicitly asks to reset review rounds.

### Finish a document-phase review

Run this at the end of `specify-design`, `plan-tasks`, `investigate`, or `fix-tasks`:

```bash
python ".workflow/scripts/review_driver.py" finish --phase plan-tasks
```

If the script exits non-zero, apply the findings and run it again.
Only blocking findings (`CRITICAL` or `MAJOR`) are required for the loop to continue.

For `specify-design` and `investigate`, a successful draft review keeps approval state so the next `finish` call can validate the approval-only status transition. That follow-up pass is not another `codex exec` content review round. It only allows the documented status-only finalization change and rejects any additional content edits until `prepare` resets the review state.

For multi-artifact document phases such as `specify-design`, `plan-tasks`, and `fix-tasks`, `finish` may revisit the full in-scope artifact set on each pass. Preserve the same review state across self-fix iterations so unchanged previously approved artifacts can remain approved and be skipped on later rounds within the same invocation.

Correct sequence:
1. run `prepare` once
2. run `finish`
3. one artifact returns blocking findings
4. fix that artifact and any obviously related contract gaps in the same phase artifact set
5. run `finish` again without rerunning `prepare`

If a later pass in the same invocation unexpectedly returns to `round 1/<max_review_turns>` after a prior round already ran, stop and verify whether the review state was reset before continuing. A reset is expected after a later review stage reports a blocking finding.

### Review one implementation task

Run this at the start of an implementation invocation so the task review-round counters are reset:

```bash
python ".workflow/scripts/review_driver.py" prepare --phase implement --arguments "$ARGUMENTS"
```

Then run this after Verify and before marking the task `DONE` for each task file:

```bash
python ".workflow/scripts/review_driver.py" review-task --task-file ".spec/cycles/c01-example/tasks/impl-001-example.md"
```

This implementation review injects the full task file contents into the `codex exec` prompt, treats the current user request as authoritative over that task file, and treats that task file as authoritative over normal review instincts. The driver streams the prompt over stdin and requires the `codex exec` reviewer to verify the current code changes, tests, refactor, verification commands, and done condition against that task. Re-run `prepare --phase implement` before the next workflow review whenever the user supplies manual review feedback or explicitly asks to reset the review rounds.

## Scope Rules

- Review exactly one target artifact at a time.
- One target review stage round may use multiple parallel reviewers, but it still produces one merged canonical result.
- For document phases, reuse the same review log path for the full command invocation and track review rounds per artifact file.
- For document phases, do not rely on the `codex exec` reviewer to read the artifact from disk; the driver must inline the artifact contents into the prompt.
- For `plan-tasks` document reviews, inline the active cycle `CYCLE.md` and treat it as a required reference before review starts.
- For implementation tasks, run one review per task before its commit and track review rounds per task file.
- For implementation reviews, inline the full task file and treat it as the source of truth for task-specific requirements unless the current user request explicitly supersedes it.
- If an implementation review conflicts with the task file, treat the task file as authoritative and resolve the conflict in favor of the task unless the current user request explicitly supersedes it.
- Treat `approved: true` and an empty `findings` array as the only success condition; `advisory_findings` may remain.
