# GameSession Decomposition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 1,855-line `GameSession` god object in `server/engine/game.py` into focused modules, each with one clear responsibility.

**Architecture:** Extract six domain modules from `GameSession`: help registry, inventory operations, survival tracking, campfire handling, chat commands, and environment/display. `GameSession` becomes a thin coordinator that delegates to these modules. All modules receive a `send` callback and operate on `Character`/`NPC` objects they're handed — they never import `GameSession`.

**Tech Stack:** Python 3.x, asyncio (no new dependencies)

**Addresses findings:** A1 (god object), A7 (scattered survival logic), A17 (display in domain logic), A19 (implicit sitting recovery)

---

## File Structure

After this improvement, the `server/engine/` directory gains these new files:

| File | Responsibility | Extracted From |
|------|---------------|----------------|
| `server/engine/help_registry.py` | `_HELP_TOPICS` dict + `_send_help()` lookup logic | `game.py` lines 72–690, 3224–3242 |
| `server/engine/inventory_ops.py` | `_do_inventory`, `_do_equip`, `_do_unequip`, `_do_drop`, `_do_pick_up`, `_do_give`, `_do_load_cart`, `_do_unload_cart`, `_auto_assign_item` | `game.py` lines 1835–2130 |
| `server/engine/survival.py` | `_drain_survival_tick`, `_sitting_stamina_tick`, `_party_survival_aggregate`, `_apply_survival_penalties`, `_do_eat`, `_do_drink`, `_do_buffs`, `_do_survival_status` | `game.py` lines 813–863, 2267–2397 |
| `server/engine/campfire.py` | `_enter_campfire`, `_handle_campfire`, `_do_formation`, `_do_manage` | `game.py` lines 2631–2906 |
| `server/engine/chat.py` | `_do_say`, `_do_emote`, `_do_shout` | `game.py` lines 1601–1638 |
| `server/engine/environment.py` | `_do_time`, `_do_weather`, `_do_light`, `_do_envdetails`, `_do_light_source`, `_carried_light`, `_effective_light` | `game.py` lines 865–907, 2948–3124 |

`server/engine/game.py` retains:
- `GameSession.__init__()`, `start()`, `handle_input()`, `_handle_connect()`, `_handle_creation()`, `_handle_stat_input()`, `_handle_navigation()` dispatcher (now thin — delegates to modules), `_do_move()`, `_do_look()`, `_do_examine()`, `_do_attack()`, `_start_combat()`, combat end handlers, `_save()`, `_load_save()`

---

### Task 1: Extract Help Registry

**Files:**
- Create: `server/engine/help_registry.py`
- Modify: `server/engine/game.py`
- Test: `tests/test_phase08_help_system.py` (existing — must still pass)

- [ ] **Step 1: Create `help_registry.py` with the topics dict and lookup function**

```python
# server/engine/help_registry.py

# Move the entire _HELP_TOPICS dict from game.py lines 72-690 here.
# Keep the exact same dict structure and content.

_HELP_TOPICS = {
    # ... (copy the full 107-entry dict from game.py lines 72-690)
}


async def send_help(send_fn, topic, state=None):
    """Look up a help topic and send the result via send_fn.

    Parameters:
        send_fn: async callable(str) -> None
        topic: str — the topic name (empty string for general help)
        state: current game state enum (for state-aware help filtering)
    """
    if not topic:
        # Send the general help listing
        lines = ["\\n=== HELP TOPICS ===\\n"]
        for key in sorted(_HELP_TOPICS.keys()):
            lines.append(f"  HELP {key}")
        lines.append("\\nType HELP <topic> for details.\\n")
        await send_fn("\\n".join(lines))
        return

    key = topic.strip().lower()
    entry = _HELP_TOPICS.get(key)
    if entry is None:
        await send_fn(f"Unknown help topic: '{topic}'. Type HELP for a list.\\n")
        return

    await send_fn(entry + "\\n")
```

- [ ] **Step 2: Run existing help tests to verify baseline**

Run: `pytest tests/test_phase08_help_system.py -v`
Expected: All ~185 tests PASS (baseline before changes)

- [ ] **Step 3: Update `game.py` — remove `_HELP_TOPICS` dict and import from `help_registry`**

In `game.py`, delete the `_HELP_TOPICS` dict (lines 72–690) and the `_send_help()` method (lines 3224–3242). Replace with:

```python
from server.engine.help_registry import send_help
```

In `_handle_navigation()` where `HELP` is dispatched, change:
```python
# Before:
await self._send_help(args)

# After:
await send_help(self._send_raw, args, self.state)
```

