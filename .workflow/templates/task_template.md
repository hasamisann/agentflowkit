Status: `PENDING` | `ACTIVE` | `DONE`

# Task NNN: [Short Task Title]

```xml
<task id="NNN" kind="implementation|fix" wave="W">
  <name>Short Task Title</name>

  <depends>
    none
  </depends>

  <files>
    src/example.ts
    src/example.test.ts
  </files>

  <context>
    Reference `.spec/cycles/cNN-name/CYCLE.md` or the relevant bug investigation.
    Describe the exact slice this task owns and any constraints it must preserve.
  </context>

  <test>
    Define the failing test cases to add first.
    Be explicit about inputs, outputs, and edge cases.
  </test>

  <action>
    Describe the minimal implementation required to satisfy the tests.
  </action>

  <refactor>
    Describe the cleanup required once tests pass.
    Include warning cleanup and naming consistency if relevant.
  </refactor>

  <verify>
    npm test
  </verify>

  <done>
    State the observable completion condition for this task.
  </done>
</task>
```
