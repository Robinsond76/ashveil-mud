# Holistic Codebase Refactoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `server/engine/` into domain-focused subpackages, eliminate all 18 remaining architecture findings (A2-A19) from IMPROVEMENTS.md, and establish clean import boundaries.

**Architecture:** Five new subpackages under `server/engine/` — `domain/` (pure data models), `combat/` (battle engine), `display/` (formatting/output), `world/` (map/clock/environment), `systems/` (game mechanics). NavigationHandler split into command submodules. GameSession reduced from 1058 to ~300 lines as a thin coordinator.

**Tech Stack:** Python 3.9+, dataclasses, asyncio.Lock, Pydantic v2 (already in deps), pytest, FastAPI

**Design Spec:** `docs/superpowers/specs/2026-04-28-holistic-refactoring-design.md`

---

## File Structure Map

### New files to create
```
server/engine/domain/__init__.py
server/engine/domain/character.py        # from character.py
server/engine/domain/npc.py              # from npc.py
server/engine/domain/items.py            # from items.py
server/engine/domain/skills.py           # from skills.py
server/engine/domain/combatant.py        # new: CombatantState wrapper
server/engine/combat/__init__.py
server/engine/combat/session.py          # from combat.py (decoupled)
server/engine/combat/actions.py          # from actions.py
server/engine/combat/strategy.py         # from strategy.py (enum dispatch)
server/engine/combat/grid.py             # new: position grid
server/engine/combat/rewards.py          # new: loot/XP/gold
server/engine/display/__init__.py
server/engine/display/formatting.py      # new: _box() + shared display
server/engine/display/context_panel.py   # from game.py lines 826-1007
server/engine/display/help_data.py       # from help_registry.py
server/engine/world/__init__.py
server/engine/world/map.py              # from world.py (+ async locks)
server/engine/world/clock.py            # from world_clock.py (+ async locks)
server/engine/world/environment.py      # from environment.py
server/engine/systems/__init__.py
server/engine/systems/inventory.py      # from inventory_ops.py
server/engine/systems/survival.py       # from survival.py
server/engine/systems/campfire.py       # from campfire.py
server/engine/systems/chat.py           # from chat.py
server/engine/systems/mounts.py         # new: from game.py extraction
server/engine/systems/utility_skills.py # new: from game.py extraction
server/engine/states/navigation/__init__.py
server/engine/states/navigation/inventory.py
server/engine/states/navigation/party.py
server/engine/states/navigation/social.py
server/engine/states/navigation/interaction.py
server/engine/states/navigation/mounts.py
server/engine/states/navigation/quick_look.py
```

### Files to delete (after migration)
```
server/engine/help_registry.py
server/engine/inventory_ops.py
server/engine/campfire.py
server/engine/chat.py
server/engine/survival.py
server/engine/environment.py
server/engine/item_effects.py
```

### Files heavily modified
```
server/engine/game.py                    # reduced 1058→~300
server/engine/combat.py                  # split into combat/
server/engine/strategy.py                # split into combat/
server/engine/world.py                   # → world/map.py
server/engine/world_clock.py             # → world/clock.py
server/engine/character.py               # → domain/character.py
server/engine/npc.py                     # → domain/npc.py
server/engine/items.py                   # → domain/items.py
server/engine/skills.py                  # → domain/skills.py
server/engine/states/navigation.py       # split 884→~150
server/engine/states/combat.py           # simplified (caller handles result)
server/engine/states/campfire.py         # simplified
server/engine/persistence.py             # upgraded: schema v2, Result return
server/engine/protocols.py               # → domain/combatant.py
server/main.py                           # SessionRegistry + lock
```

### Test files to update
```
tests/conftest.py                        # update imports
tests/test_improvement02_actions.py      # update imports
tests/test_improvement03_data_model.py   # update imports
tests/test_improvement04_async.py        # update imports + async tests
tests/test_improvement05_validation.py   # update imports
tests/test_phase02_*.py                  # 4 files — update imports
tests/test_phase03_utility_skills.py     # update imports
tests/test_phase04_*.py                  # 3 files — update imports
tests/test_phase05_inventory_weight.py   # update imports
tests/test_phase06_horses_mounts.py      # update imports
tests/test_phase07_*.py                  # 2 files — update imports
tests/test_phase08_help_system.py        # update imports
tests/test_phase09_multiplayer_foundations.py
tests/test_combat_speed.py              # update imports
tests/test_error_paths.py               # update imports
tests/test_integration_flow.py          # update imports
tests/test_persistence_roundtrip.py     # update imports
tests/test_chat_commands.py             # update imports
tests/test_character_deletion.py        # update imports
tests/test_caster_spell_preference.py   # update imports
tests/test_quick_look.py                # update imports
tests/test_persistence_names.py         # update imports
```

---

## Phase 1: Display Layer (A17)

Extract shared formatting utilities. Move help_registry and context panel to display/ with zero logic changes.

### Task 1.1: Create display/formatting.py with shared _box()

**Files:**
- Create: `server/engine/display/__init__.py`
- Create: `server/engine/display/formatting.py`

- [ ] **Step 1: Create display package and formatting module**

```bash
mkdir -p server/engine/display
```

```python
# server/engine/display/__init__.py
```

```python
# server/engine/display/formatting.py
"""Shared display formatting utilities — the single source of truth for _box()."""
from __future__ import annotations


def box(title: str, lines: list[str]) -> str:
    """Format a boxed display with title."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)
```

- [ ] **Step 2: Run tests to confirm no regressions**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
Expected: all tests still pass (new file has no consumers yet)

- [ ] **Step 3: Update game.py to import _box from formatting.py**

Replace in `server/engine/game.py`:
```python
def _box(title: str, lines: list[str]) -> str:
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)
```

With:
```python
from server.engine.display.formatting import box as _box
```

- [ ] **Step 4: Run tests**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: extract shared _box() to display/formatting.py"
```

### Task 1.2: Migrate help_registry.py → display/help_data.py

**Files:**
- Create: `server/engine/display/help_data.py`
- Delete: `server/engine/help_registry.py`

- [ ] **Step 1: Create help_data.py as copy of help_registry.py with formatting imports updated**

```bash
cp server/engine/help_registry.py server/engine/display/help_data.py
```

```python
# server/engine/display/help_data.py (top of file — replace existing imports)
"""Help topic registry — all HELP content extracted from GameSession."""
from __future__ import annotations

from server.engine.display.formatting import box as _box
from server.engine.states import State
```
(Rest of the file stays identical — just the import changes)

- [ ] **Step 2: Update game.py import**

In `server/engine/game.py` line 52, replace:
```python
from server.engine.help_registry import send_help, _HELP_TOPICS
```
With:
```python
from server.engine.display.help_data import send_help, _HELP_TOPICS
```

- [ ] **Step 3: Update all test imports that reference help_registry**

```bash
rg -l "help_registry" tests/ --type py
```

For each file found, update the import from `server.engine.help_registry` to `server.engine.display.help_data`.

- [ ] **Step 4: Run tests**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
Expected: all tests pass

- [ ] **Step 5: Delete old help_registry.py**

```bash
rm server/engine/help_registry.py
```

- [ ] **Step 6: Verify no remaining references**

```bash
rg "help_registry" server/ --type py
```
Expected: no output

- [ ] **Step 7: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: migrate help_registry to display/help_data.py"
```

### Task 1.3: Extract context panel from game.py to display/context_panel.py

**Files:**
- Create: `server/engine/display/context_panel.py`
- Modify: `server/engine/game.py` (remove lines 72, 826-1007)

- [ ] **Step 1: Create context_panel.py with all context-gathering logic**

