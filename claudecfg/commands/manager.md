# /manager

**This command invokes @manager agent.**

Run a coordination and planning session with the Manager agent.

## When to use
- Multi-step task
- Need to break work into roles
- Unsure about execution order
- Want a concrete implementation plan before touching code

## Usage
```text
/manager [goal or task]
```

## Agent Actions
The @manager agent will:
1. Clarify the goal and constraints
2. Break the work into concrete steps
3. Suggest which specialist agents should handle each part
4. Identify verification and review checkpoints
5. Return an execution-ready plan

## Important
- Use this for coordination, not for final implementation
- Prefer concrete next steps over vague strategy
- Call out blockers and assumptions explicitly
