# Specify-Design Procedure

Create one combined cycle document that captures both requirements and design. Always start with `grill-me` and only draft `CYCLE.md` after the user explicitly asks for drafting.

## Inputs

- the feature or cycle goal from the user
- constraints, platforms, CI expectations, and non-goals
- an existing `DRAFT` `CYCLE.md` when revisiting an unfinished cycle

## Execution

1. Verify the repository is initialized with git.
2. Verify `.spec/cycles/manifest.md` and `.spec/cycle_index.md` exist.
3. If the user is revisiting an existing `DRAFT` `CYCLE.md`, resolve that draft first and treat it as the provisional source of truth for already settled decisions.
4. Start `grill-me` immediately. During `grill-me`:
   - ask exactly one question at a time
   - provide a recommended answer with each question
   - if a question can be answered by exploring the codebase, explore the codebase instead, briefly share the evidence, and continue to the next unresolved point without asking the user
   - walk the design tree depth-first, resolving dependency decisions before sibling branches
   - ask only about concrete unresolved points, ambiguities, contradictions, or downstream-impacting gaps; do not invent filler questions
   - if the user explicitly delegates or defers a decision, treat that as resolved only when the owner, timing, and guardrails are clear enough to constrain downstream work
   - if new information contradicts an earlier decision, explicitly reopen that decision and resolve the affected branch before continuing
   - if revisiting an existing `DRAFT`, grill only the changed or reopened branches instead of restarting the whole design
5. Do not determine a new cycle ID, create branches, create or update workflow artifacts, or initialize review state during `grill-me`.
6. If there are no concrete unresolved points left, stop asking questions and say: `現時点で詰めるべき論点は見当たりません。CYCLE.md の起草に進めるなら明示してください。`
7. Only when the user explicitly asks to start drafting `CYCLE.md`, determine whether any concrete unresolved point, contradiction, or downstream impact still blocks drafting.
8. If any such blocking point remains, do not draft. Present the specific issue and continue `grill-me` on that branch.
9. Immediately before the first draft-side effect, initialize the specify-design review state.
10. Determine the next cycle ID by reading `.spec/cycles/manifest.md` and checking the actual filesystem contents of `.spec/cycles/`, unless revisiting an in-scope `DRAFT` cycle.
11. Ask for or infer a short cycle name only when the user has not provided one and no in-scope `DRAFT` already establishes it.
12. Determine the repository default branch and record it as the cycle base branch.
13. Create a feature branch named `feat/<short-name>` if it does not already exist, unless revisiting an in-scope cycle branch.
14. Create or update `.spec/cycles/<cycle>/CYCLE.md` from `.workflow/templates/cycle_template.md`.
15. The document must include:
   - problem statement
   - scope and out-of-scope
   - user stories and strict EARS acceptance criteria
   - constraints and non-functional requirements
   - resolved decisions
   - architecture and data/interface design
   - implementation slices that will later become tasks
   - test strategy
   - CI requirements
16. In `Resolved Decisions`, record every non-trivial downstream-constraining decision, including explicit deferred or delegated decisions. Reflect those decisions again in the relevant sections rather than treating `Resolved Decisions` as the only source of truth.
17. Replace all placeholders and example values in `CYCLE.md` before presenting it.
18. Create or update `.spec/cycles/manifest.md` for the new cycle using `.workflow/templates/manifest_template.md` as the structure reference.
19. Create or update `.spec/cycle_index.md` so it points to the active cycle using `.workflow/templates/cycle_index_template.md` as the structure reference.
20. Run the mandatory Codex review loop on `CYCLE.md`.
21. If `manifest.md` was created or materially changed, run the mandatory Codex review loop on `manifest.md`.
22. If `cycle_index.md` was created or materially changed, run the mandatory Codex review loop on `cycle_index.md`.
23. Present the review-passed `CYCLE.md` draft to the user and stop for confirmation.
24. Only after explicit user approval, apply the status-only finalization step by setting `Status: FINALIZED` in `CYCLE.md` and the matching manifest row.
25. Treat that approval-only finalization as driver validation, not as another normal Codex review round.

## Rules

- Create one cycle document only; do not split requirements and design across separate files.
- The `specify-design` phase always starts with `grill-me`; do not skip directly to drafting unless the user's current message explicitly asks to start `CYCLE.md` drafting.
- `manifest.md` is the full cycle catalog. `cycle_index.md` is the current-cycle pointer used when the user omits a cycle path.
- Do not auto-finalize.
- Do not proceed to the `plan-tasks` phase while `CYCLE.md` is still draft.
- Do not leave placeholders, example values, or unresolved open questions presented as final decisions.
- Use `Resolved Decisions` as the index of non-trivial decisions, but keep the detailed requirements and design reflected in the relevant existing sections.
