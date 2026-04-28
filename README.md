# Workflow Templates

Reusable workflow scaffolding for agent-assisted software projects.

This repository installs a local `.workflow`, `.spec`, and agent-interface setup into a target project. It supports OpenCode commands, Claude Code skills, and Codex CLI repository skills while sharing the same workflow artifacts and `codex exec` review gate.

## Install

From this repository, copy the workflow files into a target project:

```powershell
.\init-agents.ps1 -TargetDir C:\path\to\project
```

On POSIX shells:

```sh
./init-agents.sh --target-dir /path/to/project
```

Add `-InitGit` or `--init-git` when you want the initializer to create a git repository.

## Workflow Phases

- `specify-design`: define a cycle and produce `CYCLE.md`
- `plan-tasks`: split a finalized cycle into task files
- `implement`: execute one task or one dependency wave
- `investigate`: investigate one bug and stop for approval
- `fix-tasks`: split a finalized investigation into fix tasks

## Agent Invocation

OpenCode uses slash commands:

```text
/specify-design
/plan-tasks
/implement
/investigate
/fix-tasks
```

Claude Code uses the matching skills with slash invocation.

Codex CLI uses repository skills under `.agents/skills` and should be invoked explicitly with `$`:

```text
$specify-design
$plan-tasks
$implement
$investigate
$fix-tasks
```

Codex CLI support is separate from the review gate. The review gate is an internal workflow check that launches `codex exec` through `.workflow/scripts/review_driver.py`.

## Artifacts

Workflow state is local-only and excluded from git by default:

- `.spec/cycles/manifest.md`
- `.spec/cycle_index.md`
- `.spec/cycles/<cycle>/CYCLE.md`
- `.spec/cycles/<cycle>/tasks/*.md`
- `.spec/bugs/<bug-id>/INVESTIGATION.md`
- `.spec/bugs/<bug-id>/tasks/*.md`

## Review Gate

Workflow artifacts and implementation tasks use the mandatory `codex exec` review gate through `.workflow/scripts/review_driver.py`. Review settings live in `.workflow/config/codex-review.toml` and do not configure interactive Codex CLI sessions.
