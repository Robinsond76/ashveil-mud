# Combat Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple `CombatSession` from `GameSession`, replace string-based action dispatch with typed `Action` objects, make combat state transitions atomic, and validate grid positioning.

**Architecture:** Introduce an `Action` dataclass hierarchy to replace raw action strings. Replace the `on_end` callback with a `CombatResult` return value from `CombatSession._run()`. Use `asyncio.Event` for atomic state transitions. Add grid bounds validation with explicit error on overflow.

**Tech Stack:** Python 3.x, asyncio, dataclasses (no new dependencies)

**Addresses findings:** A4 (bidirectional coupling), A5 (string-based dispatch), A6 (implicit state machine), A11 (fragile positioning)

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `server/engine/actions.py` | CREATE | `Action` dataclass hierarchy: `Attack`, `Defend`, `Flee`, `UseSkill`, `UseItem` |
| `server/engine/combat.py` | MODIFY | Accept/return `Action` objects; return `CombatResult` instead of callback; atomic state transitions |
| `server/engine/strategy.py` | MODIFY | Return `Action` objects instead of strings |
| `server/engine/game.py` | MODIFY | Handle `CombatResult` return value instead of `on_end` callback |

---

### Task 1: Create Action Dataclass Hierarchy

**Files:**
- Create: `server/engine/actions.py`
- Test: `tests/test_improvement02_actions.py`

- [ ] **Step 1: Write failing test for Action types**

```python
# tests/test_improvement02_actions.py

from server.engine.actions import Attack, Defend, Flee, UseSkill, UseItem


def test_attack_action_has_target():
    a = Attack(target=None)
    assert a.target is None


def test_use_skill_action_has_skill_id():
    a = UseSkill(skill_id="fireball", target=None)
    assert a.skill_id == "fireball"


def test_use_item_action_has_item_id():
    a = UseItem(item_id="health_potion", target=None)
    assert a.item_id == "health_potion"


def test_defend_action():
    a = Defend()
    assert isinstance(a, Defend)


def test_flee_action():
    a = Flee()
    assert isinstance(a, Flee)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement02_actions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.engine.actions'`

- [ ] **Step 3: Implement `actions.py`**

```python
# server/engine/actions.py

from dataclasses import dataclass


@dataclass
class Attack:
    target: object = None  # Character | NPC | None


@dataclass
class Defend:
    pass


@dataclass
class Flee:
    pass


@dataclass
class UseSkill:
    skill_id: str
    target: object = None


@dataclass
class UseItem:
    item_id: str
    target: object = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_improvement02_actions.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/actions.py tests/test_improvement02_actions.py
git commit -m "feat: add Action dataclass hierarchy for typed combat actions"
```

---

### Task 2: Update Strategy Engine to Return Action Objects

**Files:**
- Modify: `server/engine/strategy.py`
- Test: `tests/test_improvement02_actions.py` (extend)

- [ ] **Step 1: Write failing test for strategy returning Action objects**

```python
# Append to tests/test_improvement02_actions.py

from server.engine.actions import Attack, UseSkill, UseItem, Defend, Flee
from server.engine.strategy import evaluate_strategy


def test_evaluate_strategy_returns_action_attack(load_game_data):
    """Default strategy with no rules returns Attack action."""
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")
    c.strategies = []
    action, target = evaluate_strategy(c, [], [])
    assert isinstance(action, Attack)


def test_evaluate_strategy_returns_use_skill(load_game_data):
    """Strategy rule with USE_SKILL returns UseSkill action."""
    from server.engine.character import Character
    c = Character(name="test", class_type="mage")
    c.hp = 100
    c.max_hp = 100
    c.mp = 50
    c.strategies = [
        {"priority": 1, "condition": "ALWAYS", "action": "USE_SKILL", "skill": "fireball", "target": "WEAKEST"}
    ]
    enemies = [Character(name="enemy", class_type="warrior")]
    enemies[0].hp = 30
    action, target = evaluate_strategy(c, [], enemies)
    assert isinstance(action, UseSkill)
    assert action.skill_id == "fireball"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement02_actions.py::test_evaluate_strategy_returns_action_attack -v`
Expected: FAIL — `evaluate_strategy()` still returns a string `"ATTACK"`, not an `Attack` object

- [ ] **Step 3: Update `strategy.py` to return Action objects**

In `server/engine/strategy.py`, change `evaluate_strategy()`:

