# Fix-Tasks Procedure

Break one finalized bug investigation into atomic fix tasks.

## Inputs

- a finalized investigation file path or bug ID

## Execution

1. Resolve the bug directory and verify `INVESTIGATION.md` is `FINALIZED`.
2. Read the investigation in full.
3. Create `.spec/bugs/<bug-id>/tasks/` if it does not exist.
4. Determine the next fix task numbers by checking the actual filesystem contents.
5. Create atomic fix tasks using `.workflow/templates/task_template.md`.
6. At the start of the invocation, initialize the fix-tasks review state.
7. If the user later provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the review state before the next workflow review.
8. Prefer this order whenever applicable:
   - regression test task
   - root-cause fix task
   - hardening or cleanup task
9. Replace all placeholders and example values in every fix task file before presenting them.
10. Create `dependencies.md` from `.workflow/templates/dependencies_template.md`.
11. Add exactly one row per task file and assign wave, dependency list, and initial `PENDING` status.
12. Run the mandatory Codex review loop on each fix task file individually.
13. Run the mandatory Codex review loop on `dependencies.md`.
14. Present the fix task breakdown and stop for user confirmation.

## Rules

- Keep every fix task small enough for one TDD cycle and one commit.
- Every bug fix plan must include an explicit regression strategy.
- `dependencies.md` is the task execution index used by `/implement bug <bug-id> wave <N>` and must stay synchronized with task-file status.
