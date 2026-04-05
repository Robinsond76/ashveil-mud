# Ashveil MUD — Copilot Instructions

<!-- SUPERPOWERS:START -->
## Superpowers

You have superpowers — a structured software development workflow system.

**Before starting any task**, check if a skill applies. If there is even a 1% chance a skill is relevant, read it.

### Loading Skills

To load a skill, use `read_file` on the SKILL.md file path below. Read the skill content and follow the workflow it describes.

#### Core Skill (read this first on any new task)

- **using-superpowers**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/using-superpowers/SKILL.md`

#### Available Skills

- **brainstorming**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/brainstorming/SKILL.md`
- **writing-plans**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/writing-plans/SKILL.md`
- **executing-plans**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/executing-plans/SKILL.md`
- **subagent-driven-development**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/subagent-driven-development/SKILL.md`
- **test-driven-development**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/test-driven-development/SKILL.md`
- **systematic-debugging**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/systematic-debugging/SKILL.md`
- **verification-before-completion**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/verification-before-completion/SKILL.md`
- **requesting-code-review**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/requesting-code-review/SKILL.md`
- **receiving-code-review**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/receiving-code-review/SKILL.md`
- **using-git-worktrees**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/using-git-worktrees/SKILL.md`
- **finishing-a-development-branch**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/finishing-a-development-branch/SKILL.md`
- **dispatching-parallel-agents**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/dispatching-parallel-agents/SKILL.md`
- **writing-skills**:
  `C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/writing-skills/SKILL.md`

#### Local Project Skills

- **mud-project** (project conventions, stack, commands, phase workflow):
  `.github/skills/mud-project/SKILL.md`

### Tool Mapping

Skills reference Claude Code tool names. Use these Copilot equivalents:

| Claude Code tool | Copilot equivalent |
|-----------------|-------------------|
| `Task` (dispatch subagent) | `runSubagent` |
| `TodoWrite` (task tracking) | `manage_todo_list` |
| `Skill` (invoke a skill) | `read_file` on the SKILL.md path |
| `Read` (read files) | `read_file` |
| `Write` (create files) | `create_file` |
| `Edit` (edit files) | `replace_string_in_file` or `multi_replace_string_in_file` |
| `Bash` (run commands) | `run_in_terminal` |

Full mapping:
`C:/Users/Robinson.DeSouza/.copilot/superpowers/skills/using-superpowers/references/copilot-tools.md`
<!-- SUPERPOWERS:END -->

---

## Project-Specific Context

Always also load the local project skill when working on this codebase:

`.github/skills/mud-project/SKILL.md`

This covers the Ashveil MUD stack, conventions, phase system, and where specs and plans live.