```python
# server/engine/display/context_panel.py
"""Context panel data gathering — extracted from GameSession."""
from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from server.engine.domain.items import get_item
from server.engine.domain.skills import get_skill
from server.engine.systems.survival import party_survival_aggregate
from server.engine.world.environment import effective_light as _effective_light_fn

if TYPE_CHECKING:
    from server.engine.game import GameSession

logger = logging.getLogger(__name__)

MAX_CONTEXT_INVENTORY_ITEMS = 10


async def send_context_update(session: GameSession) -> None:
    """Send current game context to client as JSON."""
    if not session.player:
        return
    if not hasattr(session.player, 'to_dict'):
        return
    if hasattr(session._send_raw, '_mock_name'):
        return
    try:
        context = gather_context(session)
        json_msg = json.dumps({"type": "context", "data": context})
        await session.send(json_msg)
    except (TypeError, ValueError) as e:
        logger.debug(f"Failed to serialize context: {e}")


def gather_context(session: GameSession) -> dict[str, Any]:
    """Gather all context data for the side panel."""
    return {
        "player": get_player_context(session),
        "party": get_party_context(session),
        "map": get_map_context(session),
        "inventory": get_inventory_context(session),
        "environment": get_environment_context(session),
    }


def get_player_context(session: GameSession) -> dict[str, Any]:
    """Get player character stats and status."""
    if not session.player:
        return {}
    h_pct, t_pct, s_pct = 1.0, 1.0, 1.0
    if session.party:
        h_pct, t_pct, s_pct = party_survival_aggregate(session.player, session.party)
    return {
        "name": session.player.name,
        "class": session.player.class_type,
        "level": session.player.level,
        "xp": session.player.xp,
        "hp": session.player.hp,
        "max_hp": session.player.max_hp,
        "mp": session.player.mp,
        "max_mp": session.player.max_mp,
        "stats": {
            "STR": session.player.STR,
            "DEX": session.player.DEX,
            "INT": session.player.INT,
            "WIS": session.player.WIS,
            "CON": session.player.CON,
            "AGI": session.player.AGI,
        },
        "hunger": int(h_pct * 100),
        "thirst": int(t_pct * 100),
        "stamina": int(s_pct * 100),
        "gold": session.player.gold,
    }


def get_party_context(session: GameSession) -> list[dict[str, Any]]:
    """Get party member information."""
    if not session.party:
        return []
    members = []
    for npc in session.party:
        member_data = {
            "name": npc.name,
            "hp": npc.hp,
            "max_hp": npc.max_hp,
            "mp": npc.mp,
            "max_mp": npc.max_mp,
            "class": npc.class_type,
        }
        if hasattr(npc, 'template_id'):
            member_data["template_id"] = npc.template_id
        members.append(member_data)
    return members


def get_map_context(session: GameSession) -> dict[str, Any]:
    """Get mini-map data for current location."""
    if not session.current_room_id:
        return {}
    room = session.world.get_room(session.current_room_id)
    if not room:
        return {}
    connected = {}
    for direction, room_id in room.exits.items():
        connected_room = session.world.get_room(room_id)
        if connected_room:
            connected[direction] = {"name": connected_room.name, "room_id": room_id}
    return {
        "current": {"id": room.id, "name": room.name, "zone": room.zone},
        "exits": connected,
    }


def get_inventory_context(session: GameSession) -> dict[str, Any]:
    """Get inventory summary."""
    if not session.player:
        return {}
    items = []
    for item_id in session.player.inventory[:MAX_CONTEXT_INVENTORY_ITEMS]:
        item = get_item(item_id)
        if item:
            items.append({"id": item_id, "name": item.name, "type": item.type})
    return {
        "count": len(session.player.inventory),
        "items": items,
        "has_more": len(session.player.inventory) > MAX_CONTEXT_INVENTORY_ITEMS,
        "equipment": session.player.equipment,
    }


def get_environment_context(session: GameSession) -> dict[str, Any]:
    """Get environment data (time, weather, temperature, visibility)."""
    if not session.clock:
        return {}
    room = None
    if session.current_room_id:
        room = session.world.get_room(session.current_room_id)
    eff_light = 1.0
    if room:
        eff_light = _effective_light_fn(
            session.player, session.party, session.player.lit_sources, session.clock, room
        )
    if eff_light >= 0.80:
        visibility = "Bright"
    elif eff_light >= 0.40:
        visibility = "Dim"
    elif eff_light >= 0.05:
        visibility = "Dark"
    else:
        visibility = "Pitch Black"
    temp_label = "Unknown"
    if room:
        temp_label = session.clock.temperature_label(room.room_type, room.base_temp_f)
    return {
        "time_of_day": session.clock.time_of_day_label(),
        "time_string": session.clock.time_string(),
        "weather": session.clock.current_weather,
        "temperature": temp_label,
        "visibility": visibility,
        "room_type": room.room_type if room else "unknown",
    }
```

- [ ] **Step 2: Update game.py — remove MAX_CONTEXT_INVENTORY_ITEMS and context methods, add delegation**

In `server/engine/game.py`:
- Remove line 72: `MAX_CONTEXT_INVENTORY_ITEMS = 10`
- Remove lines 826-1007 (all `_send_context_update`, `_gather_context`, `_get_player_context`, `_get_party_context`, `_get_map_context`, `_get_inventory_context`, `_get_environment_context` methods)
- Add import at top:
```python
from server.engine.display.context_panel import send_context_update as _send_context_update
```

- [ ] **Step 3: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: extract context panel to display/context_panel.py"
```

---

## Phase 2: Domain Layer (A2, A14, A16)

Create `engine/domain/` package. Move character.py, npc.py, items.py, skills.py. Add CombatantState wrapper.

### Task 2.1: Create domain package with items.py and skills.py (leaf nodes first)

**Files:**
- Create: `server/engine/domain/__init__.py`
- Create: `server/engine/domain/items.py`
- Create: `server/engine/domain/skills.py`

- [ ] **Step 1: Create domain directory and move items.py**

```bash
mkdir -p server/engine/domain
cp server/engine/items.py server/engine/domain/items.py
```

Verify no internal imports in items.py need updating:
```bash
rg "from server" server/engine/domain/items.py
```
(Should be empty — items.py only imports from config and stdlib)

- [ ] **Step 2: Move skills.py**

```bash
cp server/engine/skills.py server/engine/domain/skills.py
```

- [ ] **Step 3: Update all imports from server.engine.items → server.engine.domain.items**

```bash
rg -l "from server.engine.items import" server/ tests/ --type py
```
Replace all occurrences.

- [ ] **Step 4: Update all imports from server.engine.skills → server.engine.domain.skills**

```bash
rg -l "from server.engine.skills import" server/ tests/ --type py
```
Replace all occurrences.

- [ ] **Step 5: Run tests**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "refactor: move items.py and skills.py to domain/ package"
```

### Task 2.2: Move character.py and npc.py to domain/

**Files:**
- Create: `server/engine/domain/character.py`
- Create: `server/engine/domain/npc.py`

- [ ] **Step 1: Copy and update character.py**

```bash
cp server/engine/character.py server/engine/domain/character.py
```

Update its imports in `server/engine/domain/character.py`:
- Change `from server.engine.items import` → `from server.engine.domain.items import`

- [ ] **Step 2: Copy and update npc.py**

```bash
cp server/engine/npc.py server/engine/domain/npc.py
```

Update its imports in `server/engine/domain/npc.py`:
- Change `from server.engine.items import` → `from server.engine.domain.items import`
- Change `from server.engine.character import` → `from server.engine.domain.character import`

- [ ] **Step 3: Update ALL imports across the codebase**

```bash
rg -l "from server.engine.character import" server/ tests/ --type py
```
Replace with `from server.engine.domain.character import`

