# Workflow Agent Instructions

Read `.workflow/project_context.md` for repository-specific build, test, architecture, and convention details.

## Workflow Phases

- `specify-design`
- `plan-tasks`
- `implement`
- `investigate`
- `fix-tasks`

Invocation differs by agent interface:

- OpenCode commands: `/specify-design`, `/plan-tasks`, `/implement`, `/investigate`, `/fix-tasks`
- Claude Code skills: `/specify-design`, `/plan-tasks`, `/implement`, `/investigate`, `/fix-tasks`
- Codex skills: `$specify-design`, `$plan-tasks`, `$implement`, `$investigate`, `$fix-tasks`

Codex support is implemented as repository skills under `.agents/skills`; these are invoked with `$<skill-name>` or selected from Codex's skill picker, not as custom slash commands.

`specify-design` starts with `grill-me` inside the phase. `grill-me` is not a separate workflow phase.

Main flow: `INIT -> SPECIFY-DESIGN -> PLAN-TASKS -> IMPLEMENT`

Bug flow: `INVESTIGATE -> FIX-TASKS -> IMPLEMENT`

## Workflow Artifacts

Workflow artifacts are local-only and excluded via `.git/info/exclude`.

- `.spec/cycles/manifest.md`: cycle catalog
- `.spec/cycle_index.md`: active-cycle pointer used when a command omits the cycle path
- `.spec/cycles/<cycle>/CYCLE.md`: combined requirements and design for one cycle
- `.spec/cycles/<cycle>/tasks/*.md`: one atomic implementation task per file
- `.spec/cycles/<cycle>/tasks/dependencies.md`: wave graph and task status index
- `.spec/bugs/<bug-id>/INVESTIGATION.md`: finalized bug investigation
- `.spec/bugs/<bug-id>/tasks/*.md`: one atomic bug-fix task per file
- `.spec/bugs/<bug-id>/tasks/dependencies.md`: bug-fix wave graph and task status index

Statuses:

- Task: `PENDING`, `ACTIVE`, `DONE`
- Document: `DRAFT`, `FINALIZED`

`dependencies.md` must use one row per task with these columns: `Task ID`, `File`, `Wave`, `Depends On`, `Status`, `Notes`.

## Phase Gates

- `INIT -> SPECIFY-DESIGN`: git repository initialized, `.spec/cycles/manifest.md` exists, `.spec/cycle_index.md` exists
- `SPECIFY-DESIGN -> PLAN-TASKS`: `CYCLE.md` exists and is `FINALIZED`
- `PLAN-TASKS -> IMPLEMENT`: task files and `dependencies.md` exist; if CI is enabled in `CYCLE.md`, `.github/workflows/ci.yml` exists; `.workflow/project_context.md` contains no placeholder or example values
- `INVESTIGATE -> FIX-TASKS`: `INVESTIGATION.md` exists and is `FINALIZED`

## Mandatory Codex Review Loop

Every workflow artifact and every implementation task must complete this loop before it is treated as complete:

1. create or implement the artifact
2. initialize review state at the start of artifact creation for that workflow step; for `specify-design`, do this only immediately before the first `CYCLE.md` draft-side effect after `grill-me`
3. if the user provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize review state before the next workflow review
4. run one read-only `codex exec` review round
5. validate findings before applying them
6. fix valid `CRITICAL` and `MAJOR` findings
7. optionally fix valid `MIDDLE` and `MINOR` findings
8. if a blocking finding appears incorrect or ambiguous, ask the user before changing the artifact
9. repeat until there are no blocking findings or the target reaches the maximum review turn count

Applies to `CYCLE.md`, `manifest.md`, `cycle_index.md`, `INVESTIGATION.md`, `.workflow/project_context.md`, `.github/workflows/ci.yml`, each task file, each `dependencies.md`, and each implementation task's code changes.

Review invariants:

