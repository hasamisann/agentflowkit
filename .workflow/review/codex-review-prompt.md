# `codex exec` Review Prompt Template

Use this as a prompt shape when calling `codex exec` for workflow review-gate runs.

## Document Review Shape

```text
Review the <artifact-type> at <artifact-path>.

Phase: <phase-name>
Current review stage: <stage-name>
Current review round: <X>/<stage-limit-or-unlimited>

Acceptance requirements:
- <requirement 1>
- <requirement 2>

Severity definitions:
- critical: must be fixed before completion.
- major: violates a workflow/spec/task rule or is inappropriate for release quality.
- middle: acceptable for release, but meaningfully undesirable.
- minor: acceptable for release and only lightly undesirable.

Rules:
- Stay read-only.
- Return only concrete, evidence-backed findings.
- Use the supplied JSON schema.
- Set approved to true only when there are no critical or major findings.
- Judge status transitions against the documented workflow phase, not against perceived content completeness.
- Do not require a terminal or later-phase status before the workflow explicitly allows that transition.
- If you are unsure whether something is major or middle, choose middle.
- Do not report speculation, stylistic preferences, or generic alternative ideas as findings.
- For every critical or major finding, explain the concrete violated rule, evidence, or release risk.
```

## Implementation Review Shape

```text
Review the implementation for task file <task-file-path>.

Phase: implement
Artifact type: implementation-task
Artifact path: <task-file-path>
Current review stage: <stage-name>
Current review round: <X>/<stage-limit-or-unlimited>

Acceptance requirements:
- The implementation follows the task file exactly.
- Tests, implementation, refactor, verify commands, and done condition comply with the task file.

Severity definitions:
- critical: must be fixed before completion.
- major: violates a workflow/spec/task rule or is inappropriate for release quality.
- middle: acceptable for release, but meaningfully undesirable.
- minor: acceptable for release and only lightly undesirable.

Task file contents:
<<<TASK FILE START>>>
<full-task-file-contents>
<<<TASK FILE END>>>

Rules:
- Stay read-only.
- Return only concrete, evidence-backed findings.
- Use the supplied JSON schema.
- Set approved to true only when there are no critical or major findings.
- During `review-task`, the task is expected to remain `ACTIVE` until review passes and verification is rerun.
- Do not require `DONE` before the workflow reaches that transition point.
- If you are unsure whether something is major or middle, choose middle.
- Do not report speculation, stylistic preferences, or generic alternative ideas as findings.
- For every critical or major finding, explain the concrete violated rule, evidence, or release risk.
```
