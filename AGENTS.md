# AGENTS.md

## Commands

```bash
# Install deps (first time)
uv sync

# Run server on port 8081
uv run uvicorn server.main:app --reload --port 8081

# Run all tests (asyncio_mode=auto in pytest.ini)
uv run pytest tests/

# Run a single test file
uv run pytest tests/test_character_deletion.py
```

No lint, typecheck, or formatter config exists. There is no Makefile.

## Architecture

**State machine pattern.** A per-connection `GameSession` (server/engine/game.py) delegates to singleton state handlers:

```
CONNECT → CREATION → NAVIGATION ⇄ CAMPFIRE, COMBAT, STRATEGY
```

- **Handlers** (`server/engine/states/`) are stateless singletons. All mutable state lives in `GameSession`.
- **Subsystems** live in `server/engine/systems/` (campfire, chat, inventory, mounts, survival, utility_skills).
- **Domain models** in `server/engine/domain/` (Character, NPC, items, skills, validation).
- **World** in `server/engine/world/` (map, clock). WorldClock is shared across sessions.

**Data flow:** All output goes through `await session.send(text)`. Never use `print()`. Input arrives via `await session.handle_input(raw_text)`.

**Entry point:** `server/main.py` — loads all JSON data once at startup, mounts the browser client at `/`, WebSocket endpoint at `/ws`.

## Key conventions

- `from __future__ import annotations` is used project-wide for deferred evaluation.
- State handler imports use **lazy loading** (`states/__init__.py:27-43`) to break circular imports — add new handlers the same way.
- Tests use `make_nav_session` fixture (conftest.py) to create a session in NAVIGATION state, and `AsyncMock` for `session.send`.
- Test the `_collected` list on the session to assert output text.

## Game data

All content is JSON in `server/data/`: `classes/`, `items/`, `npcs/`, `rooms/`, `skills/`. Loaded once at startup by `load_items()`, `load_npcs()`, `load_skills()`, and `WorldMap.load()`.

## Config & debug

`server/config.py` — hardcoded constants. Key flags:
- `DEBUG_NO_DEATH_PENALTY = True` — disables XP/gold loss on death (on by default).
- `DATABASE_URL = "sqlite:///mud.db"` — change this to switch databases.
- Combat timing, stat budgets, and world clock ratios are all here.

## Persistence

SQLAlchemy + SQLite (`server/engine/persistence.py`). Player saves are stored as JSON blobs keyed by name. Interface: `save_player()`, `load_player()`, `delete_player()`. Must call `init_db()` before use. `check_same_thread=False` on the SQLite connection.