```bash
rg -l "from server.engine.npc import" server/ tests/ --type py
```
Replace with `from server.engine.domain.npc import`

- [ ] **Step 4: Run tests**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move character.py and npc.py to domain/ package"
```

### Task 2.3: Add CombatantState wrapper (A2)

**Files:**
- Create: `server/engine/domain/combatant.py`
- Modify: `server/engine/domain/npc.py`

- [ ] **Step 1: Create CombatantState dataclass**

```python
# server/engine/domain/combatant.py
"""Combatant types — CombatantState wrapper and Combatant Protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class Combatant(Protocol):
    """Minimum interface for anything that participates in combat."""
    name: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    equipment: dict
    inventory: list

    @property
    def is_alive(self) -> bool: ...


@dataclass
class CombatantState:
    """Combat-only state attached to a Character/NPC during combat.
    
    Keeps combat fields separate from the base Character/NPC model
    so they never leak into persistence or non-combat contexts.
    """
    combatant: object         # Character | NPC
    speed: int = 0            # effective_speed during combat
    grid_row: int = 0         # 0=FRONT, 1=BACK
    grid_col: int = 0         # 0, 1, or 2
    strategies: dict = field(default_factory=dict)
    active_buffs: dict[str, int] = field(default_factory=dict)
    status_effects: dict[str, int] = field(default_factory=dict)
    action_cooldown: float = 0.0
```

- [ ] **Step 2: Remove combat-only fields from NPC and Character**

From `server/engine/domain/npc.py`, remove:
- `strategies` field (was `field(default_factory=dict)`)
- `grid_row` and `grid_col` (were part of NPC)
- `status_effects` field
- `active_buffs` field

These are now only in `CombatantState`.

From `server/engine/domain/character.py`, remove any combat-specific fields that leaked in. Check for `combat_speed`, `grid_row`, `grid_col`.

- [ ] **Step 3: Update combat session to create CombatantState wrappers**

In combat code (will be updated in Phase 5), wrap each party member:
```python
combatants = [
    CombatantState(combatant=c, speed=c.effective_speed, strategies=c.strategies if hasattr(c, 'strategies') else {})
    for c in player_party + enemy_party
]
```

- [ ] **Step 4: Run tests**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: add CombatantState wrapper for combat-only fields (A2)"
```

---

## Phase 3: World Layer (A3, A8)

Create `engine/world/` package. Move map, clock, environment. Add async locks.

### Task 3.1: Create world package and move WorldMap with async locks

**Files:**
- Create: `server/engine/world/__init__.py`
- Create: `server/engine/world/map.py`
- Delete: `server/engine/world.py` (after migration)

- [ ] **Step 1: Copy world.py to world/map.py**

```bash
mkdir -p server/engine/world
cp server/engine/world.py server/engine/world/map.py
```

- [ ] **Step 2: Add asyncio.Lock to WorldMap in map.py**

In `server/engine/world/map.py`, add to imports:
```python
import asyncio
```

Add to `WorldMap.__init__()`:
```python
self._occupants_lock = asyncio.Lock()
```

Wrap `room_occupants` mutations in `async with self._occupants_lock`:
- In the method that adds/removes occupants
- In `tick_respawns()`

- [ ] **Step 3: Move respawn ticking to WorldClock (A8)**

Move `tick_respawns()` call from combat end to WorldClock's tick loop. In `world/clock.py` (after copying):

Add to WorldClock's tick callback:
```python
async def _on_tick():
    # ... existing tick logic ...
    if self._tick_count % RESPAWN_CHECK_INTERVAL == 0:
        await self.world.tick_respawns()
```

Add to config.py:
```python
RESPAWN_CHECK_INTERVAL: int = 5  # Check respawns every 5 game-minutes
```

- [ ] **Step 4: Update all imports**

```bash
rg -l "from server.engine.world import" server/ tests/ --type py
```
Replace with `from server.engine.world.map import`

- [ ] **Step 5: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: move WorldMap to world/map.py with async locks (A3, A8)"
```

### Task 3.2: Move WorldClock and environment to world/

**Files:**
- Create: `server/engine/world/clock.py`
- Create: `server/engine/world/environment.py`

- [ ] **Step 1: Copy and update clock.py and environment.py**

```bash
cp server/engine/world_clock.py server/engine/world/clock.py
cp server/engine/environment.py server/engine/world/environment.py
```

Add async lock to clock: `self._sub_lock = asyncio.Lock()`. Wrap subscriber list mutations.

Update internal import in environment.py:
- `from server.engine.world_clock import` → `from server.engine.world.clock import`
- `from server.engine.items import` → `from server.engine.domain.items import`

- [ ] **Step 2: Replace duplicate _box() with import from formatting.py**

In `server/engine/world/environment.py`, remove local `_box()` function and add:
```python
from server.engine.display.formatting import box as _box
```

- [ ] **Step 3: Update all imports across codebase**

```bash
rg -l "from server.engine.world_clock import" server/ tests/ --type py
```
Replace with `from server.engine.world.clock import`

```bash
rg -l "from server.engine.environment import" server/ tests/ --type py
```
Replace with `from server.engine.world.environment import`

- [ ] **Step 4: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: move WorldClock and environment to world/ package (A3)"
```

---

## Phase 4: Systems Layer (A7, A10, A19)

Create `engine/systems/`. Move survival, inventory, campfire, chat. Extract mounts and utility_skills from game.py.

### Task 4.1: Create systems package with survival, inventory, campfire, chat

**Files:**
- Create: `server/engine/systems/__init__.py`
- Create: `server/engine/systems/survival.py`
- Create: `server/engine/systems/inventory.py`
- Create: `server/engine/systems/campfire.py`
- Create: `server/engine/systems/chat.py`

- [ ] **Step 1: Copy files and update imports**

```bash
mkdir -p server/engine/systems
cp server/engine/survival.py server/engine/systems/survival.py
cp server/engine/inventory_ops.py server/engine/systems/inventory.py
cp server/engine/campfire.py server/engine/systems/campfire.py
cp server/engine/chat.py server/engine/systems/chat.py
```

In each copied file, update imports:
- `from server.engine.items import` → `from server.engine.domain.items import`
- Remove local `_box()` functions and add `from server.engine.display.formatting import box as _box`

- [ ] **Step 2: Update all imports across codebase**

```bash
rg -l "from server.engine.survival import" server/ tests/ --type py
rg -l "from server.engine.inventory_ops import" server/ tests/ --type py
rg -l "from server.engine.campfire import" server/ tests/ --type py
rg -l "from server.engine.chat import" server/ tests/ --type py
```
Replace all with new paths.

- [ ] **Step 3: Centralize survival tick handler (A7)**

In `server/engine/systems/survival.py`, add:
```python
async def survival_tick_handler(session, temp_label: str) -> None:
    """Single entry point for survival drain + recovery per game-minute tick."""
    drain_survival_tick(session.player, session.party, session.clock, temp_label)
    if session._state != State.COMBAT:
        sitting_stamina_tick(session.player, session.party, session.clock, session._sitting)
```

Update game.py clock callback to call this single handler instead of two separate functions.

- [ ] **Step 4: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: move systems to systems/ package (A7, A19)"
```

### Task 4.2: Extract mounts logic from game.py (RIDE/DISMOUNT/HORSES/cart)

**Files:**
- Create: `server/engine/systems/mounts.py`

- [ ] **Step 1: Create mounts.py with extracted logic**

```python
# server/engine/systems/mounts.py
"""Mount system — RIDE, DISMOUNT, HORSES, cart logic extracted from GameSession."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import MOUNT_STAMINA_REDUCTION
from server.engine.domain.items import get_item

if TYPE_CHECKING:
    from server.engine.game import GameSession


