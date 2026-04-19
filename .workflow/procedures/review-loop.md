# Codex Review Loop

Use this procedure whenever a workflow step creates one document or completes one implementation task.

## Goal

Do not treat an artifact as complete until the merged `codex exec` review reports no blocking findings.

## Required Loop

1. Create or implement the artifact.
2. At the start of each workflow invocation, initialize the review state for that phase.
3. If the user provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the review state before the next workflow review.
4. Run one read-only Codex review round for that artifact.
5. Validate the findings before applying them:
   - `CRITICAL`: must be fixed before completion.
   - `MAJOR`: violates workflow/spec/task requirements or is inappropriate for release quality.
   - `MIDDLE`: acceptable for release, but meaningfully undesirable.
   - `MINOR`: acceptable for release and only lightly undesirable.
6. Fix valid `CRITICAL` and `MAJOR` findings.
7. Optionally fix valid `MIDDLE` and `MINOR` findings.
8. If a blocking finding appears incorrect or ambiguous, stop and ask the user before changing the artifact.
9. Repeat until the merged review result contains no blocking findings or the target reaches the maximum review turn count.
10. If the review turn limit is reached, stop and report the remaining blocking findings instead of continuing to loop.

One review round means the driver launches the configured parallel reviewers with the same prompt, each reviewer performs a docs-first review followed by the normal review, and the driver then merges their results into one canonical review result.
The provided documents are the source of truth for the round. Reviewers must not emit findings or suggested fixes that conflict with those documents. If the provided documents conflict with each other, reviewers must report that document conflict instead of inventing a resolution.

## Required Codex Settings

- all review settings come from `.workflow/config/codex-review.toml`
- change review settings only in `.workflow/config/codex-review.toml`; that file is the single source of truth for model, sandbox, reasoning effort, output schema, prompt transport, document review mode, parallelism, blocking severities, and maximum review turns
- write one canonical review log per command invocation under `logs/reviews/`
- overwrite that same canonical review log on each review round during the command invocation
- reviewer-specific raw logs may be written alongside the canonical log as transient diagnostics
- default settings are `parallel_reviews = 3`, `max_review_turns = 10`, and `blocking_severities = ["critical", "major"]`

## Helper Script

Use `.workflow/scripts/review_driver.py` instead of hand-assembling review commands.
Do not invoke `codex exec` directly for workflow reviews.
The driver streams prompts over stdin, inlines document contents for document-phase reviews, fans each review round out to the configured parallel reviewer count, merges the results, and records diagnostics under `logs/reviews/`.

### Prepare a document-phase review

Run this at the start of a command invocation so the review log path, target scope, and review-round counters are reset:

```bash
python ".workflow/scripts/review_driver.py" prepare --tool opencode --phase plan-tasks --arguments "$ARGUMENTS"
```

For Claude skills, pass `${CLAUDE_SESSION_ID}` so each skill invocation gets its own state file.
Re-run the same `prepare` command before the next workflow review whenever the user supplies manual review feedback or explicitly asks to reset the review rounds.

### Finish a document-phase review

Run this at the end of `specify-design`, `plan-tasks`, `investigate`, or `fix-tasks`:

```bash
python ".workflow/scripts/review_driver.py" finish --tool opencode --phase plan-tasks
```

If the script exits non-zero, apply the findings and run it again.
Only blocking findings (`CRITICAL` or `MAJOR`) are required for the loop to continue.

For `specify-design` and `investigate`, a successful draft review keeps approval state so the next `finish` call can validate the approval-only status transition. That follow-up pass is not another `codex exec` content review round. It only allows the documented status-only finalization change and rejects any additional content edits until `prepare` resets the review state.

### Review one implementation task

Run this at the start of an implementation invocation so the task review-round counters are reset:

```bash
python ".workflow/scripts/review_driver.py" prepare --tool opencode --phase implement --arguments "$ARGUMENTS"
```

Then run this after Verify and before Commit for each task file:

```bash
python ".workflow/scripts/review_driver.py" review-task --tool opencode --task-file ".spec/cycles/c01-example/tasks/impl-001-example.md"
```

This implementation review injects the full task file contents into the `codex exec` prompt, treats that task file as the source of truth for task-specific requirements, and always treats the task file as authoritative if a normal review instinct would conflict with it. The driver streams the prompt over stdin and requires Codex to verify the current code changes, tests, refactor, verification commands, and done condition against that task. Re-run `prepare --phase implement` before the next workflow review whenever the user supplies manual review feedback or explicitly asks to reset the review rounds.

## Scope Rules

- Review exactly one target artifact at a time.
- One target review round may use multiple parallel reviewers, but it still produces one merged canonical result.
- For document phases, reuse the same review log path for the full command invocation and track review rounds per artifact file.
- For document phases, do not rely on Codex to read the artifact from disk; the driver must inline the artifact contents into the prompt.
- For `plan-tasks` document reviews, inline the active cycle `CYCLE.md` and treat it as a required reference before review starts.
- For implementation tasks, run one review per task before its commit and track review rounds per task file.
- For implementation reviews, inline the full task file and treat it as the source of truth for task-specific requirements.
- If an implementation review conflicts with the task file, treat the task file as authoritative and resolve the conflict in favor of the task.
- Treat `approved: true` and an empty `findings` array as the only success condition; `advisory_findings` may remain.
