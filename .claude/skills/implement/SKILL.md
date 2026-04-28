---
name: implement
description: Implement one task or one requested wave.
argument-hint: <task-file> | wave <N> | bug <bug-id> wave <N>
disable-model-invocation: true
---

Review state setup:
!`python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" prepare --interface claude --phase implement --session-id "${CLAUDE_SESSION_ID}" --arguments "$ARGUMENTS"`

If the latest user input supplies manual review feedback, asks for re-review, or explicitly asks to reset review rounds, run the same `prepare` command again before the next workflow review.

Read `CLAUDE.md`, `.workflow/procedures/implement.md`, `.workflow/procedures/review-loop.md`, the resolved task file, and the relevant `dependencies.md` file when the input targets a wave.

Then execute `.workflow/procedures/implement.md` exactly.

For every resolved task file, after Verify and before marking the task `DONE`, run:

```bash
python "$(git rev-parse --show-toplevel)/.workflow/scripts/review_driver.py" review-task --interface claude --session-id "${CLAUDE_SESSION_ID}" --task-file "<resolved-task-file>"
```

Resolve every valid blocking finding (`CRITICAL` or `MAJOR`), optionally apply valid advisory findings (`MIDDLE` or `MINOR`), and if a blocking finding appears incorrect or ambiguous, ask the user before changing the task. Do not mark the task `DONE` until that review passes.

User arguments: $ARGUMENTS