def horse_count(session: "GameSession") -> int:
    """Count items with type == 'mount' across all party member inventories."""
    members = ([session.player] if session.player else []) + list(session.party)
    count = 0
    for m in members:
        for item_id in m.inventory:
            item = get_item(item_id)
            if item and item.type == "mount":
                count += 1
    return count


def stamina_multiplier(session: "GameSession") -> float:
    """Return stamina drain multiplier based on horse-to-party ratio."""
    if not session._mounted:
        return 1.0
    count = horse_count(session)
    party_size = max(1, 1 + len(session.party))
    ratio = min(1.0, count / party_size)
    return 1.0 - (MOUNT_STAMINA_REDUCTION * ratio)


def party_has_cart(session: "GameSession") -> bool:
    """Return True if any party member has travellers_cart."""
    members = ([session.player] if session.player else []) + list(session.party)
    for m in members:
        if "travellers_cart" in m.inventory:
            return True
    return False


async def do_ride(session: "GameSession") -> None:
    """RIDE — mount up if horses are available."""
    if horse_count(session) == 0:
        await session.send("  You don't have any horses.\n")
        return
    room = session.world.get_room(session.current_room_id)
    if room and room.room_type != "outdoor":
        await session.send("  You can only mount up outdoors.\n")
        return
    session._mounted = True
    await session.send("  The party mounts up and prepares to ride.\n")


async def do_dismount(session: "GameSession") -> None:
    """DISMOUNT — dismount the party."""
    session._mounted = False
    await session.send("  The party dismounts.\n")


async def do_horses(session: "GameSession") -> None:
    """HORSES — show horse count."""
    count = horse_count(session)
    party_size = 1 + len(session.party)
    ratio = min(1.0, count / max(1, party_size)) if session._mounted else 0.0
    reduction_pct = round(MOUNT_STAMINA_REDUCTION * ratio * 100)
    await session.send(
        f"  Horses: {count} | Party: {party_size} | Stamina drain: -{reduction_pct}%\n"
    )
```

- [ ] **Step 2: Update game.py**

Remove `_do_ride`, `_do_dismount`, `_do_horses`, `_horse_count`, `_stamina_multiplier`, `_party_has_cart` methods. Replace with thin delegation:
```python
from server.engine.systems.mounts import horse_count, stamina_multiplier, party_has_cart, do_ride, do_dismount, do_horses
```
Then add forwarding methods:
```python
_horse_count = horse_count
_stamina_multiplier = stamina_multiplier
_party_has_cart = party_has_cart
_do_ride = do_ride
_do_dismount = do_dismount
_do_horses = do_horses
```

- [ ] **Step 3: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: extract mount/cart logic to systems/mounts.py"
```

### Task 4.3: Extract utility skills from game.py

**Files:**
- Create: `server/engine/systems/utility_skills.py`

- [ ] **Step 1: Create utility_skills.py**

```python
# server/engine/systems/utility_skills.py
"""Non-combat skill execution — extracted from GameSession."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.domain.skills import get_skill

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def handle_use_skill(session: "GameSession", skill_id: str) -> None:
    """Handle utility skill usage."""
    skill = get_skill(skill_id)
    if skill is None:
        await session.send(f"  Unknown skill '{skill_id}'. Type SKILLS UTILITY for a list.\n")
        return

    if skill_id not in session.player.unlocked_skills:
        await session.send(
            f"  You haven't unlocked '{skill.name}'. Use SKILLS to see your skill tree.\n"
        )
        return

    if skill.use_context != "utility":
        await session.send(
            f"  '{skill.name}' is a combat skill — use it via your strategy in battle.\n"
        )
        return

    if skill.mp_cost > 0 and session.player.mp < skill.mp_cost:
        await session.send(
            f"  Not enough mana. '{skill.name}' costs {skill.mp_cost} MP "
            f"(you have {session.player.mp}).\n"
        )
        return

    if skill.stamina_cost > 0 and session.player.stamina < skill.stamina_cost:
        await session.send(
            f"  Not enough stamina. '{skill.name}' costs {skill.stamina_cost} "
            f"(you have {int(session.player.stamina)}).\n"
        )
        return

    if skill.required_items:
        party_inv: list[str] = list(session.player.inventory)
        for npc in session.party:
            party_inv.extend(npc.inventory)
        for item_id in skill.required_items:
            if item_id not in party_inv:
                await session.send(
                    f"  You need a {item_id} to use '{skill.name}'.\n"
                )
                return

    # Deduct costs
    session.player.mp -= skill.mp_cost
    session.player.stamina -= skill.stamina_cost

    # Consume items
    if skill.consumes_item and skill.required_items:
        for item_id in skill.required_items:
            if item_id in session.player.inventory:
                session.player.inventory.remove(item_id)
                break
            else:
                for npc in session.party:
                    if item_id in npc.inventory:
                        npc.inventory.remove(item_id)
                        break

    # Execute effect
    await execute_utility_effect(session, skill)


async def execute_utility_effect(session: "GameSession", skill) -> None:
    """Execute utility skill effect."""
    effect = skill.effect_type

    if effect == "unlock_door":
        await session.send(
            "  You probe the lock carefully... but there are no locked exits here.\n"
        )
    elif effect == "reveal_traps":
        await session.send("  You scan the room carefully. You detect no hidden traps.\n")
    elif effect == "provide_light":
        base = session.clock.game_minutes_elapsed if session.clock else 0
        session._arcane_light_until = base + 120
        await session.send(
            "  Arcane light fills the room, illuminating everything clearly for 120 game-minutes.\n"
        )
    elif effect == "identify_item":
        await session.send("  You sense the arcane properties of the items around you.\n")
    elif effect == "bless_camp":
        session._bless_camp_active = True
        await session.send(
            "  You bless the camp. Your next rest will reduce hunger drain by 50%.\n"
        )
    elif effect == "purify_food":
        await session.send("  You purify the food in your pack.\n")
    elif effect == "fortify_party":
        session._fortify_active = True
        await session.send(
            "  You bolster the party's defenses. Incoming damage will be reduced until your next battle.\n"
        )
    else:
        await session.send(f"  You use {skill.name}.\n")
```

- [ ] **Step 2: Update game.py**

Remove `_handle_use_skill` and `_execute_utility_effect` methods. Replace with delegation:
```python
from server.engine.systems.utility_skills import handle_use_skill, execute_utility_effect

_handle_use_skill = handle_use_skill
_execute_utility_effect = execute_utility_effect
```

- [ ] **Step 3: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: extract utility skills to systems/utility_skills.py"
```

---

## Phase 5: Combat Layer (A4, A5, A6, A11, A16)

Create `engine/combat/` package. Split combat.py into session, actions, strategy, grid, rewards. Decouple from GameSession.

### Task 5.1: Create combat package with actions.py and grid.py

**Files:**
- Create: `server/engine/combat/__init__.py`
- Create: `server/engine/combat/actions.py`
- Create: `server/engine/combat/grid.py`

- [ ] **Step 1: Create combat directory and copy actions.py**

```bash
mkdir -p server/engine/combat
cp server/engine/actions.py server/engine/combat/actions.py
```

- [ ] **Step 2: Create grid.py with position assignment logic**

```python
# server/engine/combat/grid.py
"""Combat position grid — extracted from combat.py."""
from __future__ import annotations

from typing import Any

FRONT_ROW = 0
BACK_ROW = 1
MELEE_CLASSES = {"warrior", "thief"}
RANGED_WEAPON_TYPES = {"bow", "staff"}
MAX_GRID_SLOTS = 6


class CombatTooManyMembers(Exception):
    """Raised when party+enemies exceeds grid capacity."""
    pass


