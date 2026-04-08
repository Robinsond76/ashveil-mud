# Data Model Cleanup — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the Character/NPC data model — create a `Combatant` protocol, move NPC-only fields out of `Character`, add an `owner` field for multiplayer safety, and type item effects.

**Architecture:** Introduce a `Combatant` Protocol that both `Character` and `NPC` satisfy for combat. Move `grid_row`/`grid_col` to the `Combatant` wrapper in `combat.py` (already exists there). Add `owner` field to `Character` for multiplayer ownership guards. Create an `ItemEffect` tagged union for typed item effect handling.

**Tech Stack:** Python 3.x, dataclasses (no new dependencies)

**Addresses findings:** A2 (Character/NPC inheritance leaks), A10 (missing permissions), A14 (skill/modifier complexity), A16 (implicit item effects)

**Prerequisite:** Execute this plan BEFORE Improvement 01 and 02, because both depend on cleaner data boundaries.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `server/engine/protocols.py` | CREATE | `Combatant` Protocol definition |
| `server/engine/item_effects.py` | CREATE | `ItemEffect` dataclass hierarchy |
| `server/engine/character.py` | MODIFY | Remove `grid_row`/`grid_col` defaults from Character; add `owner` field |
| `server/engine/npc.py` | MODIFY | Add `owner` field |
| `server/engine/combat.py` | MODIFY | Use `Combatant` wrapper for grid positions instead of Character fields |
| `server/engine/game.py` | MODIFY | Add ownership guards on mutations |

---

### Task 1: Create Combatant Protocol

**Files:**
- Create: `server/engine/protocols.py`
- Test: `tests/test_improvement03_data_model.py`

- [ ] **Step 1: Write failing test for protocol conformance**

```python
# tests/test_improvement03_data_model.py

def test_character_satisfies_combatant_protocol(load_game_data):
    """Character should satisfy the Combatant protocol."""
    from server.engine.protocols import Combatant
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")
    # Protocol requires: name, hp, max_hp, mp, max_mp, is_alive, equipment, inventory
    assert hasattr(c, "name")
    assert hasattr(c, "hp")
    assert hasattr(c, "max_hp")
    assert hasattr(c, "mp")
    assert hasattr(c, "max_mp")
    assert hasattr(c, "equipment")
    assert hasattr(c, "inventory")


def test_npc_satisfies_combatant_protocol(load_game_data):
    """NPC should satisfy the Combatant protocol."""
    from server.engine.protocols import Combatant
    from server.engine.npc import NPC
    # NPC inherits from Character, so it should also satisfy the protocol
    assert hasattr(NPC, "hp")
    assert hasattr(NPC, "max_hp")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement03_data_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.engine.protocols'`

- [ ] **Step 3: Implement `protocols.py`**

```python
# server/engine/protocols.py

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_improvement03_data_model.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/protocols.py tests/test_improvement03_data_model.py
git commit -m "feat: add Combatant protocol for type-safe combat"
```

---

### Task 2: Move Grid Position Out of Character

**Files:**
- Modify: `server/engine/character.py`
- Modify: `server/engine/combat.py`
- Test: existing combat tests + `tests/test_improvement03_data_model.py` (extend)

- [ ] **Step 1: Write test verifying grid_row/grid_col live on Combatant wrapper, not Character**

```python
# Append to tests/test_improvement03_data_model.py

def test_character_no_longer_has_grid_defaults(load_game_data):
    """grid_row and grid_col should not default on Character — they belong on the combat wrapper."""
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")
    # grid_row/grid_col should still exist for formation persistence,
    # but default to -1 (unplaced)
    assert c.grid_row == -1
    assert c.grid_col == -1
```

- [ ] **Step 2: Verify the `Combatant` dataclass wrapper in combat.py already has `row`/`col`**

Read `combat.py` lines 103–140. The existing `Combatant` wrapper already has `row` and `col` fields. The Character's `grid_row`/`grid_col` are only used for persisting formation preferences. Confirm that `_assign_positions()` writes to the `Combatant.row`/`Combatant.col` wrapper, NOT to `Character.grid_row`/`Character.grid_col`.

If `_assign_positions()` writes to `character.grid_row`, update it to write to the `Combatant` wrapper's `row`/`col` instead.

- [ ] **Step 3: Run combat tests**

Run: `pytest tests/test_phase02_combat_penalties.py tests/test_phase07_wizard_spell_overhaul.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add server/engine/character.py server/engine/combat.py tests/test_improvement03_data_model.py
git commit -m "refactor: grid position managed by combat wrapper, not Character fields"
```

---

### Task 3: Add Owner Field for Multiplayer Safety

**Files:**
- Modify: `server/engine/character.py`
- Modify: `server/engine/npc.py`
- Modify: `server/engine/persistence.py`
- Modify: `server/engine/game.py`
- Test: `tests/test_improvement03_data_model.py` (extend)

- [ ] **Step 1: Write failing test for owner field**

```python
# Append to tests/test_improvement03_data_model.py

def test_character_has_owner_field(load_game_data):
    """Character should have an owner field defaulting to empty string."""
    from server.engine.character import Character
    c = Character(name="Hero", class_type="warrior")
    assert hasattr(c, "owner")
    assert c.owner == ""


def test_owner_persists_in_to_dict(load_game_data):
    """Owner field should appear in Character.to_dict() output."""
    from server.engine.character import Character
    c = Character(name="Hero", class_type="warrior", owner="player1")
    d = c.to_dict()
    assert d["owner"] == "player1"


def test_owner_restored_from_dict(load_game_data):
    """Owner field should be restored by Character.from_dict()."""
    from server.engine.character import Character
    c = Character(name="Hero", class_type="warrior", owner="player1")
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.owner == "player1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement03_data_model.py::test_character_has_owner_field -v`
Expected: FAIL — `owner` field doesn't exist

