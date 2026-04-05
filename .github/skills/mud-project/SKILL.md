---
name: mud-project
description: "Use when: working on Ashveil MUD — covers stack, conventions, run commands, test commands, data layout, phase workflow, and where specs/plans live. Load before any feature work, debugging, or planning on this codebase."
---

# Ashveil MUD — Project Skill

## What This Is

A Python-based text MUD (Multi-User Dungeon) with a browser terminal client. Players connect via WebSocket, explore rooms, fight monsters in tick-based combat, manage a party, and progress through skills and gear.

## Stack

| Layer | Technology |
|-------|-----------|
| Server | Python 3.x, asyncio, FastAPI |
| Transport | WebSocket (`/ws`) |
| Database | SQLAlchemy + SQLite (per-player JSON blob) |
| Client | HTML + vanilla JS terminal (`client/`) |
| Deps | `requirements.txt` — fastapi, uvicorn, websockets, sqlalchemy, pydantic, aiofiles |

## Run Commands

```powershell
# Install dependencies (first time or after requirements.txt changes)
pip install -r requirements.txt

# Start the server (from workspace root)
uvicorn server.main:app --reload

# Server available at: http://localhost:8000
# WebSocket at:        ws://localhost:8000/ws
# Browser client at:  http://localhost:8000  (serves client/index.html)
```

## Testing

There is a `pytest` test suite under `tests/` (55 tests as of Phase 2, all passing). Run it from the workspace root:

```powershell
pytest tests/
```

Test files follow the naming convention `test_phase<NN>_<topic>.py`. Fixtures are in `tests/conftest.py` (session-scoped; loads items + NPCs from JSON).

For manual verification:
1. Start the server with `uvicorn server.main:app --reload`
2. Open the browser client and run through the relevant commands
3. Check for Python exceptions in the uvicorn console output

When adding new phase tests: create files as `tests/test_phase<NN>_<topic>.py`. Stub imports from `server.engine.*`.

## Directory Layout

```
server/
  config.py            — constants (tick rates, weather, game time, etc.)
  main.py              — FastAPI app, WebSocket entrypoint, startup hooks
  engine/
    character.py       — Character dataclass, stat rolls
    combat.py          — CombatSession, tick loop, attack resolution
    game.py            — GameSession, all command handling (largest file)
    items.py           — Item/Inventory logic
    npc.py             — NPC dataclass, factory
    persistence.py     — save_player / load_player (SQLAlchemy)
    skills.py          — Skill registry and resolution
    strategy.py        — Combat strategy enum and AI
    world.py           — Room, WorldMap, room loader
    world_clock.py     — WorldClock (background asyncio tick loop)
  data/
    classes/classes.json
    items/armor.json, weapons.json, consumables.json, misc.json
    npcs/monsters.json, recruitables.json
    rooms/town.json, forest.json, dungeon.json, testing_grounds.json
    skills/warrior_skills.json, mage_skills.json, thief_skills.json, cleric_skills.json
client/
  index.html           — browser terminal UI
  terminal.js          — WebSocket client logic
docs/
  superpowers/
    specs/             — approved feature specs (one file per phase)
    plans/             — implementation plans (one file per phase)
```

## Key Conventions

- **Single asyncio event loop**: Everything (WebSocket, combat, world clock) runs cooperatively. Never use `threading` or `asyncio.run()` inside coroutines.
- **JSON data files**: Game content (rooms, NPCs, items, skills, classes) is defined in `server/data/`. Python code never hard-codes game content.
- **No type annotations** on new code unless the surrounding file already uses them.
- **No docstrings** unless the surrounding code already has them.
- **`GameSession`** is one-per-WebSocket-connection. It owns all per-player state for the session.
- **`WorldMap`** and **`WorldClock`** are shared singletons, initialized in `main.py` at startup.
- **State machine**: `CONNECT → CREATION → NAVIGATION → CAMPFIRE → STRATEGY → COMBAT`. Commands are gated by state.
- **New commands** go in `game.py` in the `handle_input()` dispatch block.
- **New data fields** on `Character` go in `character.py`; load/save in `persistence.py`.

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| JSON data files | Easy to edit content without touching code |
| Single asyncio event loop | Avoids threading complexity |
| `WorldClock` subscribers | Decouples weather broadcast from session polling |
| Per-session `CombatSession` | Keeps combat isolated; multiplayer combat is future work |
| `room_type` ("outdoor"/"indoor"/"underground") | Three-way distinction needed for weather/light |
| `_THIRST_MULTIPLIERS` at module level (not dataclass field) | Avoids dataclass mutable-default error |
| Darkvision on NPC, not player race | Simpler; monsters drive the darkness rule |
| `survival_multiplier` computed once at `CombatSession` creation | Keeps survival penalties static for the duration of a fight |
| `_sitting_stamina_tick()` only fires when not in combat | Prevents stamina regen overlap with combat tick |
| EAT/DRINK use partial name match against inventory | Tolerant UX — players don't need exact item IDs |

## Phase System & Specs/Plans

Feature development follows a phase workflow:

| # | Phase | Status | Spec | Plan |
|---|-------|--------|------|------|
| 1 | World Clock & Environment | ✅ COMPLETED | `docs/superpowers/specs/phase-01-world-clock-environment.md` | — |
| 2 | Survival Stats | ✅ COMPLETED | `docs/superpowers/specs/phase-02-survival-stats.md` | `docs/superpowers/plans/phase-02-survival-stats.md` |
| 3 | Utility Skills & Mana Rework | 🔲 NOT STARTED | `docs/superpowers/specs/phase-03-utility-skills-mana.md` | `docs/superpowers/plans/phase-03-utility-skills-mana.md` |
| 4 | Food & Consumables | 🔲 NOT STARTED | `docs/superpowers/specs/phase-04-food-consumables.md` | `docs/superpowers/plans/phase-04-food-consumables.md` |
| 5 | Inventory & Weight | 🔲 NOT STARTED | `docs/superpowers/specs/phase-05-inventory-weight.md` | `docs/superpowers/plans/phase-05-inventory-weight.md` |
| 6 | Horses & Mounts | 🔲 NOT STARTED | `docs/superpowers/specs/phase-06-horses-mounts.md` | `docs/superpowers/plans/phase-06-horses-mounts.md` |
| 7 | Wizard & Spell Overhaul | 🔲 NOT STARTED | `docs/superpowers/specs/phase-07-wizard-spell-overhaul.md` | `docs/superpowers/plans/phase-07-wizard-spell-overhaul.md` |
| 8 | Help System | 🔲 NOT STARTED | `docs/superpowers/specs/phase-08-help-system.md` | `docs/superpowers/plans/phase-08-help-system.md` |
| 9 | Multiplayer Foundations | 🔲 NOT STARTED | `docs/superpowers/specs/phase-09-multiplayer-foundations.md` | `docs/superpowers/plans/phase-09-multiplayer-foundations.md` |

**New specs** → `docs/superpowers/specs/phase-NN-<slug>.md`
**New plans** → `docs/superpowers/plans/phase-NN-<slug>.md`

## Workflow for a New Phase

1. Read the spec from `docs/superpowers/specs/phase-NN-*.md`
2. If no plan exists yet, use the **writing-plans** skill to create one at `docs/superpowers/plans/phase-NN-*.md`
3. Use the **executing-plans** or **subagent-driven-development** skill to work through the plan
4. Use the **verification-before-completion** skill before declaring a phase done
5. Update `MEMORY.md` to mark the phase status and document what was built
