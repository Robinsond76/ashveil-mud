# Async Safety — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add proper synchronization to shared mutable state, decouple NPC respawn from combat, and fix light source persistence.

**Architecture:** Add `asyncio.Lock` to `WorldMap.room_occupants` mutations. Move NPC respawn ticking into `WorldClock` as a periodic global operation. Persist lit source state through `Character.to_dict()`.

**Tech Stack:** Python 3.x, asyncio (no new dependencies)

**Addresses findings:** A3 (unsynced global state), A8 (NPC respawn only ticks in combat)

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `server/engine/world.py` | MODIFY | Add `asyncio.Lock` on `room_occupants`; make `enter_room`/`leave_room` async |
| `server/engine/world_clock.py` | MODIFY | Add periodic `tick_respawns()` call on each world tick |
| `server/engine/game.py` | MODIFY | Await `enter_room`/`leave_room` (now async); persist `_lit_sources` |
| `server/engine/character.py` | MODIFY | Add `lit_sources` to `to_dict()`/`from_dict()` |
| `server/main.py` | MODIFY | Pass `WorldMap` to `WorldClock` for respawn ticking |

---

### Task 1: Add asyncio.Lock to WorldMap.room_occupants

**Files:**
- Modify: `server/engine/world.py`
- Test: `tests/test_improvement04_async.py`

- [ ] **Step 1: Write failing test for concurrent room enter/leave safety**

```python
# tests/test_improvement04_async.py

import asyncio
import pytest


@pytest.mark.asyncio
async def test_concurrent_room_enter_does_not_corrupt(load_game_data):
    """Two players entering the same room concurrently should both appear."""
    from server.engine.world import WorldMap
    world = WorldMap()
    # Manually add a room entry
    world.room_occupants["town_square"] = []

    async def enter(name):
        await world.enter_room("town_square", name)

    await asyncio.gather(enter("Alice"), enter("Bob"))
    occupants = await world.players_in_room("town_square")
    assert "Alice" in occupants
    assert "Bob" in occupants
    assert len(occupants) == 2


@pytest.mark.asyncio
async def test_concurrent_leave_does_not_corrupt(load_game_data):
    """Two players leaving the same room concurrently should both be removed."""
    from server.engine.world import WorldMap
    world = WorldMap()
    world.room_occupants["town_square"] = ["Alice", "Bob"]

    async def leave(name):
        await world.leave_room("town_square", name)

    await asyncio.gather(leave("Alice"), leave("Bob"))
    occupants = await world.players_in_room("town_square")
    assert len(occupants) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement04_async.py -v`
Expected: FAIL — `enter_room` is not async / doesn't exist as async yet

- [ ] **Step 3: Add `asyncio.Lock` to WorldMap**

In `server/engine/world.py`, update `WorldMap.__init__()` (line 112):

```python
import asyncio

class WorldMap:
    def __init__(self):
        self._rooms = {}
        self.room_occupants = {}
        self._occupants_lock = asyncio.Lock()
```

Convert `enter_room`, `leave_room`, and `players_in_room` to async:

```python
async def enter_room(self, room_id, player_name):
    async with self._occupants_lock:
        if room_id not in self.room_occupants:
            self.room_occupants[room_id] = []
        if player_name not in self.room_occupants[room_id]:
            self.room_occupants[room_id].append(player_name)

async def leave_room(self, room_id, player_name):
    async with self._occupants_lock:
        if room_id in self.room_occupants:
            try:
                self.room_occupants[room_id].remove(player_name)
            except ValueError:
                pass

async def players_in_room(self, room_id):
    async with self._occupants_lock:
        return list(self.room_occupants.get(room_id, []))
```

- [ ] **Step 4: Update all callers in `game.py` to await the new async methods**

Search `game.py` for all calls to `self.world.enter_room(`, `self.world.leave_room(`, and `self.world.players_in_room(`. Add `await` to each:

```python
# Before:
self.world.enter_room(self.current_room_id, self.player.name)
# After:
await self.world.enter_room(self.current_room_id, self.player.name)

# Before:
self.world.leave_room(old_room, self.player.name)
# After:
await self.world.leave_room(old_room, self.player.name)

# Before:
occupants = self.world.players_in_room(self.current_room_id)
# After:
occupants = await self.world.players_in_room(self.current_room_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_improvement04_async.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (may need to update other tests that call these methods)

- [ ] **Step 7: Commit**

```bash
git add server/engine/world.py server/engine/game.py tests/test_improvement04_async.py
git commit -m "fix: add asyncio.Lock to WorldMap room_occupants for concurrent safety"
```

---

### Task 2: Move NPC Respawn Into WorldClock

**Files:**
- Modify: `server/engine/world_clock.py`
- Modify: `server/engine/world.py`
- Modify: `server/main.py`
- Test: `tests/test_improvement04_async.py` (extend)

- [ ] **Step 1: Write test for periodic respawn ticking**

```python
# Append to tests/test_improvement04_async.py

