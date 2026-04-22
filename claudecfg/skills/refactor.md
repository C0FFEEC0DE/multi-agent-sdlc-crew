---
name: refactor
description: Run the housekeeper in an isolated subagent for bounded refactors and cleanup with verification awareness.
agent: Veles
context: fork
disable-model-invocation: true
allowed-tools:
  - Read
  - Glob
  - Grep
  - Edit
  - Write
  - Bash(git status:*)
  - Bash(git diff:*)
paths:
  - "**/*.py"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.sh"
---

# /refactor

Run refactoring session with the Veles agent.

## When to use
- Code duplication
- Functions too long (>50 lines)
- Bad variable names
- Tests became fragile
- Technical debt cleanup

## Usage
```
/refactor [what to refactor]
```

## Examples
```
/refactor the auth module
/refactor extract common logic from services
/refactor rename variables in user controller
```

## Agent
Invokes @housekeeper (Veles) who will:
1. Identify refactoring targets
2. Propose cleanup and safety checkpoints
3. Ensure verification still passes
4. Leave code cleaner than found
5. Report what was changed

## Constraints
- **Never ask the user for confirmation.** Proceed directly with bounded refactoring changes.
- Keep changes focused and limited in scope.
- Do not perform release or deploy work.
