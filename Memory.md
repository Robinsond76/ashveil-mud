# Ashveil MUD - Refactoring Memory

## Goal

Refactor the `game.py` god file (1,667 lines, 77 methods) into a clean, maintainable architecture using Python best practices. The goal is to decompose `GameSession` into state-specific handlers while maintaining all existing functionality.

## Instructions

- Use the brainstorming skill before implementing (already completed)
- Use the writing-plans skill to create implementation plans (already completed)
- Follow the implementation plan at `docs/superpowers/plans/2026-04-12-game-session-decomposition.md`
- Execute using subagent-driven-development skill (recommended) or executing-plans skill
- Do NOT modify tests — they should pass without changes after refactoring
- Use TDD approach with frequent commits

## Discoveries

- **Current state**: `game.py` is a classic "god object" handling 6 game states (CONNECT, CREATION, NAVIGATION, CAMPFIRE, STRATEGY, COMBAT) plus survival, mounts, cart, chat, environment, inventory, combat orchestration, and more
- **Existing partial extraction**: `inventory_ops.py`, `survival.py`, `campfire.py`, `environment.py`, `chat.py` already extracted but still wrapped by GameSession
- **Selected architecture**: Approach A - State Handlers with:
  - Stateless singleton handlers (memory efficient, thread-safe)
  - TypedDict contexts for state-specific data (Option B)
  - O(1) command dispatch via dict lookup (replaces 200+ line if-elif chains)
  - Include existing utility modules in design

## Accomplished

1. ✅ Analyzed game.py and identified god object problems
2. ✅ Presented 3 refactoring approaches (A: State Handlers, B: Command Pattern, C: Hybrid)
3. ✅ User selected Approach A (State Handlers)
4. ✅ Created detailed design with 4 architecture decisions
5. ✅ User requested best options for all decisions → chose TypedDicts, stateless singletons, dict dispatch, include existing modules
6. ✅ Wrote 2,476-line implementation plan with 12 tasks across 5 phases
7. ✅ Committed plan to git master
8. ✅ Pushed to origin

**In Progress**: None yet — implementation has not started

**Next**: Execute the implementation plan (12 tasks)

## Relevant files / directories

- **`server/engine/game.py`** — Main file to refactor (1,667 → ~250 lines)
- **`docs/superpowers/plans/2026-04-12-game-session-decomposition.md`** — Implementation plan (2,476 lines)
- **`server/engine/states/`** — New directory to create with handlers:
  - `__init__.py` — State enum, HANDLER_REGISTRY
  - `base.py` — StateHandler protocol
  - `contexts.py` — TypedDict state contexts
  - `connect.py` — Login handler
  - `creation.py` — Character creation wizard
  - `navigation.py` — Exploration handler (largest, ~350 lines)
  - `campfire.py` — Rest & party management
  - `strategy.py` — Strategy editor
  - `combat.py` — Combat orchestration
- **`server/engine/protocols.py`** — Existing Protocol definitions
- **`IMPROVEMENTS.md`** — Architecture findings including A1 (God Object issue)