---
name: docs
description: Run the docwriter in an isolated subagent for README, docs, and user-facing documentation changes.
agent: Docwriter
context: fork
disable-model-invocation: true
allowed-tools:
  - Read
  - Glob
  - Grep
  - Edit
  - Write
paths:
  - "**/*.md"
  - "docs/**"
  - "README*"
  - "CHANGELOG*"
---

# /docs

Run documentation session with the Docwriter agent.

## When to use
- Need to document feature/API
- README needs updating
- Code lacks documentation
- Architecture needs explaining

## Usage
```
/docs [what to document]
```

## Examples
```
/docs the auth API
/docs update README with new features
/docs document the payment flow
/docs create architecture diagram
```

## Agent
Invokes @docwriter (Wiki-Wiki) who will:
1. Identify documentation needs
2. Write README, API docs, or code docs
3. Add examples everywhere
4. Ensure docs are in sync with code
5. Report what was documented