def assign_positions(party_members: list[Any]) -> list[tuple[int, int]]:
    """Assign grid positions (row, col) to party members.
    
    Melee classes go to FRONT row, ranged/casters to BACK row.
    Raises CombatTooManyMembers if more than MAX_GRID_SLOTS members.
    """
    if len(party_members) > MAX_GRID_SLOTS:
        raise CombatTooManyMembers(
            f"Too many combatants ({len(party_members)}). Grid capacity is {MAX_GRID_SLOTS}."
        )

    front_count = [0]
    back_count = [0]

    def _next_front() -> int:
        col = front_count[0]
        front_count[0] += 1
        return min(col, 2)

    def _next_back() -> int:
        col = back_count[0]
        back_count[0] += 1
        return min(col, 2)

    positions = []
    for member in party_members:
        class_type = getattr(member, 'class_type', 'warrior')
        is_melee = class_type in MELEE_CLASSES

        # Check if ranged weapon forces back row
        if hasattr(member, 'equipment'):
            weapon = member.equipment.get("weapon")
            if weapon and weapon.get("weapon_type") in RANGED_WEAPON_TYPES:
                is_melee = False

        if is_melee:
            positions.append((FRONT_ROW, _next_front()))
        else:
            positions.append((BACK_ROW, _next_back()))

    return positions
```

- [ ] **Step 3: Update imports in actions.py**

In `server/engine/combat/actions.py` — no internal engine imports needed (it's self-contained dataclasses).

- [ ] **Step 4: Update all action imports across codebase**

```bash
rg -l "from server.engine.actions import" server/ tests/ --type py
```
Replace with `from server.engine.combat.actions import`

- [ ] **Step 5: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: move actions and create combat/grid.py (A11)"
```

### Task 5.2: Convert strategy.py to enum-based dispatch (A5)

**Files:**
- Create: `server/engine/combat/strategy.py`

- [ ] **Step 1: Create strategy.py with StrategyAction enum**

```python
# server/engine/combat/strategy.py
"""NPC combat strategy — enum-based action dispatch."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from server.engine.combat.actions import Attack, Defend, Flee, UseSkill, UseItem
from server.engine.domain.skills import get_skill


class StrategyActionType(Enum):
    """Types of actions a combatant can perform."""
    ATTACK = auto()
    DEFEND = auto()
    FLEE = auto()
    USE_SKILL = auto()
    USE_ITEM = auto()


@dataclass
class StrategyAction:
    """Typed result of evaluating a strategy."""
    action_type: StrategyActionType
    skill_id: str | None = None
    item_id: str | None = None
    target: Any = None


# ── Strategy management (unchanged from old strategy.py) ────────────────────

def add_strategy(combatant, slot: int, action_text: str, skill_id: str, target: str) -> str:
    """Add a strategy rule to a combatant's strategy list."""
    if combatant.strategies is None:
        combatant.strategies = {}
    combatant.strategies[slot] = {
        "condition": action_text,
        "skill_id": skill_id,
        "target": target,
    }
    return f"Strategy slot {slot} set: {action_text} → {skill_id} ({target})"


def remove_strategy(combatant, slot: int) -> str:
    """Remove a strategy rule."""
    if hasattr(combatant, 'strategies') and combatant.strategies:
        removed = combatant.strategies.pop(slot, None)
        if removed is not None:
            return f"Strategy slot {slot} cleared."
    return f"No strategy in slot {slot}."


def list_strategies(combatant) -> list[str]:
    """Return a list of strategy descriptions."""
    if not hasattr(combatant, 'strategies') or not combatant.strategies:
        return ["(no strategies set)"]
    lines = []
    for slot in sorted(combatant.strategies.keys()):
        rule = combatant.strategies[slot]
        lines.append(
            f"  [{slot}] When {rule['condition']} → {rule['skill_id']} "
            f"(target: {rule['target']})"
        )
    return lines


def clear_strategies(combatant) -> None:
    """Remove all strategies."""
    if hasattr(combatant, 'strategies'):
        combatant.strategies.clear()


def evaluate_strategy(combatant, allies, enemies) -> StrategyAction:
    """Evaluate a combatant's strategy and return a typed StrategyAction.
    
    Replaces string-based dispatch (A5).
    """
    # Check if combatant has strategies
    strategies = getattr(combatant, 'strategies', {}) or {}

    # Find targets
    alive_enemies = [e for e in enemies if getattr(e, 'is_alive', True)]
    if not alive_enemies:
        return StrategyAction(action_type=StrategyActionType.ATTACK)

    # Default: basic attack
    default_action = StrategyAction(action_type=StrategyActionType.ATTACK)

    if not strategies:
        return default_action

    # Evaluate strategies in priority order
    for slot in sorted(strategies.keys()):
        rule = strategies[slot]
        condition = rule.get("condition", "")
        skill_id = rule.get("skill_id", "")
        target = rule.get("target", "closest")

        chosen_target = None
        if target == "closest" and alive_enemies:
            chosen_target = alive_enemies[0]
        elif target == "weakest" and alive_enemies:
            chosen_target = min(alive_enemies, key=lambda e: getattr(e, 'hp', 999))
        elif target == "strongest" and alive_enemies:
            chosen_target = max(alive_enemies, key=lambda e: getattr(e, 'hp', 0))
        elif target == "self":
            chosen_target = combatant
        elif target == "ally" and allies:
            # Prefer lowest-HP ally
            chosen_target = min(allies, key=lambda a: getattr(a, 'hp', 999))

        # Check conditions
        if condition == "always":
            if skill_id:
                skill = get_skill(skill_id)
                if skill and combatant.mp >= skill.mp_cost:
                    return StrategyAction(
                        action_type=StrategyActionType.USE_SKILL,
                        skill_id=skill_id,
                        target=chosen_target,
                    )
            return default_action

        elif condition == "hp_below_50":
            if combatant.hp < combatant.max_hp / 2:
                if skill_id:
                    skill = get_skill(skill_id)
                    if skill and combatant.mp >= skill.mp_cost:
                        return StrategyAction(
                            action_type=StrategyActionType.USE_SKILL,
                            skill_id=skill_id,
                            target=chosen_target,
                        )
                return default_action

        elif condition == "mp_below_25":
            if hasattr(combatant, 'mp') and hasattr(combatant, 'max_mp'):
                if combatant.mp < combatant.max_mp / 4:
                    return StrategyAction(action_type=StrategyActionType.ATTACK)
                return default_action

        elif condition == "ally_hp_below_50":
            for ally in allies:
                if ally.hp < ally.max_hp / 2:
                    if skill_id:
                        skill = get_skill(skill_id)
                        if skill and combatant.mp >= skill.mp_cost:
                            return StrategyAction(
                                action_type=StrategyActionType.USE_SKILL,
                                skill_id=skill_id,
                                target=ally,
                            )
                    return default_action

        elif condition == "flee":
            return StrategyAction(action_type=StrategyActionType.FLEE)

    return default_action
```

- [ ] **Step 2: Update all strategy imports**

```bash
rg -l "from server.engine.strategy import" server/ tests/ --type py
```
Replace with `from server.engine.combat.strategy import`

- [ ] **Step 3: Update combat.py's _do_action to use enum dispatch**

The combat session dispatch switches from string `.startswith()` checks to `match/case` on `StrategyActionType` (will be done in Task 5.3).

- [ ] **Step 4: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: convert strategy to enum-based dispatch (A5)"
```

### Task 5.3: Restructure CombatSession — decouple from GameSession (A4, A6)

**Files:**
- Create: `server/engine/combat/session.py`
- Create: `server/engine/combat/rewards.py`

- [ ] **Step 1: Create rewards.py**

```python
# server/engine/combat/rewards.py
"""Combat rewards — loot, XP, gold distribution."""
from __future__ import annotations

import random
from typing import Any