- [ ] **Step 3: Add `owner` field to `Character` dataclass**

In `server/engine/character.py`, add to the Character dataclass:

```python
owner: str = ""
```

- [ ] **Step 4: Update `to_dict()` and `from_dict()` to include `owner`**

In `to_dict()` (line ~431):
```python
# Add to the returned dict:
"owner": self.owner,
```

In `from_dict()` (line ~470):
```python
# Add when constructing Character:
owner=d.get("owner", ""),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_improvement03_data_model.py -v`
Expected: All tests PASS

- [ ] **Step 6: Add ownership guard to `_do_give()` in `game.py`**

In `game.py`, `_do_give()` (lines 2041–2085), add at the top:

```python
# Verify both source and target members belong to this player
all_members = [self.player] + self.party
source = _find_member(args_source, all_members)
target = _find_member(args_target, all_members)
if source and source.owner and source.owner != self.player.name:
    await self._send_raw("You don't own that party member.\n")
    return
if target and target.owner and target.owner != self.player.name:
    await self._send_raw("You don't own that party member.\n")
    return
```

- [ ] **Step 7: Set owner on character creation**

In `game.py`, `_finalize_character_stats()` (lines 1209–1265), after creating the character:

```python
self.player.owner = self.player.name
```

In `_try_recruit_response()` (lines 2444–2475), when an NPC joins:

```python
npc.owner = self.player.name
```

- [ ] **Step 8: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add server/engine/character.py server/engine/game.py server/engine/persistence.py tests/test_improvement03_data_model.py
git commit -m "feat: add owner field to Character for multiplayer ownership guards"
```

---

### Task 4: Create ItemEffect Dataclass Hierarchy

**Files:**
- Create: `server/engine/item_effects.py`
- Modify: `server/engine/combat.py`
- Test: `tests/test_improvement03_data_model.py` (extend)

- [ ] **Step 1: Write failing test for ItemEffect types**

```python
# Append to tests/test_improvement03_data_model.py

from server.engine.item_effects import HealEffect, RestoreMPEffect, StatusRemoveEffect


def test_heal_effect_has_amount():
    e = HealEffect(amount=50)
    assert e.amount == 50


def test_restore_mp_effect_has_amount():
    e = RestoreMPEffect(amount=30)
    assert e.amount == 30


def test_status_remove_effect_has_status_id():
    e = StatusRemoveEffect(status_id="poison")
    assert e.status_id == "poison"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement03_data_model.py::test_heal_effect_has_amount -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `item_effects.py`**

```python
# server/engine/item_effects.py

from dataclasses import dataclass


@dataclass
class HealEffect:
    amount: int


@dataclass
class RestoreMPEffect:
    amount: int


@dataclass
class StatusRemoveEffect:
    status_id: str


@dataclass
class BuffEffect:
    buff_id: str
    duration_minutes: int


def parse_item_effect(effect_dict):
    """Convert a raw effect dict from JSON into a typed ItemEffect.

    Parameters:
        effect_dict: dict with "type" key and type-specific fields

    Returns:
        HealEffect | RestoreMPEffect | StatusRemoveEffect | BuffEffect | None
    """
    if not effect_dict:
        return None

    et = effect_dict.get("type", "")

    if et == "heal":
        return HealEffect(amount=effect_dict.get("amount", 0))
    if et == "restore_mp":
        return RestoreMPEffect(amount=effect_dict.get("amount", 0))
    if et == "status_remove":
        return StatusRemoveEffect(status_id=effect_dict.get("status_id", ""))
    if et == "buff":
        return BuffEffect(
            buff_id=effect_dict.get("buff_id", ""),
            duration_minutes=effect_dict.get("duration", 0),
        )

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_improvement03_data_model.py -v`
Expected: All tests PASS

- [ ] **Step 5: Update `_resolve_item()` in combat.py to use typed effects**

In `combat.py`, `_resolve_item()` (lines 794–821):

```python
# At top of combat.py:
from server.engine.item_effects import parse_item_effect, HealEffect, RestoreMPEffect, StatusRemoveEffect

# In _resolve_item(), replace the string-based checks:

# Before:
# et = item.get("effect_type", "")
# if et == "heal":
#     ...
# elif et == "restore_mp":
#     ...

# After:
effect = parse_item_effect(item.get("effect"))
if isinstance(effect, HealEffect):
    heal = min(effect.amount, combatant.character.max_hp - combatant.character.hp)
    combatant.character.hp += heal
    await self._send(f"  {combatant.name} uses {item_id} and heals {heal} HP.\n")
elif isinstance(effect, RestoreMPEffect):
    restore = min(effect.amount, combatant.character.max_mp - combatant.character.mp)
    combatant.character.mp += restore
    await self._send(f"  {combatant.name} uses {item_id} and restores {restore} MP.\n")
elif isinstance(effect, StatusRemoveEffect):
    # ... existing status removal logic
    pass
```

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/engine/item_effects.py server/engine/combat.py tests/test_improvement03_data_model.py
git commit -m "feat: add typed ItemEffect hierarchy, replace string-based item effect checks"
```
