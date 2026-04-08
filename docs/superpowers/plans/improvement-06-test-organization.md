# Test Organization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate duplicated test fixtures, parametrize bulk tests, eliminate cross-phase duplication, and standardize naming.

**Architecture:** Move shared helpers (`make_nav_session()`) into `conftest.py`. Replace 185 individual help topic tests with a single parametrized test. Remove EAT/DRINK tests from Phase 2 (they belong in Phase 4). Split oversized test files. Standardize test names to `test_<command>_<scenario>_<expected>` pattern.

**Tech Stack:** Python 3.x, pytest (no new dependencies)

**Addresses findings:** T1 (trivial tests), T6 (EAT/DRINK duplication), T7 (fixture duplication), T8 (unbalanced file sizes), T9 (inconsistent naming)

**Prerequisite:** Execute AFTER architecture improvements (01–05) to avoid restructuring tests twice.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `tests/conftest.py` | MODIFY | Add shared `make_nav_session()` fixture |
| `tests/test_phase08_help_system.py` | MODIFY | Replace 185 individual tests with parametrized tests |
| `tests/test_phase02_character.py` | MODIFY | Consolidate trivial field tests |
| `tests/test_phase02_commands.py` | MODIFY | Remove EAT/DRINK tests (moved to Phase 4) |
| `tests/test_phase03_utility_skills.py` | MODIFY | Use shared fixture |
| `tests/test_phase04_buff_hooks.py` | MODIFY | Use shared fixture |
| `tests/test_phase07_wizard_spell_overhaul.py` | MODIFY | Split into two files |
| `tests/test_phase07_glass_cannon.py` | CREATE | Glass cannon mechanic tests split from phase07 |

---

### Task 1: Consolidate `make_nav_session()` Into conftest.py

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_phase02_commands.py`
- Modify: `tests/test_phase03_utility_skills.py`
- Modify: `tests/test_phase04_buff_hooks.py`

- [ ] **Step 1: Read all three existing `make_nav_session()` helpers**

Read and compare:
- `tests/test_phase02_commands.py` lines 17–32
- `tests/test_phase03_utility_skills.py` lines 26–43
- `tests/test_phase04_buff_hooks.py` lines 24–41

Identify the superset of parameters across all three.

- [ ] **Step 2: Create a unified `make_nav_session()` in conftest.py**

```python
# Append to tests/conftest.py

from unittest.mock import AsyncMock
from server.engine.game import GameSession, State
from server.engine.world import WorldMap
from server.engine.character import Character


@pytest.fixture
def make_nav_session(load_game_data):
    """Factory fixture to create a GameSession in NAVIGATION state.

    Usage:
        session = make_nav_session()
        session = make_nav_session(class_type="mage", mp=50, stamina=80)
        session = make_nav_session(clock=mock_clock)
    """
    def _factory(
        class_type="warrior",
        hp=None,
        mp=None,
        stamina=None,
        hunger=None,
        thirst=None,
        clock=None,
        room_id="town_square",
    ):
        send_fn = AsyncMock()
        world = WorldMap()
        world.load(DATA_DIR)

        from server.engine.world_clock import WorldClock
        if clock is None:
            clock = WorldClock.__new__(WorldClock)
            clock.total_minutes = 0
            clock._hour = 12
            clock._minute = 0

        # Minimal class_defs for creation
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        session = GameSession(
            send_fn=send_fn,
            world=world,
            class_defs=class_defs,
            clock=clock,
            sessions={},
        )
        session.state = State.NAVIGATION

        # Create player
        player = Character(name="TestPlayer", class_type=class_type)
        if hp is not None:
            player.hp = hp
            player.max_hp = max(hp, player.max_hp)
        if mp is not None:
            player.mp = mp
            player.max_mp = max(mp, player.max_mp)
        if stamina is not None:
            player.stamina = stamina
        if hunger is not None:
            player.hunger = hunger
        if thirst is not None:
            player.thirst = thirst

        session.player = player
        session.current_room_id = room_id
        session.party = []

        return session

    return _factory
