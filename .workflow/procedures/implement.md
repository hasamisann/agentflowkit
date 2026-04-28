# Implement Procedure

Implement one task or every task in one requested wave.

## Accepted Inputs

- `/implement <task-file>`
- `/implement wave <N>` for the active cycle
- `/implement bug <bug-id> wave <N>` for bug-fix tasks

## Task Resolution

1. Resolve the target task path from the user input.
2. For cycle waves, use the active cycle's `dependencies.md`.
3. For bug waves, use `.spec/bugs/<bug-id>/tasks/dependencies.md`.
4. For wave execution, resolve every task in the requested wave whose status is not `DONE`, then process them sequentially.
5. Skip tasks already marked `Status: DONE`.
6. Never move to the next wave unless the user explicitly asks.
7. At the start of each implementation invocation, initialize the implement review state.
8. If the user later provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the implement review state before the next workflow review.

## Per-Task Execution Order

1. Read the task file in full.
2. Verify dependency tasks are `DONE` in both the dependency rows and the task files.
3. Change the task status to `ACTIVE`.
4. Change the matching `dependencies.md` row to `ACTIVE`.
5. Execute Red: write the failing test first.
6. Execute Green: implement the smallest passing change.
7. Execute Refactor: clean up while keeping tests green.
8. Execute Verify: run every command in `<verify>`.
9. Run `python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" review-task --interface <agent-interface> --task-file <task-file>` and include `--session-id <session-id>` when the host provides one.
10. Include the full task file contents in the implementation review prompt, treat the current user request as authoritative over the task file, treat that task file as authoritative over review suggestions, and require the `codex exec` reviewer to verify compliance with the task's `<test>`, `<action>`, `<refactor>`, `<verify>`, and `<done>` sections.
11. Validate review findings before applying them:
    - fix valid `CRITICAL` and `MAJOR` findings
    - optionally apply valid `MIDDLE` and `MINOR` findings
    - if a blocking finding appears incorrect or ambiguous, ask the user before changing the implementation
12. Repeat the `codex exec` review-gate loop until the task has no blocking findings in every configured stage or reaches a bounded stage's review turn limit. If a later stage reports a blocking finding, fix it and restart from the first stage with that task's review rounds reset.
13. Re-run the relevant verification after review-driven fixes.
14. Mark the task `DONE`.
15. Mark the matching `dependencies.md` row `DONE`.

## Rules

- A wave run is still one task at a time. Complete the full lifecycle for task A before task B.
- Do not commit workflow files unless the user explicitly asks.
- Do not push.
- If a verify command fails, fix it before review or marking the task `DONE`.
- A task may be marked `DONE` without creating a commit.
- If the user explicitly asks for a commit, create it only after the task has no blocking review findings.
- If a bounded review stage's turn limit is reached, stop and report the remaining blocking findings instead of continuing to loop.
- If one task in a wave fails, stop and report before attempting later tasks in the same wave.
- Review findings must not contradict the current user request, the task file, or the provided workflow documents; if those sources conflict, report the conflict explicitly.
- If a `codex exec` review conflicts with the task file, treat the task file as correct unless the current user request explicitly supersedes it, and do not change the implementation only to satisfy the conflicting review.