```python
# At the top of strategy.py:
from server.engine.actions import Attack, Defend, Flee, UseSkill, UseItem

# In evaluate_strategy(), change all return statements:

# Before:
return "ATTACK", target
# After:
return Attack(target=target), target

# Before:
return "DEFEND", None
# After:
return Defend(), None

# Before:
return "FLEE", None
# After:
return Flee(), None

# Before:
return f"USE_SKILL {skill_id}", target
# After:
return UseSkill(skill_id=skill_id, target=target), target

# Before:
return f"USE_ITEM {item_id}", target
# After:
return UseItem(item_id=item_id, target=target), target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_improvement02_actions.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/strategy.py tests/test_improvement02_actions.py
git commit -m "refactor: strategy engine returns Action objects instead of strings"
```

---

### Task 3: Update CombatSession to Accept Action Objects

**Files:**
- Modify: `server/engine/combat.py`
- Test: Run existing combat tests

- [ ] **Step 1: Update `_do_action()` in `combat.py` to accept Action objects**

Replace the string-parsing dispatch (lines 478–572) with isinstance checks:

```python
# In combat.py, update imports:
from server.engine.actions import Attack, Defend, Flee, UseSkill, UseItem

# Replace _do_action() (lines 478-572):
async def _do_action(self, combatant, action, target):
    """Execute a combat action.

    Parameters:
        combatant: Combatant wrapper
        action: Action dataclass instance
        target: resolved target Combatant or None
    """
    if isinstance(action, Defend):
        # Copy existing DEFEND logic from lines 508-525
        combatant.character.defending = True
        await self._send(f"  {combatant.name} takes a defensive stance.\n")
        return

    if isinstance(action, Flee):
        # Copy existing FLEE logic from lines 527-542
        # ... (exact same logic, just triggered by isinstance instead of string match)
        return

    if isinstance(action, UseSkill):
        await self._resolve_skill(combatant, action.skill_id, target)
        return

    if isinstance(action, UseItem):
        await self._resolve_item(combatant, action.item_id, target)
        return

    # Default: Attack
    if target is None:
        target = self._pick_default_target(combatant)
    if target:
        await self._resolve_attack(combatant, target)
```

- [ ] **Step 2: Update `_combatant_loop()` to pass Action objects to `_do_action()`**

In `_combatant_loop()` (lines 427–465), where `evaluate_strategy()` is called, the return value is now an Action object. Pass it directly to `_do_action()`:

```python
# Before:
action_str, target = evaluate_strategy(combatant.character, allies, enemies)
await self._do_action(combatant, action_str, target)

# After (no change needed — evaluate_strategy now returns Action objects,
# and _do_action now accepts them):
action, target = evaluate_strategy(combatant.character, allies, enemies)
await self._do_action(combatant, action, target)
```

- [ ] **Step 3: Run existing combat tests**

Run: `pytest tests/test_phase02_combat_penalties.py tests/test_phase07_wizard_spell_overhaul.py -v`
Expected: All tests PASS

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/combat.py
git commit -m "refactor: CombatSession uses Action objects instead of string parsing"
```

---

### Task 4: Create CombatResult and Remove on_end Callback

**Files:**
- Modify: `server/engine/combat.py`
- Modify: `server/engine/game.py`
- Create: Add `CombatResult` to `server/engine/actions.py`

- [ ] **Step 1: Add CombatResult to actions.py**

```python
# Append to server/engine/actions.py

@dataclass
class CombatResult:
    state: str           # "victory" or "defeat"
    summary: list        # list of summary strings
    rewards: dict = None # {"xp": int, "gold": int, "loot": list[str]} or None
```

- [ ] **Step 2: Update `CombatSession._run()` to return CombatResult instead of calling on_end**

In `combat.py`, change `_run()` (lines 391–425):

```python
# Before (line 423):
await self._on_end(self.state, summary)

# After:
# Remove the await self._on_end(...) call.
# Instead, store the result:
self.result = CombatResult(
    state=self.state.value,
    summary=summary,
    rewards=self._collected_rewards if self.state == CombatState.VICTORY else None,
)
```

- [ ] **Step 3: Update `CombatSession.__init__()` — remove `on_end` parameter**

```python
# Before (lines 169-175):
def __init__(self, player_party, enemy_party, send, on_end, lighting=1.0, survival_multiplier=1.0):
    self._on_end = on_end

