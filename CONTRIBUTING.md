# Contributing to Claude Code Configuration

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a new branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run validation: `./scripts/validate.sh` (if available)
5. Commit your changes: `git commit -am 'Add new feature'`
6. Push to the branch: `git push origin feature/my-feature`
7. Submit a pull request

## Project Structure

```
install.sh        # Repository-level installer entrypoint
claudecfg/
├── agents/         # Agent definitions (*.md)
├── commands/       # Slash command documentation
├── skills/         # Skill definitions (commands that invoke agents)
├── workflows/      # Workflow definitions
├── settings.json   # Main configuration
├── GUIDE.md        # User guide
└── install.sh      # Compatibility wrapper to ../install.sh
```

## Adding a New Agent

1. Create `claudecfg/agents/[alias].md`
2. Use the template:

```yaml
---
name: AgentName
alias: short
description: Brief description
type: AgentType
---

**You are Persona.** Description...

## Personality
...

## Standard Output
...
```

3. Update `claudecfg/agents/m.md` to include new agent
4. Update README.md agent table
5. Update GUIDE.md subagents section

## Adding a New Command

1. Create `claudecfg/commands/[command].md`
2. If it invokes an agent, also create `claudecfg/skills/[command].md`
3. Update CLAUDE.md commands list

## Code Style

- Keep agent files under 150 lines
- Use consistent formatting in output templates
- Include catchphrases that match personality
- Always fill all fields in Standard Output template

## Testing

Before submitting:
- [ ] JSON files are valid
- [ ] Agent markdown has proper frontmatter
- [ ] All links in documentation work

## Questions?

Open an issue or ask in discussions.
