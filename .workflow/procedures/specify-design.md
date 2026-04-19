# Specify-Design Procedure

Create one combined cycle document that captures both requirements and design.

## Inputs

- the feature or cycle goal from the user
- constraints, platforms, CI expectations, and non-goals

## Execution

1. Verify the repository is initialized with git.
2. Verify `.spec/cycles/manifest.md` and `.spec/cycle_index.md` exist.
3. Determine the next cycle ID by reading `.spec/cycles/manifest.md` and checking the actual filesystem contents of `.spec/cycles/`.
4. Ask for or infer a short cycle name only when the user has not provided one.
5. Determine the repository default branch and record it as the cycle base branch.
6. Create a feature branch named `feat/<short-name>` if it does not already exist.
7. Create `.spec/cycles/<cycle>/CYCLE.md` from `.workflow/templates/cycle_template.md`.
8. At the start of the invocation, initialize the specify-design review state.
9. If the user later provides manual review feedback, asks for re-review after a prior completion, or explicitly asks to reset review rounds, re-initialize the review state before the next workflow review.
10. The document must include:
   - problem statement
   - scope and out-of-scope
   - user stories and strict EARS acceptance criteria
   - constraints and non-functional requirements
   - architecture and data/interface design
   - implementation slices that will later become tasks
   - test strategy
   - CI requirements
11. Replace all placeholders and example values in `CYCLE.md` before presenting it.
12. Create or update `.spec/cycles/manifest.md` for the new cycle using `.workflow/templates/manifest_template.md` as the structure reference.
13. Create or update `.spec/cycle_index.md` so it points to the active cycle using `.workflow/templates/cycle_index_template.md` as the structure reference.
14. Run the mandatory Codex review loop on `CYCLE.md`.
15. If `manifest.md` was created or materially changed, run the mandatory Codex review loop on `manifest.md`.
16. If `cycle_index.md` was created or materially changed, run the mandatory Codex review loop on `cycle_index.md`.
17. Present the review-passed `CYCLE.md` draft to the user and stop for confirmation.
18. Only after explicit user approval, apply the status-only finalization step by setting `Status: FINALIZED` in `CYCLE.md` and the matching manifest row.
19. Treat that approval-only finalization as driver validation, not as another normal Codex review round.

## Rules

- Create one cycle document only; do not split requirements and design across separate files.
- `manifest.md` is the full cycle catalog. `cycle_index.md` is the current-cycle pointer used when the user omits a cycle path.
- Do not auto-finalize.
- Do not proceed to `/plan-tasks` while `CYCLE.md` is still draft.
- Do not leave placeholders, example values, or unresolved open questions presented as final decisions.