# After:
def __init__(self, player_party, enemy_party, send, lighting=1.0, survival_multiplier=1.0):
    self.result = None  # Set after _run() completes
```

- [ ] **Step 4: Add `run_and_get_result()` convenience method**

```python
async def run_and_get_result(self):
    """Run combat to completion and return CombatResult."""
    await self._run()
    return self.result
```

- [ ] **Step 5: Update `game.py` — replace callback with awaited result**

In `game.py`, `_start_combat()` (lines 2533–2577):

```python
# Before:
self._combat = CombatSession(
    player_party=..., enemy_party=..., send=self._send_raw,
    on_end=self._on_combat_end, lighting=..., survival_multiplier=...
)
await self._combat.start()

# After:
self._combat = CombatSession(
    player_party=..., enemy_party=..., send=self._send_raw,
    lighting=..., survival_multiplier=...
)
result = await self._combat.run_and_get_result()

# Handle result directly:
if result.state == "victory":
    await self._end_combat_victory(result)
else:
    await self._end_combat_defeat(result)
```

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/engine/actions.py server/engine/combat.py server/engine/game.py
git commit -m "refactor: replace on_end callback with CombatResult return value"
```

---

### Task 5: Atomic Combat State Transitions

**Files:**
- Modify: `server/engine/combat.py`

- [ ] **Step 1: Add asyncio.Event for state transition guard**

In `CombatSession.__init__()`:

```python
import asyncio

# Add to __init__:
self._ended = asyncio.Event()
```

- [ ] **Step 2: Update `_check_combat_end()` to use atomic set**

```python
# Before (lines 467-474):
def _check_combat_end(self):
    if all(not c.is_alive for c in self._enemy_combatants):
        self.state = CombatState.VICTORY
    elif all(not c.is_alive for c in self._player_combatants):
        self.state = CombatState.DEFEAT

# After:
def _check_combat_end(self):
    if self._ended.is_set():
        return  # Already transitioning — prevent double-fire
    if all(not c.is_alive for c in self._enemy_combatants):
        self.state = CombatState.VICTORY
        self._ended.set()
    elif all(not c.is_alive for c in self._player_combatants):
        self.state = CombatState.DEFEAT
        self._ended.set()
```

- [ ] **Step 3: Update `_combatant_loop()` to check the event**

```python
# In the combatant loop, add early exit:
async def _combatant_loop(self, combatant):
    while self.state == CombatState.ACTIVE and not self._ended.is_set():
        # ... existing loop body
```

- [ ] **Step 4: Run combat tests**

Run: `pytest tests/test_phase02_combat_penalties.py tests/test_phase07_wizard_spell_overhaul.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/combat.py
git commit -m "refactor: atomic combat state transitions with asyncio.Event"
```

---

### Task 6: Grid Position Validation

**Files:**
- Modify: `server/engine/combat.py`
- Test: `tests/test_improvement02_actions.py` (extend)

- [ ] **Step 1: Write failing test for grid overflow**

```python
# Append to tests/test_improvement02_actions.py

from server.engine.combat import CombatSession

MAX_GRID_SLOTS = 6  # 2 rows × 3 cols


def test_assign_positions_rejects_party_over_six(load_game_data):
    """Parties larger than 6 should raise ValueError, not silently drop members."""
    from server.engine.character import Character
    oversized_party = [Character(name=f"c{i}", class_type="warrior") for i in range(7)]
    import pytest
    with pytest.raises(ValueError, match="exceeds.*grid"):
        CombatSession._assign_positions(oversized_party, is_player_side=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_improvement02_actions.py::test_assign_positions_rejects_party_over_six -v`
Expected: FAIL — currently silently clamps

- [ ] **Step 3: Add validation to `_assign_positions()`**

In `combat.py`, `_assign_positions()` (lines 198–264):

```python
@staticmethod
def _assign_positions(party, is_player_side=True):
    MAX_GRID_SLOTS = 6  # 2 rows × 3 columns
    if len(party) > MAX_GRID_SLOTS:
        raise ValueError(
            f"Party of {len(party)} exceeds grid capacity ({MAX_GRID_SLOTS} slots)."
        )
    # ... rest of existing logic
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_improvement02_actions.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/engine/combat.py tests/test_improvement02_actions.py
git commit -m "fix: validate grid positions, reject parties over 6 members"
```