```

- [ ] **Step 3: Update `test_phase02_commands.py` — remove local helper, use fixture**

```python
# Before:
def make_nav_session(...):
    ...

def test_look_shows_room(self):
    s = make_nav_session()

# After:
def test_look_shows_room(make_nav_session):
    s = make_nav_session()
```

Add `make_nav_session` as a parameter to every test function that uses it.

- [ ] **Step 4: Update `test_phase03_utility_skills.py` — remove local helper, use fixture**

Same pattern: delete the local `make_nav_session()`, add fixture parameter.

- [ ] **Step 5: Update `test_phase04_buff_hooks.py` — remove local helper, use fixture**

Same pattern.

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_phase02_commands.py tests/test_phase03_utility_skills.py tests/test_phase04_buff_hooks.py
git commit -m "refactor: consolidate make_nav_session into conftest.py shared fixture"
```

---

### Task 2: Parametrize Help Topic Tests

**Files:**
- Modify: `tests/test_phase08_help_system.py`

- [ ] **Step 1: Count existing individual test functions**

Run: `pytest tests/test_phase08_help_system.py --collect-only | Select-String "test session" | Measure-Object`
Expected: ~185 tests

- [ ] **Step 2: Replace `TestPhaseA_HelpTopicsDict` (81 individual tests) with parametrized test**

```python
# Before (81 individual functions):
# def test_topic_movement_exists():
#     assert "movement" in _HELP_TOPICS
# def test_topic_combat_exists():
#     assert "combat" in _HELP_TOPICS
# ... (79 more)

# After (1 parametrized test):
import pytest
from server.engine.game import _HELP_TOPICS

EXPECTED_TOPICS = [
    "movement", "combat", "inventory", "equipment", "stats",
    # ... list all 81+ expected topic keys
]

@pytest.mark.parametrize("topic", EXPECTED_TOPICS)
def test_help_topic_exists(topic):
    """Each expected help topic should exist in the _HELP_TOPICS dict."""
    assert topic in _HELP_TOPICS
```

- [ ] **Step 3: Replace `TestPhaseC_TopicLookup` (88 individual tests) with parametrized test**

```python
# Before (88 individual functions):
# def test_help_movement_returns_text():
#     assert len(_HELP_TOPICS["movement"]) > 0
# ... (87 more)

# After (1 parametrized test):
@pytest.mark.parametrize("topic", EXPECTED_TOPICS)
def test_help_topic_has_nonempty_content(topic):
    """Each help topic should have non-empty content."""
    assert topic in _HELP_TOPICS
    assert len(_HELP_TOPICS[topic]) > 10  # Minimum reasonable content
```

- [ ] **Step 4: Keep `TestPhaseB_StateAwareHelp` and `TestPhaseD_UnknownTopic` unchanged**

These 16 tests test behavioral logic, not just dict existence — keep them as-is.

- [ ] **Step 5: Run tests and verify**

Run: `pytest tests/test_phase08_help_system.py -v`
Expected: All pass. Test count should drop from ~185 to ~97+ (parametrized tests count as N per parameter but run faster).

- [ ] **Step 6: Commit**

```bash
git add tests/test_phase08_help_system.py
git commit -m "refactor: parametrize 185 help topic tests into 2 parametrized tests"
```

---

### Task 3: Remove EAT/DRINK Duplication from Phase 2

**Files:**
- Modify: `tests/test_phase02_commands.py`
- (No change to `tests/test_phase04_commands.py` — it already has the comprehensive versions)

- [ ] **Step 1: Identify the duplicated tests in Phase 2**

These tests in `test_phase02_commands.py` are duplicated in `test_phase04_commands.py`:
- `test_eat_with_no_item_gives_feedback()` — line ~31
- `test_eat_food_item_restores_hunger()` — line ~47
- `test_eat_removes_item_from_inventory()` — line ~63
- `test_drink_water_flask_restores_thirst()` — line ~79
- `test_drink_removes_item_from_inventory()` — line ~95

- [ ] **Step 2: Delete the 5 EAT/DRINK tests from `test_phase02_commands.py`**

