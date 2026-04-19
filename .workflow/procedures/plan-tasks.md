# Plan-Tasks Procedure

Break one finalized cycle document into atomic implementation tasks.

## Inputs

- the active cycle, identified from `.spec/cycle_index.md` or explicitly provided by the user

## Execution

1. Verify `.spec/cycles/<cycle>/CYCLE.md` exists and has `Status: FINALIZED`.
2. Fill in `.workflow/project_context.md` using the current repository and the cycle document.
3. Remove all placeholder blocks and example values from `.workflow/project_context.md` before finalizing it.
4. At the start of the invocation, initialize the plan-tasks review state.
5. If the user later provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the review state before the next workflow review.
6. Run the mandatory Codex review loop on `.workflow/project_context.md`, with the active cycle `CYCLE.md` included as a required reference and source of truth for cycle requirements.
7. If CI is enabled in `CYCLE.md`, create `.github/workflows/ci.yml` from `.workflow/templates/github-actions/ci.yml`.
8. Replace all CI template placeholders before treating `.github/workflows/ci.yml` as complete.
9. If CI is enabled, run the mandatory Codex review loop on `.github/workflows/ci.yml` before treating it as complete, again with the active cycle `CYCLE.md` included as a required reference.
10. Create `.spec/cycles/<cycle>/tasks/` if it does not exist.
11. Determine the next task numbers by checking the actual filesystem contents of that `tasks/` directory.
12. Create one task file per atomic unit using `.workflow/templates/task_template.md`.
13. Each task must be independently implementable, testable, and commit-ready.
14. Replace all placeholders and example values in every task file before presenting them.
15. Create `dependencies.md` from `.workflow/templates/dependencies_template.md`.
16. Add exactly one row per task file and assign wave, dependency list, and initial `PENDING` status.
17. Run the mandatory Codex review loop on each task file individually, always with the active cycle `CYCLE.md` included as a required reference.
18. Run the mandatory Codex review loop on `dependencies.md`, always with the active cycle `CYCLE.md` included as a required reference.
19. Present the task breakdown, wave graph, and CI file if any, then stop for user confirmation.

## Rules

- Keep tasks small enough for one TDD cycle and one atomic commit.
- Prefer clear dependency waves over vague ordering.
- If a task list is too large, split by architecture boundary rather than by file type alone.
- `dependencies.md` is the task execution index used by `/implement wave <N>` and must stay synchronized with task-file status.
- Review findings must not contradict the active cycle `CYCLE.md`; if documents conflict, report that conflict explicitly.
- If a review finding conflicts with a generated task file's stated requirements, treat the task file as authoritative instead of changing it only to satisfy the conflicting review.