def test_world_clock_ticks_respawns(load_game_data):
    """WorldClock should call world.tick_respawns() on each game-minute tick."""
    from server.engine.world import WorldMap, Room, EncounterGroup
    from server.engine.world_clock import WorldClock

    world = WorldMap()
    # Add a room with a defeated encounter group
    room = Room.__new__(Room)
    room.id = "test_room"
    room.encounter_groups = [EncounterGroup.__new__(EncounterGroup)]
    room.encounter_groups[0].defeated = True
    room.encounter_groups[0].respawn_countdown = 2
    room.encounter_groups[0].respawn_ticks = 3
    room.encounter_groups[0].members = []
    room.encounter_groups[0].group = "test_group"
    room.encounter_groups[0].label = "Test Group"
    world._rooms["test_room"] = room

    # Simulate one respawn tick
    world.tick_respawns()
    assert room.encounter_groups[0].respawn_countdown == 1

    world.tick_respawns()
    assert room.encounter_groups[0].respawn_countdown == 0
    assert room.encounter_groups[0].defeated is False  # respawned
```

- [ ] **Step 2: Run test to verify baseline behavior**

Run: `pytest tests/test_improvement04_async.py::test_world_clock_ticks_respawns -v`
Expected: PASS (tick_respawns already works; we're testing the existing logic)

- [ ] **Step 3: Wire WorldClock to call `tick_respawns()` periodically**

In `server/engine/world_clock.py`, update `WorldClock.__init__()` to accept a `world` parameter:

```python
class WorldClock:
    def __init__(self, world=None):
        # ... existing init
        self._world = world
```

In the main tick loop (where game minutes advance), add:

```python
# After advancing game time:
if self._world:
    self._world.tick_respawns()
```

- [ ] **Step 4: Update `main.py` to pass WorldMap to WorldClock**

In `server/main.py`, startup hook:

```python
# Before:
_world_clock = WorldClock()

# After:
_world_clock = WorldClock(world=_world)
```

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/engine/world_clock.py server/main.py tests/test_improvement04_async.py
git commit -m "feat: WorldClock ticks NPC respawns globally, decoupled from combat"
```

---

### Task 3: Persist Light Source State

**Files:**
- Modify: `server/engine/character.py`
- Modify: `server/engine/game.py`
- Test: `tests/test_improvement04_async.py` (extend)

- [ ] **Step 1: Write failing test for light source persistence**

```python
# Append to tests/test_improvement04_async.py

def test_lit_sources_persist_in_to_dict(load_game_data):
    """lit_sources should be included in Character.to_dict()."""
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")
    c.lit_sources = {"torch_1": 500}
    d = c.to_dict()
    assert d["lit_sources"] == {"torch_1": 500}


def test_lit_sources_restored_from_dict(load_game_data):
    """lit_sources should be restored from Character.from_dict()."""
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")
    c.lit_sources = {"torch_1": 500}
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.lit_sources == {"torch_1": 500}


def test_lit_sources_defaults_empty(load_game_data):
    """lit_sources should default to empty dict."""
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")
    assert c.lit_sources == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement04_async.py::test_lit_sources_persist_in_to_dict -v`
Expected: FAIL — `lit_sources` attribute doesn't exist

- [ ] **Step 3: Add `lit_sources` field to Character**

In `server/engine/character.py`, add to the dataclass:

```python
from dataclasses import dataclass, field

# Add to Character fields:
lit_sources: dict = field(default_factory=dict)
```

In `to_dict()` (line ~431):
```python
"lit_sources": dict(self.lit_sources),
```

In `from_dict()` (line ~470):
```python
lit_sources=d.get("lit_sources", {}),
```

- [ ] **Step 4: Update `game.py` to use `player.lit_sources` instead of `self._lit_sources`**

In `game.py`, replace all references to `self._lit_sources` with `self.player.lit_sources`:
- `__init__()`: Remove `self._lit_sources = {}` (line ~754)
- `_carried_light()`: Change `self._lit_sources` → `self.player.lit_sources`
- `_do_light_source()`: Change `self._lit_sources` → `self.player.lit_sources`
- `_load_save()`: Restore `self.player.lit_sources` from saved data (it now comes through `from_dict()` automatically)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_improvement04_async.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/engine/character.py server/engine/game.py tests/test_improvement04_async.py
git commit -m "fix: persist light source state through Character serialization"
```
