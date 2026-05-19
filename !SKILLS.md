# Skills & Commands Reference

> Quick reference for available Claude Code commands in this project.
> These are global skills available across all repos.

## Available Commands

| Command | What it does |
|---------|-------------|
| `/bootstrap` | Set up project context files (you already ran this!) |
| `/session-start` | Read context files, check git state, summarise where things stand |
| `/session-end` | Update context docs, commit changes, and push |
| `/audit` | Check if documentation matches the actual code |
| `/conventional-commit` | Create a well-formatted conventional commit |
| `/skill-scan` | Scan a GitHub repo and extract skills into Cortex |
| `/skill-search` | Search Cortex for skills relevant to current task |
| `/skill-add` | Manually capture current work as a Cortex skill |

## How It Works

- **Automatic**: Claude reads `AI_CONTEXT.md` and `memory.json` at the start of every conversation
- **On demand**: Use the commands above when you need them
- **Session memory**: `AI_CONTEXT.md` tracks what was done each session so context carries over

## Key Documentation

| File | Purpose |
|------|---------|
| `Documentation/AI_CONTEXT.md` | Living project brain — architecture, status, session history |
| `Documentation/TOOLBOX.md` | Module and service inventory |
| `.github/memory.json` | Machine-readable project memory |
