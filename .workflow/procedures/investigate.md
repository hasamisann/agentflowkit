# Investigate Procedure

Investigate one bug and produce one finalized investigation document.

## Inputs

- observed behavior
- expected behavior
- reproduction steps
- environment details

## Execution

1. Capture the bug report details and expected behavior.
2. Reproduce the issue locally using commands from `.workflow/project_context.md` when available; otherwise determine the repository-native commands first.
3. Capture the exact failing output or logs.
4. Determine the next bug ID by checking the actual filesystem contents of `.spec/bugs/`.
5. Create a bug directory: `.spec/bugs/<bug-id>/`.
6. Determine the target branch for the fix.
7. Create a fix branch named `fix/<short-name>` when a dedicated fix branch does not already exist.
8. Create `.spec/bugs/<bug-id>/INVESTIGATION.md` from `.workflow/templates/investigation_template.md`.
9. At the start of the invocation, initialize the investigate review state.
10. If the user later provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the review state before the next workflow review.
11. Document:
   - reproduction
   - exact failure output
   - root cause
   - impact scope
   - regression strategy
   - recommended fix direction
   - target branch
   - planned fix branch
12. Replace all placeholders and example values in `INVESTIGATION.md` before presenting it.
13. Run the mandatory `codex exec` review gate on `INVESTIGATION.md`.
14. Present the review-passed investigation draft and stop for user confirmation.
15. Only after explicit approval, apply the status-only finalization step by setting `Status: FINALIZED`.
16. Treat that approval-only finalization as driver validation, not as another normal `codex exec` review round.

## Rules

- Do not jump to fix planning before the investigation is finalized.
- Prefer evidence from local reproduction over speculation.
- Do not leave unresolved placeholder text in a finalized investigation.
