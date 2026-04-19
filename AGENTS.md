# Ashveil MUD — Agent Instructions

## Quick Start

### First-time Setup

```powershell
pip install -r requirements.txt
```

### Run the Server

```powershell
python3 -m uvicorn server.main:app --reload --port 8081
```

Server runs at http://localhost:8081

### Run Tests

```powershell
# If pytest is not in your PATH, use the full path:
/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/

# Or run via Python module:
python3 -m pytest tests/
```

## Architecture

- **Entry point:** `server/main.py` — FastAPI app with WebSocket endpoint at `/ws`
- **Game engine:** `server/engine/game.py` — GameSession coordinator (843 lines), state handlers in `server/engine/states/`
- **Data:** JSON files in `server/data/` (rooms, items, NPCs, skills, classes)
- **Client:** `client/` — browser terminal (index.html + terminal.js)

## Key Quirks

- **Async safety issues:** `WorldMap.room_occupants`, `WorldClock._subscribers`, `_sessions` dict are mutated by concurrent async tasks with no `asyncio.Lock` (see IMPROVEMENTS.md A3, A4)
- **Combat↔GameSession coupling:** `CombatSession` takes callbacks into `GameSession`; cannot reuse combat independently
- **String-based action dispatch:** `evaluate_strategy()` returns raw strings like `"USE_SKILL fireball"`, parsed in `_do_action()` with `.startswith()` checks
- **Light sources not persisted:** `_lit_sources` in game.py not saved to Character.to_dict()
- **Magic numbers hardcoded:** stamina drain rates (2.0), crit multiplier (1.5), flee chance (0.40), etc.

## Recent Improvements (2026-04-18)

- **A1: GameSession Decomposition** — Refactored 1,667-line `GameSession` into 6 stateless state handlers. `game.py` reduced to 843 lines. All 613 tests pass.

## Testing

- `/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/` — all tests use `asyncio_mode = auto`
- Many test files are phase-named (test_phase02_*, test_phase03_*, etc.)
- Known issues (see IMPROVEMENTS.md):
  - T1: Trivial pass tests that only check field initialization
  - T4: Excessive mocking hides real bugs
  - T5: No async/concurrency testing

## Important Files

- `GETTING_STARTED.md` — comprehensive game tutorial
- `IMPROVEMENTS.md` — architecture and test findings (19 architecture + 14 test findings)
- `server/config.py` — configuration values
- `server/engine/character.py` — XP_TABLE (10 levels), MODIFIER_CATALOGUE
- `server/engine/world.py` — WorldMap with room loading

## Working on This Repo

- Run `/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/` after every change
- Check IMPROVEMENTS.md before major refactors — execution order: 03 → 01 → 02 → 04 → 05 → 06 → 07
- game.py is the main bottleneck; expect decomposition work to be complex