- [ ] **Step 4: Run help tests to verify extraction didn't break anything**

Run: `pytest tests/test_phase08_help_system.py -v`
Expected: All ~185 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/engine/help_registry.py server/engine/game.py
git commit -m "refactor: extract help registry from GameSession"
```

---

### Task 2: Extract Inventory Operations

**Files:**
- Create: `server/engine/inventory_ops.py`
- Modify: `server/engine/game.py`
- Test: `tests/test_phase05_inventory_weight.py` (existing — must still pass)

- [ ] **Step 1: Create `inventory_ops.py` with all inventory functions**

Extract these methods from `GameSession` into standalone async functions that accept explicit parameters instead of `self`:

```python
# server/engine/inventory_ops.py

from server.engine.items import get_item, ITEM_REGISTRY
from server.engine.character import Character


async def do_inventory(send_fn, player, party):
    """Show party inventory. Extracted from GameSession._do_inventory (lines 1857-1925)."""
    # Copy logic from game.py lines 1857-1925
    # Replace self._send_raw with send_fn
    # Replace self.player with player
    # Replace self.party with party
    pass


async def do_equip(send_fn, player, party, args):
    """Equip an item on a party member. Extracted from GameSession._do_equip (lines 1927-1949)."""
    pass


async def do_unequip(send_fn, player, party, args):
    """Unequip an item from a party member. Extracted from GameSession._do_unequip (lines 1951-1965)."""
    pass


async def do_drop(send_fn, player, party, room, args):
    """Drop item in current room. Extracted from GameSession._do_drop (lines 1967-1985)."""
    pass


async def do_pick_up(send_fn, player, party, room, args):
    """Pick up item from room. Extracted from GameSession._do_pick_up (lines 1987-2014)."""
    pass


def auto_assign_item(player, party, item_id):
    """Auto-assign item to best party member. Extracted from GameSession._auto_assign_item (lines 2016-2031)."""
    pass


async def auto_assign_item_with_message(send_fn, player, party, item_id):
    """Auto-assign and notify. Extracted from GameSession._auto_assign_item_with_message (lines 2033-2039)."""
    pass


async def do_give(send_fn, player, party, args):
    """Transfer item between party members. Extracted from GameSession._do_give (lines 2041-2085)."""
    pass


async def do_load_cart(send_fn, player, party, cart_inventory, room, args):
    """Store item in cart. Extracted from GameSession._do_load_cart (lines 2087-2106)."""
    pass


async def do_unload_cart(send_fn, player, party, cart_inventory, args):
    """Retrieve item from cart. Extracted from GameSession._do_unload_cart (lines 2108-2130)."""
    pass
```

- [ ] **Step 2: Copy the exact logic from each `GameSession` method into the new functions**

For each function, copy the method body from `game.py`, replacing:
- `self._send_raw(...)` → `await send_fn(...)`
- `self.player` → `player`
- `self.party` → `party`
- `self.world.get_room(self.current_room_id)` → `room`
- `self._cart_inventory` → `cart_inventory`

- [ ] **Step 3: Update `game.py` — replace inventory methods with delegation**

```python
from server.engine.inventory_ops import (
    do_inventory, do_equip, do_unequip, do_drop, do_pick_up,
    do_give, do_load_cart, do_unload_cart, auto_assign_item,
    auto_assign_item_with_message,
)
```

Replace each old method on GameSession with a thin delegate:
```python
async def _do_inventory(self):
    await do_inventory(self._send_raw, self.player, self.party)
```

- [ ] **Step 4: Run inventory tests**

Run: `pytest tests/test_phase05_inventory_weight.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/engine/inventory_ops.py server/engine/game.py
git commit -m "refactor: extract inventory operations from GameSession"
```

---

### Task 3: Extract Survival System

**Files:**
- Create: `server/engine/survival.py`
- Modify: `server/engine/game.py`
- Test: `tests/test_phase02_drain.py`, `tests/test_phase02_recovery.py`, `tests/test_phase04_commands.py` (existing — must still pass)

- [ ] **Step 1: Create `survival.py` with all survival functions**

Extract these from `GameSession`:

```python
# server/engine/survival.py

def party_survival_aggregate(player, party):
    """Compute aggregate hunger/thirst across the full party.
    Extracted from GameSession._party_survival_aggregate (lines 813-825).
    Returns: tuple(avg_hunger_pct, avg_thirst_pct)
    """
    pass


def apply_survival_penalties(player, party):
    """Compute survival_multiplier and movement_blocked flag.
    Extracted from GameSession._apply_survival_penalties (lines 827-843).
    Returns: tuple(survival_multiplier: float, movement_blocked: bool)
    """
    pass