- use the review settings defined in `.workflow/config/codex-review.toml`
- keep the review read-only
- write logs under `logs/reviews/`
- reuse one canonical review log file per command invocation and overwrite it on each review iteration
- reviewer-specific raw logs may be written alongside the canonical log as transient diagnostics
- never finalize a document, mark a task `DONE`, or create a reviewed implementation commit while blocking findings remain
- during review, treat the phase-defined in-progress status as correct (`DRAFT`, `PENDING`, or `ACTIVE` as applicable); do not block only because a later status transition has not happened yet
- for implementation reviews, include the full task file contents and verify tests, implementation, refactor, verify commands, and done condition against that task
- one review round launches the configured parallel reviewers with reviewer-specific prompts derived from the same target artifact and shared references, then merges their results into the canonical review result
- every reviewer in a round performs a docs-first review before the normal review; the provided documents are the source of truth and reviewers must not emit findings that contradict them
- for `plan-tasks` document reviews, include the active cycle `CYCLE.md` as a required reference
- for implementation reviews, treat the task file as the source of truth for task-specific requirements
- if an implementation review conflicts with the task file, the task file wins
- default severity intent: `CRITICAL` = must fix before completion, `MAJOR` = rule/spec violation or release-inappropriate, `MIDDLE` = non-blocking but undesirable, `MINOR` = non-blocking and light
- default review settings are `parallel_reviews = 3`, `max_review_turns = 10`, and `blocking_severities = ["critical", "major"]`

Use `.workflow/procedures/review-loop.md` and `.workflow/scripts/review_driver.py` for the concrete command shapes.

## User Confirmation Rule

Stop for explicit user approval when presenting:

- `CYCLE.md`
- CI configuration
- task breakdown
- investigation report
- any draft that is ready to finalize

## Implementation Rules

Per task, follow this order:

1. Red: write the failing test described in the task file
2. Green: implement the minimum change to pass
3. Refactor: clean up while keeping tests green
4. Verify: run every command in `<verify>`
5. Review Loop: run the mandatory Codex review loop and resolve valid blocking findings
6. Verify Again: rerun relevant verification after review-driven edits
7. Mark the task `DONE` and keep the matching `dependencies.md` row status synchronized

Rules:

- a wave run may execute multiple tasks sequentially, but still one task must complete its full lifecycle before the next task starts
- never stage `.spec/`, `.workflow/`, `.opencode/`, `.claude/`, `.agents/`, `AGENTS.md`, or `CLAUDE.md` unless the user explicitly asks
- do not push
- keep the task file status and the matching `dependencies.md` row status synchronized

## Bug Flow Rules

Bug investigations must capture local reproduction, exact failing output or logs, root cause, impact scope, regression strategy, target branch, and planned fix branch.

Fix task planning must:

- split work into atomic tasks
- prefer the order: regression test, root-cause fix, hardening or cleanup

## Commit Conventions

- when the user explicitly asks for a commit, use Conventional Commits
- allowed types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `style`
- commit granularity is user-directed and does not need to match task boundaries

## File Reading Discipline

- when reading any file under `.spec/`, read the entire file
- do not use git-based discovery for `.spec/`, `.workflow/`, `.opencode/`, `.claude/`, `.agents/`, `AGENTS.md`, or `CLAUDE.md`
- use filesystem reads and filesystem search instead

## Directory Convention

```text
.spec/
├── cycle_index.md
├── cycles/
│   ├── manifest.md
│   └── <cycle>/
│       ├── CYCLE.md
│       └── tasks/
│           ├── dependencies.md
│           └── *.md
└── bugs/
    └── <bug-id>/
        ├── INVESTIGATION.md
        └── tasks/
            ├── dependencies.md
            └── *.md
```

Shared local workflow files live under `.workflow/`, `.opencode/`, `.claude/`, `.agents/`, `AGENTS.md`, and `CLAUDE.md`.

## Branch Strategy

- use the repository default branch as the integration branch
- `feat/<name>`: cycle branch created during `specify-design`
- `fix/<name>`: bug-fix branch created during `investigate`

Cycle completion: finish all task files, merge the feature branch into the default branch, then update `.spec/cycle_index.md` to `DONE` or replace it with the next active cycle.

Bug completion: finish all bug task files, merge the fix branch into the target branch recorded in `INVESTIGATION.md`, and keep the investigation and task files as the local audit trail.