Remove these 5 test functions entirely. Phase 4 has comprehensive coverage (14 EAT/DRINK tests).

- [ ] **Step 3: Run Phase 4 tests to confirm coverage**

Run: `pytest tests/test_phase04_commands.py -v`
Expected: All 14+ EAT/DRINK tests PASS

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (5 fewer total, but no coverage loss)

- [ ] **Step 5: Commit**

```bash
git add tests/test_phase02_commands.py
git commit -m "refactor: remove EAT/DRINK test duplication from Phase 2 (covered in Phase 4)"
```

---

### Task 4: Consolidate Trivial Field Tests in Phase 2

**Files:**
- Modify: `tests/test_phase02_character.py`

- [ ] **Step 1: Review existing tests**

Tests like:
```python
def test_character_has_hunger_default_100():
    c = Character(name="test", class_type="warrior")
    assert c.hunger == 100.0

def test_character_has_thirst_default_100():
    c = Character(name="test", class_type="warrior")
    assert c.thirst == 100.0
```

- [ ] **Step 2: Replace with a single comprehensive defaults test**

```python
def test_character_initializes_with_survival_defaults(load_game_data):
    """All survival stats should initialize to their max values."""
    from server.engine.character import Character
    c = Character(name="test", class_type="warrior")

    assert c.hunger == 100.0
    assert c.max_hunger == 100.0
    assert c.thirst == 100.0
    assert c.max_thirst == 100.0
    assert c.stamina == 100.0
    assert c.max_stamina == 100.0
```

Keep any tests that test **behavior** (e.g., drain rate calculation, buff application). Only consolidate the pure field-initialization checks.

- [ ] **Step 3: Run test to verify**

Run: `pytest tests/test_phase02_character.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase02_character.py
git commit -m "refactor: consolidate trivial field-init tests into single comprehensive test"
```

---

### Task 5: Split Oversized Phase 7 Test File

**Files:**
- Modify: `tests/test_phase07_wizard_spell_overhaul.py`
- Create: `tests/test_phase07_glass_cannon.py`

- [ ] **Step 1: Identify the split boundary**

Read `tests/test_phase07_wizard_spell_overhaul.py`. Identify tests related to:
- **Glass cannon mechanic** (HP reduction, damage bonus for mage) → move to `test_phase07_glass_cannon.py`
- **Spell casting** (spell data, mana cost, AoE, damage resolution) → keep in `test_phase07_wizard_spell_overhaul.py`

- [ ] **Step 2: Create `test_phase07_glass_cannon.py`**

Move all glass cannon tests to the new file. Include necessary imports and any local fixtures.

- [ ] **Step 3: Verify original file is smaller**

Run: `python -c "print(sum(1 for _ in open('tests/test_phase07_wizard_spell_overhaul.py')))"`
Expected: Under 300 lines (down from 550+)

- [ ] **Step 4: Run both test files**

Run: `pytest tests/test_phase07_wizard_spell_overhaul.py tests/test_phase07_glass_cannon.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_phase07_wizard_spell_overhaul.py tests/test_phase07_glass_cannon.py
git commit -m "refactor: split Phase 7 tests into wizard spells + glass cannon mechanics"
```

---

### Task 6: Standardize Test Names

**Files:**
- Modify: Multiple test files

- [ ] **Step 1: Adopt naming convention**

Convention: `test_<command_or_feature>_<scenario>_<expected_outcome>`

Examples of renames:
```
test_look_shows_stamina_warning_when_zero
  → test_look_zero_stamina_shows_exhaustion_warning

test_mage_spell_power_modifier_adds_staff_bonus
  → test_mage_spell_power_nonzero_with_staff_equipped

test_eat_with_no_item_gives_feedback
  → test_eat_no_food_in_inventory_shows_error_message
```

- [ ] **Step 2: Rename tests in each file**

Only rename tests with misleading or vague names. Do NOT rename tests that already follow the convention. Each rename should be a simple find-replace of the function name.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (names changed, behavior unchanged)

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "refactor: standardize test naming to command_scenario_expected convention"
```