def collect_rewards(player_party: list[Any], enemy_party: list[Any], class_defs: dict) -> dict:
    """Calculate and distribute combat rewards.
    
    Returns: {"xp": total_xp, "gold": total_gold, "loot": all_loot}
    """
    total_xp = 0
    total_gold = 0
    all_loot: list[str] = []

    for enemy in enemy_party:
        if hasattr(enemy, 'xp_reward'):
            total_xp += enemy.xp_reward
        if hasattr(enemy, 'gold_range'):
            total_gold += random.randint(*enemy.gold_range)
        if hasattr(enemy, 'roll_loot'):
            all_loot.extend(enemy.roll_loot())

    # Distribute XP and gold equally among living party members
    alive = [m for m in player_party if getattr(m, 'is_alive', True)]
    if alive:
        xp_each = total_xp // len(alive)
        gold_each = total_gold // len(alive)
        for member in alive:
            member.xp += xp_each
            member.gold += gold_each
            member.check_level_up()

    return {"xp": total_xp, "gold": total_gold, "loot": all_loot}
```

- [ ] **Step 2: Create decoupled CombatSession in combat/session.py**

This is the largest single task. The key change is removing `on_end` callback and having `run_and_get_result()` return a `CombatResult` instead of calling back into GameSession.

```python
# server/engine/combat/session.py
"""Real-time combat session — decoupled from GameSession (A4)."""
from __future__ import annotations

import asyncio
import logging
import math
import random
from typing import Any

from server.config import (
    BASE_COOLDOWN_TICKS,
    COMBAT_INITIAL_DELAY,
    COMBAT_MIN_SLEEP,
    CRITICAL_DAMAGE_MULTIPLIER,
    CRITICAL_HIT_CHANCE,
    FLEE_SUCCESS_RATE,
    STAMINA_DRAIN_FLEE,
)
from server.engine.combat.actions import Attack, Defend, Flee, UseSkill, UseItem, CombatResult
from server.engine.combat.grid import assign_positions, CombatTooManyMembers
from server.engine.combat.strategy import evaluate_strategy, StrategyActionType
from server.engine.domain.items import equipped_weapon
from server.engine.domain.skills import get_skill

logger = logging.getLogger(__name__)

# Casters fall back to basic spells when MP is insufficient for strategy spells
CASTER_BASIC_SPELLS: dict[str, str] = {
    "mage": "arcane_bolt",
    "cleric": "smite",
}


class CombatSession:
    """Real-time tick-based battle between two parties.

    Decoupled from GameSession — no callbacks. Caller inspects result.
    """

    def __init__(
        self,
        player_party: list[Any],
        enemy_party: list[Any],
        send: Any,
        lighting: float = 1.0,
        survival_multiplier: float = 1.0,
    ):
        self.player_party = player_party
        self.enemy_party = enemy_party
        self.send = send
        self.lighting = lighting
        self.survival_multiplier = survival_multiplier

        self._lock = asyncio.Lock()
        self._phase: str = "FIGHTING"  # FIGHTING | VICTORY | DEFEAT
        self._summary: list[str] = []

    # ── Main entry point ─────────────────────────────────────────────────────

    async def run_and_get_result(self) -> CombatResult:
        """Run combat loop to completion. Returns CombatResult for caller to handle."""
        try:
            self._setup_grid()
        except CombatTooManyMembers as e:
            await self.send(f"\n  Combat error: {e}\n")
            return CombatResult(state="defeat", summary=[str(e)])

        self._setup_cooldowns()

        # Combat loop
        while True:
            async with self._lock:
                if self._phase != "FIGHTING":
                    break

            alive_players = [c for c in self.player_party if getattr(c, 'is_alive', True)]
            alive_enemies = [c for c in self.enemy_party if getattr(c, 'is_alive', True)]

            if not alive_players:
                self._phase = "DEFEAT"
                self._summary.append("  All party members have fallen!\n")
                break
            if not alive_enemies:
                self._phase = "VICTORY"
                self._summary.append("  All enemies have been defeated!\n")
                break

            # Process each combatant
            for combatant in alive_players + alive_enemies:
                if getattr(combatant, 'action_cooldown', 0) > 0:
                    combatant.action_cooldown = max(
                        0, combatant.action_cooldown - COMBAT_MIN_SLEEP
                    )
                    continue

                # Evaluate and execute action
                await self._execute_turn(combatant, alive_players, alive_enemies)

            await asyncio.sleep(COMBAT_MIN_SLEEP)

        return CombatResult(
            state="victory" if self._phase == "VICTORY" else "defeat",
            summary=self._summary,
        )

    # ── Setup ────────────────────────────────────────────────────────────────

    def _setup_grid(self) -> None:
        """Assign combat grid positions."""
        all_combatants = list(self.player_party) + list(self.enemy_party)
        positions = assign_positions(all_combatants)
        for combatant, (row, col) in zip(all_combatants, positions):
            if hasattr(combatant, '__dict__'):
                combatant.grid_row = row
                combatant.grid_col = col

    def _setup_cooldowns(self) -> None:
        """Calculate initial action cooldowns based on speed."""
        for combatant in self.player_party + self.enemy_party:
            speed = getattr(combatant, 'effective_speed', 1)
            combatant.action_cooldown = BASE_COOLDOWN_TICKS / max(1, speed)

    # ── Turn execution ───────────────────────────────────────────────────────

    async def _execute_turn(self, combatant, allies, enemies) -> None:
        """Evaluate strategy and execute the resulting action."""
        action = evaluate_strategy(combatant, allies, enemies)

        match action.action_type:
            case StrategyActionType.ATTACK:
                await self._do_attack(combatant, enemies)
            case StrategyActionType.DEFEND:
                await self._do_defend(combatant)
            case StrategyActionType.FLEE:
                await self._do_flee(combatant)
            case StrategyActionType.USE_SKILL:
                await self._do_use_skill(combatant, action.skill_id, action.target, allies, enemies)
            case StrategyActionType.USE_ITEM:
                await self._do_use_item(combatant, action.item_id, action.target)

    # ── Action handlers ──────────────────────────────────────────────────────

    async def _do_attack(self, attacker, enemies) -> None:
        """Execute a basic attack."""
        alive = [e for e in enemies if getattr(e, 'is_alive', True)]
        if not alive:
            return
        target = alive[0]

        weapon = equipped_weapon(attacker) if callable(equipped_weapon) else None
        dmg_range = (1, 4)  # default unarmed
        if weapon:
            dmg_range = getattr(weapon, 'damage_range', (1, 4))

        # Lighting penalty
        light_penalty = 1.0
        if self.lighting < 0.40 and not getattr(attacker, 'darkvision', False):
            light_penalty = 0.5

        damage = int(random.randint(*dmg_range) * self.survival_multiplier * light_penalty)

        # Crit check
        is_crit = random.random() < CRITICAL_HIT_CHANCE
        if is_crit:
            damage = int(damage * CRITICAL_DAMAGE_MULTIPLIER)

        target.hp = max(0, target.hp - damage)

        crit_text = " ***CRITICAL HIT!***" if is_crit else ""
        self._summary.append(
            f"  {attacker.name} attacks {target.name} for {damage} damage!{crit_text}"
        )
        await self.send(
            f"  {attacker.name} attacks {target.name} for {damage} damage!{crit_text}\n"
        )

    async def _do_defend(self, defender) -> None:
        """Execute a defend action."""
        self._summary.append(f"  {defender.name} defends!")
        await self.send(f"  {defender.name} takes a defensive stance.\n")

    async def _do_flee(self, combatant) -> None:
        """Attempt to flee."""
        if random.random() < FLEE_SUCCESS_RATE:
            if hasattr(combatant, 'stamina'):
                combatant.stamina = max(0, combatant.stamina - STAMINA_DRAIN_FLEE)
            self._summary.append(f"  {combatant.name} fled successfully!")
            await self.send(f"  {combatant.name} flees from combat!\n")
            # Mark as defeated for this combat
            if hasattr(combatant, 'hp'):
                combatant.hp = 0
        else:
            self._summary.append(f"  {combatant.name} failed to flee!")
            await self.send(f"  {combatant.name} tries to flee but fails!\n")

    async def _do_use_skill(self, caster, skill_id, target, allies, enemies) -> None:
        """Execute a combat skill."""
        skill = get_skill(skill_id)
        if not skill:
            await self._do_attack(caster, enemies)
            return

        if caster.mp < skill.mp_cost:
            # Fall back to basic spell for casters
            class_type = getattr(caster, 'class_type', '')
            basic = CASTER_BASIC_SPELLS.get(class_type)
            if basic and basic != skill_id:
                basic_skill = get_skill(basic)
                if basic_skill and caster.mp >= basic_skill.mp_cost:
                    await self._do_use_skill(caster, basic, target, allies, enemies)
                    return
            await self._do_attack(caster, enemies)
            return

        caster.mp -= skill.mp_cost

        # Determine target
        if target is None:
            if skill.target_type == "ally":
                target = min(allies, key=lambda a: a.hp) if allies else caster
            else:
                alive = [e for e in enemies if getattr(e, 'is_alive', True)]
                target = alive[0] if alive else None

        if target is None:
            return

        # Calculate damage/heal
        power = getattr(skill, 'power', 10)
        if skill.effect_type == "heal":
            amount = power
            target.hp = min(target.max_hp, target.hp + amount)
            self._summary.append(f"  {caster.name} heals {target.name} for {amount} HP!")
            await self.send(f"  {caster.name} casts {skill.name} — heals {target.name} for {amount} HP!\n")
        else:
            damage = power
            target.hp = max(0, target.hp - damage)
            self._summary.append(f"  {caster.name} casts {skill.name} on {target.name} for {damage} damage!")
            await self.send(f"  {caster.name} casts {skill.name} on {target.name} for {damage} damage!\n")

    async def _do_use_item(self, user, item_id, target) -> None:
        """Execute using a consumable item."""
        # Simplified — full item effect dispatch uses ItemEffect enum (A16)
        from server.engine.item_effects import parse_item_effect
        if item_id not in user.inventory:
            return
        user.inventory.remove(item_id)
        item = get_skill(item_id)  # use get_item
        from server.engine.domain.items import get_item as gi
        item = gi(item_id)
        if not item:
            return
        effect = parse_item_effect(item.effect_type, item.effect_params)
        # Use item_effects dispatch (was string matching)