def drain_survival_tick(player, party, clock, room):
    """Drain hunger/thirst for one game-minute tick.
    Extracted from GameSession._drain_survival_tick (lines 845-852).
    Reads temperature from room and weather from clock.
    """
    pass


def sitting_stamina_tick(player, is_sitting, is_in_combat):
    """Recover stamina if player is sitting and not in combat.
    Extracted from GameSession._sitting_stamina_tick (lines 854-863).
    """
    pass


async def do_eat(send_fn, player, party, clock, args):
    """EAT command handler.
    Extracted from GameSession._do_eat (lines 2280-2327).
    """
    pass


async def do_drink(send_fn, player, party, clock, args):
    """DRINK command handler.
    Extracted from GameSession._do_drink (lines 2329-2377).
    """
    pass


async def do_buffs(send_fn, player, party, clock):
    """BUFFS command handler.
    Extracted from GameSession._do_buffs (lines 2379-2397).
    """
    pass


async def do_survival_status(send_fn, player, party):
    """STATUS command handler.
    Extracted from GameSession._do_survival_status (lines 2267-2278).
    """
    pass
```

- [ ] **Step 2: Copy exact logic from GameSession methods**

Same pattern as Task 2: replace `self.*` references with explicit parameters.

- [ ] **Step 3: Update `game.py` — replace survival methods with delegation**

```python
from server.engine.survival import (
    party_survival_aggregate, apply_survival_penalties,
    drain_survival_tick, sitting_stamina_tick,
    do_eat, do_drink, do_buffs, do_survival_status,
)
```

- [ ] **Step 4: Run survival tests**

Run: `pytest tests/test_phase02_drain.py tests/test_phase02_recovery.py tests/test_phase04_commands.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/engine/survival.py server/engine/game.py
git commit -m "refactor: extract survival system from GameSession"
```

---

### Task 4: Extract Chat Commands

**Files:**
- Create: `server/engine/chat.py`
- Modify: `server/engine/game.py`
- Test: `tests/test_phase09_multiplayer_foundations.py` (existing — must still pass)

- [ ] **Step 1: Create `chat.py` with SAY, EMOTE, SHOUT**

```python
# server/engine/chat.py


async def do_say(send_fn, player_name, room_id, sessions, world, message):
    """Broadcast SAY to all players in the same room.
    Extracted from GameSession._do_say (lines 1601-1611).

    Parameters:
        send_fn: async callable(str) for the speaking player
        player_name: str — who is speaking
        room_id: str — current room ID
        sessions: dict[str, GameSession] — all active sessions
        world: WorldMap — for room_occupants lookup
        message: str — the message text
    """
    text = f"{player_name} says: \"{message}\""
    occupants = world.players_in_room(room_id)
    for name in occupants:
        if name != player_name and name in sessions:
            await sessions[name]._send_raw(text + "\n")
    await send_fn(f"You say: \"{message}\"\n")


async def do_emote(send_fn, player_name, room_id, sessions, world, action):
    """Broadcast EMOTE to all players in the same room.
    Extracted from GameSession._do_emote (lines 1613-1623).
    """
    text = f"* {player_name} {action}"
    occupants = world.players_in_room(room_id)
    for name in occupants:
        if name != player_name and name in sessions:
            await sessions[name]._send_raw(text + "\n")
    await send_fn(text + "\n")


async def do_shout(send_fn, player_name, sessions, message):
    """Broadcast SHOUT/OOC to ALL connected players.
    Extracted from GameSession._do_shout (lines 1625-1638).
    """
    text = f"[OOC] {player_name}: {message}"
    for name, sess in sessions.items():
        if name != player_name:
            await sess._send_raw(text + "\n")
    await send_fn(text + "\n")
```

- [ ] **Step 2: Update `game.py` — replace chat methods with delegation**

```python
from server.engine.chat import do_say, do_emote, do_shout
```

In `_handle_navigation()` SAY branch:
```python
# Before:
await self._do_say(args)

# After:
await do_say(self._send_raw, self.player.name, self.current_room_id,
             self._sessions, self.world, args)
```

- [ ] **Step 3: Run multiplayer tests**

Run: `pytest tests/test_phase09_multiplayer_foundations.py -v`
Expected: All tests PASS

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/chat.py server/engine/game.py
git commit -m "refactor: extract chat commands from GameSession"
```

---

### Task 5: Extract Campfire Handler

**Files:**
- Create: `server/engine/campfire.py`
- Modify: `server/engine/game.py`
- Test: Run full suite (no dedicated campfire tests exist)