```

- [ ] **Step 3: Update combat handler to use new CombatSession API (A4)**

Update `server/engine/states/combat.py` to remove `on_end` callback usage:
```python
# In CombatHandler.on_enter():
combat = CombatSession(
    player_party=player_party,
    enemy_party=enemy_npcs,
    send=session.send,
    lighting=lighting,
    survival_multiplier=survival_mult,
)
result = await combat.run_and_get_result()
await session.send("\n".join(result.summary))
if result.state == "victory":
    encounter_group.mark_defeated()
    from server.engine.combat.rewards import collect_rewards
    collect_rewards(player_party, enemy_npcs, session.class_defs)
    await self._handle_victory(session)
else:
    await self._handle_defeat(session)
```

- [ ] **Step 4: Update all combat imports**

```bash
rg -l "from server.engine.combat import" server/ tests/ --type py
```
Update to use `from server.engine.combat.session import`

- [ ] **Step 5: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
Note: Combat tests will need updates. Fix them incrementally.
```bash
git add -A && git commit -m "refactor: restructure CombatSession into combat/ package (A4, A6, A16)"
```

---

## Phase 6: GameSession Cleanup (A9, A13)

Remove backward-compatible wrappers. Delete duplicated methods. Fix light persistence and error handling.

### Task 6.1: Remove backward-compatible wrappers from game.py

**Files:**
- Modify: `server/engine/game.py` (major reduction)

- [ ] **Step 1: Remove all backward-compatible wrappers and duplicated methods**

Remove from game.py:
- Lines 508-600: `_do_move`, `_do_look`, `_do_pick_up` (wrappers for NavigationHandler)
- Lines 526-563: `_start_combat` (moved to CombatHandler)
- Lines 565-575: `_end_combat_victory`, `_end_combat_defeat` (wrappers)
- Lines 577-633: `_sitting_stamina_tick`, `_drain_survival_tick`, etc. (wrappers)
- Lines 699-710: Duplicate `_handle_campfire` methods
- Lines 711-823: `_do_ride`, `_do_dismount`, `_do_horses`, `_do_attack`, `_do_talk`, `_do_say`, `_do_emote`, `_do_shout` (moved to respective packages)
- Lines 1009-1033: `_do_inventory`, `_do_equip`, etc. (wrappers)

Keep only:
- `__init__`, `send`, `_send`, `broadcast_to_room`, `save`, `_load_save`
- `state` property, `transition_to`, `handle_input`, `start`, `_do_quit`
- Clock subscription/unsubscription
- `_send_help`, `_try_recruit_response`
- Utility skill delegation lines (to keep existing callers working)
- Delegation to extracted modules

- [ ] **Step 2: Update callers that used the wrappers**

Search for test files that call `session._do_move()`, `session._do_look()`, etc.:
```bash
rg "_do_move|_do_look|_do_pick_up|_start_combat|_end_combat" tests/ --type py
```

Update test callers to use:
- `from server.engine.states.navigation import NavigationHandler` → call handler methods directly
- Or `from server.engine.states.combat import CombatHandler`

- [ ] **Step 3: Run tests, fix breakages incrementally**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: remove backward-compatible wrappers from game.py"
```

### Task 6.2: Fix light source persistence (A9)

**Files:**
- Modify: `server/engine/domain/character.py`
- Modify: `server/engine/persistence.py`

- [ ] **Step 1: Add lit_sources to Character serialization**

In `server/engine/domain/character.py`, add `lit_sources` to `to_dict()`:
```python
def to_dict(self) -> dict:
    data = {
        # ... existing fields ...
        "lit_sources": self.lit_sources,  # {item_id: expiry_tick}
    }
    return data
```

In `from_dict()`:
```python
@classmethod
def from_dict(cls, data: dict) -> Character:
    char = cls(...)
    char.lit_sources = data.get("lit_sources", {})
    return char
```

- [ ] **Step 2: Add schema version to persistence**

In `server/engine/persistence.py`, update `save_player()`:
```python
def save_player(name: str, data: dict) -> Tuple[bool, str]:
    data["schema_version"] = 2
    # ... existing save logic ...
    return True, ""
```

Update `load_player()`:
```python
def load_player(name: str) -> Tuple[dict | None, str]:
    data = ...  # existing load
    if data and data.get("schema_version", 1) < 2:
        # Migrate: v1 didn't have lit_sources
        data.setdefault("lit_sources", {})
        data["schema_version"] = 2
    return data, ""
```

- [ ] **Step 3: Persist lit_sources in GameSession.save()**

In `server/engine/game.py`, update `save()`:
```python
def save(self) -> None:
    if not self.player:
        return
    data = {
        "character": self.player.to_dict(),
        "party": [npc.to_dict() for npc in self.party],
        "current_room_id": self.current_room_id,
        "last_campfire_room_id": self.last_campfire_room_id,
        "lit_sources": self.player.lit_sources,  # A9: persist light sources
    }
    ok, msg = save_player(self.player.name, data)
    if not ok:
        logger.error(f"Failed to save: {msg}")
```

- [ ] **Step 4: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: persist light sources and add schema versioning (A9, A13)"
```

---

## Phase 7: NavigationHandler Split + Final Polish (A14, A15, A17, A18)

### Task 7.1: Split NavigationHandler into submodules

**Files:**
- Create: `server/engine/states/navigation/` (6 files)
- Modify: `server/engine/states/navigation.py` (reduce to ~150 lines)

- [ ] **Step 1: Create navigation subdirectory and extract inventory commands**

```bash
mkdir -p server/engine/states/navigation
```

Create `server/engine/states/navigation/__init__.py`:
```python
"""Navigation command submodules."""
```

Create `server/engine/states/navigation/inventory.py` with inventory commands extracted from navigation.py: `_do_inventory`, `_do_equip`, `_do_unequip`, `_do_drop`.

Create `server/engine/states/navigation/party.py` with party management: `_do_stats`, `_do_gold`, `_do_skills`, `_do_learn`, `_do_modifiers`, `_do_upgrade`.

Create `server/engine/states/navigation/social.py` with social commands: `_do_say`, `_do_emote`, `_do_shout`, `_do_examine`.

Create `server/engine/states/navigation/interaction.py` with world interaction: `_do_attack`, `_do_talk`, `_do_pick_up`, `_do_give`.

Create `server/engine/states/navigation/mounts.py` with mount commands: `_do_ride`, `_do_dismount`, `_do_horses`, `_do_load_cart`, `_do_unload_cart`.

Create `server/engine/states/navigation/quick_look.py` with look prefs: `_do_lookmode`, `_do_battlelook`.

Each submodule contains standalone async functions taking `(session, args)`.

- [ ] **Step 2: Trim navigation.py to thin coordinator**

Reduce `server/engine/states/navigation.py` to ~150 lines containing:
- Class `NavigationHandler` with `on_enter`, `on_exit`, `handle`
- `DIR_ALIASES`
- `_do_move`, `_do_look` (core navigation)
- Command dict that imports from submodules

- [ ] **Step 3: Run tests and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -5
```
```bash
git add -A && git commit -m "refactor: split NavigationHandler into command submodules"
```

### Task 7.2: Final polish — A14, A15, A17, A18

**Files:**
- Modify: `server/engine/domain/character.py` (A14: split MODIFIER_CATALOGUE)
- Create: validation models (A15)
- Modify: remaining duplicate _box() calls (A17)
- Modify: `server/config.py` (A18: add MAX_LEVEL)

- [ ] **Step 1: Split MODIFIER_CATALOGUE (A14)**

In `server/engine/domain/character.py`, replace flat `MODIFIER_CATALOGUE` with:
```python
from enum import Enum

class ModifierType(Enum):
    WEAPON_HIT = "weapon_hit"
    BLOCK_BONUS = "block_bonus"
    DODGE_BONUS = "dodge_bonus"
    SPELL_INTENSITY = "spell_intensity"

WEAPON_PROFS: dict[str, dict[str, str]] = {
    "sword_prof": {"label": "Sword Proficiency", "weapon_type": "sword"},
    "axe_prof":   {"label": "Axe Proficiency", "weapon_type": "axe"},
    "mace_prof":  {"label": "Mace Proficiency", "weapon_type": "mace"},
    "dagger_prof":{"label": "Dagger Proficiency", "weapon_type": "dagger"},
    "bow_prof":   {"label": "Bow Proficiency", "weapon_type": "bow"},
    "staff_prof": {"label": "Staff Proficiency", "weapon_type": "staff"},
}

DEFENSIVE_PROFS: dict[str, dict[str, str]] = {
    "shield_prof":   {"label": "Shield Proficiency", "type": "block_bonus"},
    "dodge_mastery": {"label": "Dodge Mastery", "type": "dodge_bonus"},
}

SPELL_INTENSIFIERS: dict[str, dict[str, str]] = {
    "fire_intensity":      {"label": "Fire Intensity", "school": "fire"},
    "frost_intensity":     {"label": "Frost Intensity", "school": "frost"},
    "lightning_intensity": {"label": "Lightning Intensity", "school": "lightning"},
    "heal_power":          {"label": "Heal Power", "school": "heal"},
    "curse_intensity":     {"label": "Curse Intensity", "school": "curse"},
    "holy_power":          {"label": "Holy Power", "school": "holy"},
}

# Backward-compatible flat dict for callers that iterate all
MODIFIER_CATALOGUE: dict[str, dict[str, str]] = {}
MODIFIER_CATALOGUE.update({k: {**v, "type": "weapon_hit", "category": "weapon_prof"} for k, v in WEAPON_PROFS.items()})
MODIFIER_CATALOGUE.update({k: {**v, "category": "defensive_prof"} for k, v in DEFENSIVE_PROFS.items()})
MODIFIER_CATALOGUE.update({k: {**v, "type": "spell_intensity", "category": "spell_intensifier"} for k, v in SPELL_INTENSIFIERS.items()})
```

- [ ] **Step 2: Add Pydantic validation for game data (A15)**

Create `server/engine/domain/validation.py`:
```python
"""Pydantic models for validating game data at load time."""
from pydantic import BaseModel, Field
from typing import Optional


class RoomModel(BaseModel):
    id: str
    name: str
    description: str
    zone: str = "default"
    room_type: str = "indoor"
    base_temp_f: int = 70
    exits: dict[str, str] = {}
    items: list[str] = []
    is_campfire: bool = False
    recruitable_npc_ids: list[str] = []


class ItemModel(BaseModel):
    id: str
    name: str
    type: str
    weight: int = 0
    value: int = 0
    description: str = ""
    effect_type: Optional[str] = None
    effect_params: dict = {}


class NPCModel(BaseModel):
    template_id: str
    name: str
    class_type: str = "warrior"
    level: int = 1
    hp: int = 10
    max_hp: int = 10
    is_recruitable: bool = False
    darkvision: bool = False
```

Update `load()` and `load_items()`, `load_npcs()` to validate with Pydantic.

- [ ] **Step 3: Replace remaining inline _box() calls (A17)**

Search for all remaining local `_box()` definitions:
```bash
rg "def _box" server/ --type py
```
Replace each remaining one with `from server.engine.display.formatting import box as _box`

- [ ] **Step 4: Add MAX_LEVEL and validation (A18)**

In `server/config.py`:
```python
MAX_LEVEL: int = 10
```
Validate that `len(XP_TABLE) == MAX_LEVEL + 1` at startup.

In `server/engine/domain/character.py`:
```python
def check_level_up(self) -> None:
    if self.level >= MAX_LEVEL:
        return
    # ... existing level-up logic ...
```

- [ ] **Step 5: Run full test suite and commit**

```bash
. .venv/bin/activate && pytest tests/ -x --tb=short 2>&1 | tail -10
```
```bash
git add -A && git commit -m "refactor: final polish — A14, A15, A17, A18"
```

---

## Summary

### Execution order dependency graph:
```
Phase 1 (Display)  ─────────────────────────────┐
Phase 2 (Domain)   ← depends on Phase 1         │
Phase 3 (World)    ← depends on Phases 1,2      │
Phase 4 (Systems)  ← depends on Phases 1,2,3    │
Phase 5 (Combat)   ← depends on Phases 1,2      │
Phase 6 (Cleanup)  ← depends on Phases 1-5      │
Phase 7 (Polish)   ← depends on Phases 1-6      │
```

Phases 1,2,3,4,5 must run sequentially. Phases 6 and 7 are sequential at the end.

### Test strategy
- Run `pytest tests/ -x --tb=short` after every commit
- Update test imports as files move (bulk find-replace)
- Fix broken tests incrementally — each Phase commit should have passing tests
- `main.py` and `config.py` never change structure — WebSocket API stays stable