- [ ] **Step 1: Create `campfire.py` with campfire state logic**

Extract `_enter_campfire` (lines 2631–2656), `_handle_campfire` (lines 2658–2723), `_do_formation` (lines 2725–2845), and `_do_manage` (lines 2847–2906) from `GameSession`.

```python
# server/engine/campfire.py

from server.engine.character import Character


async def enter_campfire(send_fn, player, party, room):
    """Transition to campfire state. Extracted from lines 2631-2656."""
    pass


async def handle_campfire(send_fn, player, party, cmd, args, *, learn_fn, modifiers_fn, upgrade_fn, save_fn):
    """Dispatch campfire commands. Extracted from lines 2658-2723.

    Callbacks:
        learn_fn: async callable for LEARN command
        modifiers_fn: async callable for MODIFIERS command
        upgrade_fn: async callable for UPGRADE command
        save_fn: async callable for saving the game

    Returns: str — next state transition signal ("leave", "manage <name>", or None)
    """
    pass


async def do_formation(send_fn, player, party, args):
    """View or change battle formation. Extracted from lines 2725-2845."""
    pass


async def do_manage(send_fn, player, party, args):
    """Enter strategy editing for a party member. Extracted from lines 2847-2906.
    Returns: the target Character/NPC to manage, or None if not found.
    """
    pass
```

- [ ] **Step 2: Copy logic, replace self-references with parameters**

- [ ] **Step 3: Update `game.py` — replace campfire methods with delegation**

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/campfire.py server/engine/game.py
git commit -m "refactor: extract campfire handler from GameSession"
```

---

### Task 6: Extract Environment Display

**Files:**
- Create: `server/engine/environment.py`
- Modify: `server/engine/game.py`
- Test: Run full suite

- [ ] **Step 1: Create `environment.py` with environment/display functions**

Extract from `GameSession`:
- `_carried_light()` (lines 865–897) — returns light level from party's lit sources
- `_effective_light()` (lines 899–907) — combines room + carried light
- `_do_time()` (lines 2948–2963) — TIME command
- `_do_weather()` (lines 2965–2984) — WEATHER command
- `_do_light()` (lines 2986–3013) — LIGHT/LIGHTING command
- `_do_envdetails()` (lines 3015–3040) — ENV command
- `_do_light_source()` (lines 3042–3124) — LIT/EXTINGUISH command

```python
# server/engine/environment.py


def carried_light(player, party, lit_sources, clock):
    """Calculate light contribution from party's lit torches/lanterns.
    Extracted from GameSession._carried_light (lines 865-897).
    Returns: float (0.0 to 1.0)
    """
    pass


def effective_light(room, player, party, lit_sources, clock):
    """Combine room ambient light + carried light.
    Extracted from GameSession._effective_light (lines 899-907).
    Returns: float (0.0 to 1.0)
    """
    pass


async def do_time(send_fn, clock):
    """TIME command. Extracted from lines 2948-2963."""
    pass


async def do_weather(send_fn, clock, room):
    """WEATHER command. Extracted from lines 2965-2984."""
    pass


async def do_light(send_fn, player, party, lit_sources, clock, room):
    """LIGHT/LIGHTING command. Extracted from lines 2986-3013."""
    pass


async def do_envdetails(send_fn, player, party, lit_sources, clock, room):
    """ENV command. Extracted from lines 3015-3040."""
    pass


async def do_light_source(send_fn, player, party, lit_sources, clock, item_arg, extinguish=False):
    """LIT/EXTINGUISH command. Extracted from lines 3042-3124.
    Modifies lit_sources dict in place.
    """
    pass
```

- [ ] **Step 2: Copy logic, replace self-references**

- [ ] **Step 3: Update `game.py` — delegate environment commands**

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/environment.py server/engine/game.py
git commit -m "refactor: extract environment display from GameSession"
```

---

### Task 7: Final Cleanup — Slim Down `_handle_navigation()`

**Files:**
- Modify: `server/engine/game.py`

- [ ] **Step 1: Review `_handle_navigation()` (lines 1424–1599)**

After Tasks 1–6, this method should now be a thin dispatcher. Each branch should be a one-liner delegation call. Verify no orphan logic remains inline.

- [ ] **Step 2: Re-measure `game.py` line count**

Run: `python -c "print(sum(1 for _ in open('server/engine/game.py')))"`
Expected: Under 1,000 lines (down from 1,855)

- [ ] **Step 3: Run full test suite one final time**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add server/engine/game.py
git commit -m "refactor: slim down _handle_navigation dispatcher"
```
