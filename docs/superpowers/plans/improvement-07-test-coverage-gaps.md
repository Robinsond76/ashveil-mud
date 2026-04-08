# Test Coverage Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill critical test coverage gaps — add tests for untested commands, error paths, async concurrency, status effects, persistence roundtrip, and a full integration flow.

**Architecture:** Add focused test files for each gap area. Use `pytest-asyncio` for async tests. Use proper assertion patterns (exact message matching, not `assert output`). Mock RNG where needed to eliminate non-determinism.

**Tech Stack:** Python 3.x, pytest, pytest-asyncio (add to `requirements.txt` if not present)

**Addresses findings:** T2 (weak assertions), T3 (no error paths), T4 (excessive mocking), T5 (no async tests), T10 (untested commands), T11 (non-determinism), T12 (no integration test), T13 (no persistence roundtrip), T14 (no stress tests)

**Prerequisite:** Execute AFTER Improvement 06 (test organization) so new tests follow the cleaned-up structure.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `tests/test_chat_commands.py` | CREATE | Tests for SAY, EMOTE, SHOUT |
| `tests/test_error_paths.py` | CREATE | Wrong-state commands, malformed input, edge cases |
| `tests/test_persistence_roundtrip.py` | CREATE | Full save/load cycle with complex character data |
| `tests/test_status_effects.py` | CREATE | Status effect application, tick, and expiry |
| `tests/test_integration_flow.py` | CREATE | End-to-end: CONNECT → CREATE → NAVIGATE → FIGHT → REST |
| `tests/test_phase02_combat_penalties.py` | MODIFY | Fix non-deterministic RNG tests |
| `tests/test_phase03_utility_skills.py` | MODIFY | Strengthen weak assertions |
| `requirements.txt` | MODIFY | Add `pytest-asyncio` if missing |

---

### Task 1: Add Chat Command Tests (SAY, EMOTE, SHOUT)

**Files:**
- Create: `tests/test_chat_commands.py`

- [ ] **Step 1: Write SAY tests**

```python
# tests/test_chat_commands.py

import asyncio
import pytest
from unittest.mock import AsyncMock
from server.engine.game import GameSession, State
from server.engine.world import WorldMap
from server.engine.character import Character

DATA_DIR = "server/data"


def _make_multiplayer_sessions(make_nav_session):
    """Create two sessions in the same room with shared sessions dict."""
    sessions = {}

    s1 = make_nav_session(room_id="town_square")
    s1.player = Character(name="Alice", class_type="warrior")
    s1.current_room_id = "town_square"
    s1._sessions = sessions

    s2 = make_nav_session(room_id="town_square")
    s2.player = Character(name="Bob", class_type="mage")
    s2.current_room_id = "town_square"
    s2._sessions = sessions

    sessions["Alice"] = s1
    sessions["Bob"] = s2

    # Register both in room_occupants
    s1.world.room_occupants["town_square"] = ["Alice", "Bob"]

    return s1, s2


def test_say_broadcasts_to_same_room(make_nav_session):
    """SAY should send the message to all players in the same room."""
    s1, s2 = _make_multiplayer_sessions(make_nav_session)

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("SAY Hello everyone!")
    )

    # s2 should have received Alice's message
    calls = [str(c) for c in s2._send_raw.call_args_list]
    assert any("Alice" in c and "Hello everyone!" in c for c in calls)


def test_say_shows_confirmation_to_speaker(make_nav_session):
    """SAY should show 'You say:' to the speaker."""
    s1, s2 = _make_multiplayer_sessions(make_nav_session)

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("SAY Hello!")
    )

    calls = [str(c) for c in s1._send_raw.call_args_list]
    assert any("You say" in c for c in calls)


def test_say_empty_message_shows_usage(make_nav_session):
    """SAY with no message should show usage hint."""
    s1, _ = _make_multiplayer_sessions(make_nav_session)

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("SAY")
    )

    calls = [str(c) for c in s1._send_raw.call_args_list]
    assert any("say" in c.lower() for c in calls)
```

- [ ] **Step 2: Write EMOTE tests**

```python
# Append to tests/test_chat_commands.py

def test_emote_broadcasts_action_to_room(make_nav_session):
    """EMOTE should broadcast '* Alice waves' to the room."""
    s1, s2 = _make_multiplayer_sessions(make_nav_session)

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("EMOTE waves hello")
    )

    calls = [str(c) for c in s2._send_raw.call_args_list]
    assert any("Alice" in c and "waves hello" in c for c in calls)


def test_me_alias_works_like_emote(make_nav_session):
    """ME should be an alias for EMOTE."""
    s1, s2 = _make_multiplayer_sessions(make_nav_session)

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("ME nods thoughtfully")
    )

    calls = [str(c) for c in s2._send_raw.call_args_list]
    assert any("Alice" in c and "nods thoughtfully" in c for c in calls)
```

- [ ] **Step 3: Write SHOUT tests**

```python
# Append to tests/test_chat_commands.py

def test_shout_broadcasts_to_all_sessions(make_nav_session):
    """SHOUT should broadcast to ALL connected players, even in different rooms."""
    sessions = {}

    s1 = make_nav_session(room_id="town_square")
    s1.player = Character(name="Alice", class_type="warrior")
    s1.current_room_id = "town_square"
    s1._sessions = sessions

    s2 = make_nav_session(room_id="forest_path")
    s2.player = Character(name="Bob", class_type="mage")
    s2.current_room_id = "forest_path"
    s2._sessions = sessions

    sessions["Alice"] = s1
    sessions["Bob"] = s2

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("SHOUT Anyone out there?")
    )

    calls = [str(c) for c in s2._send_raw.call_args_list]
    assert any("Alice" in c and "Anyone out there?" in c for c in calls)


def test_ooc_alias_works_like_shout(make_nav_session):
    """OOC should be an alias for SHOUT."""
    sessions = {}
    s1 = make_nav_session(room_id="town_square")
    s1.player = Character(name="Alice", class_type="warrior")
    s1._sessions = sessions
    sessions["Alice"] = s1

    asyncio.get_event_loop().run_until_complete(
        s1.handle_input("OOC testing 123")
    )

    calls = [str(c) for c in s1._send_raw.call_args_list]
    assert any("testing 123" in c for c in calls)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_chat_commands.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_chat_commands.py
git commit -m "test: add SAY, EMOTE, SHOUT command test coverage"
```

---

### Task 2: Add Error Path Tests

**Files:**
- Create: `tests/test_error_paths.py`

- [ ] **Step 1: Write tests for wrong-state commands**

```python
# tests/test_error_paths.py

import asyncio
import pytest
from server.engine.game import GameSession, State
from server.engine.character import Character


def test_attack_in_campfire_state_rejected(make_nav_session):
    """ATTACK should be rejected when in CAMPFIRE state."""
    s = make_nav_session()
    s.state = State.CAMPFIRE

    asyncio.get_event_loop().run_until_complete(s.handle_input("ATTACK"))

    calls = [str(c) for c in s._send_raw.call_args_list]
    # Should NOT start combat; should show error or be ignored
    assert s._combat is None


def test_campfire_in_combat_state_rejected(make_nav_session):
    """CAMPFIRE should be rejected while in combat."""
    s = make_nav_session()
    s.state = State.COMBAT

    asyncio.get_event_loop().run_until_complete(s.handle_input("CAMPFIRE"))

    # State should remain COMBAT
    assert s.state == State.COMBAT


def test_move_in_combat_state_rejected(make_nav_session):
    """Movement commands should be rejected in COMBAT state."""
    s = make_nav_session()
    s.state = State.COMBAT
    original_room = s.current_room_id

    asyncio.get_event_loop().run_until_complete(s.handle_input("NORTH"))

    assert s.current_room_id == original_room
```

- [ ] **Step 2: Write tests for malformed input**

```python
# Append to tests/test_error_paths.py

def test_equip_no_args_shows_usage(make_nav_session):
    """EQUIP with no arguments should show usage."""
    s = make_nav_session()

    asyncio.get_event_loop().run_until_complete(s.handle_input("EQUIP"))

    calls = [str(c) for c in s._send_raw.call_args_list]
    assert any("equip" in c.lower() or "usage" in c.lower() for c in calls)


def test_give_no_args_shows_usage(make_nav_session):
    """GIVE with no arguments should show usage."""
    s = make_nav_session()

    asyncio.get_event_loop().run_until_complete(s.handle_input("GIVE"))

    calls = [str(c) for c in s._send_raw.call_args_list]
    assert any("give" in c.lower() or "usage" in c.lower() for c in calls)


def test_unknown_command_shows_error(make_nav_session):
    """A completely unknown command should produce an error message."""
    s = make_nav_session()

    asyncio.get_event_loop().run_until_complete(s.handle_input("TELEPORT"))

    calls = [str(c) for c in s._send_raw.call_args_list]
    assert any(
        "unknown" in c.lower() or "not recognized" in c.lower() or "help" in c.lower()
        for c in calls
    )
```

- [ ] **Step 3: Write tests for edge cases**

```python
# Append to tests/test_error_paths.py

def test_move_with_zero_stamina_blocked(make_nav_session):
    """Movement should be blocked when stamina is 0."""
    s = make_nav_session(stamina=0.0)
    original_room = s.current_room_id

    asyncio.get_event_loop().run_until_complete(s.handle_input("SOUTH"))

    assert s.current_room_id == original_room
    calls = [str(c) for c in s._send_raw.call_args_list]
    assert any("stamina" in c.lower() or "exhausted" in c.lower() for c in calls)


def test_drop_item_not_in_inventory(make_nav_session):
    """DROP with an item not in inventory should show error."""
    s = make_nav_session()
    s.player.inventory = []

    asyncio.get_event_loop().run_until_complete(s.handle_input("DROP excalibur"))

    calls = [str(c) for c in s._send_raw.call_args_list]
    assert any("don't have" in c.lower() or "not found" in c.lower() for c in calls)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_error_paths.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_error_paths.py
git commit -m "test: add error path tests for wrong-state commands and malformed input"
```

---

### Task 3: Add Persistence Roundtrip Test

**Files:**
- Create: `tests/test_persistence_roundtrip.py`

- [ ] **Step 1: Write roundtrip tests**

```python
# tests/test_persistence_roundtrip.py

import pytest
from server.engine.character import Character
from server.engine.persistence import save_player, load_player


def test_character_roundtrip_preserves_all_fields(load_game_data):
    """Save and load a complex character — all fields should survive the roundtrip."""
    c = Character(name="RoundtripHero", class_type="mage")
    c.level = 5
    c.xp = 4000
    c.gold = 250
    c.hp = 15
    c.max_hp = 30
    c.mp = 40
    c.max_mp = 60
    c.STR = 8
    c.DEX = 12
    c.INT = 18
    c.WIS = 14
    c.CON = 10
    c.AGI = 11
    c.hunger = 72.5
    c.thirst = 88.0
    c.stamina = 45.0
    c.equipment = {"weapon": "oak_staff", "body": "cloth_robe", "head": None,
                   "hands": None, "feet": None, "back": None}
    c.inventory = ["health_potion", "mana_potion", "torch"]
    c.modifiers = {"fire_intensity": 2, "staff_prof": 1}
    c.unlocked_skills = {"fireball": 1, "frost_bolt": 1}
    c.strategies = [{"priority": 1, "condition": "ALWAYS", "action": "USE_SKILL",
                     "skill": "fireball", "target": "WEAKEST"}]
    c.active_buffs = {"ration_satiated": 500}

    save_data = {
        "character": c.to_dict(),
        "party": [],
        "current_room_id": "town_square",
        "last_campfire_room_id": "inn",
    }

    save_player("RoundtripHero", save_data)
    loaded = load_player("RoundtripHero")

    assert loaded is not None
    loaded_char = Character.from_dict(loaded["character"])

    assert loaded_char.name == "RoundtripHero"
    assert loaded_char.class_type == "mage"
    assert loaded_char.level == 5
    assert loaded_char.gold == 250
    assert loaded_char.hp == 15
    assert loaded_char.mp == 40
    assert loaded_char.STR == 8
    assert loaded_char.INT == 18
    assert loaded_char.hunger == pytest.approx(72.5)
    assert loaded_char.thirst == pytest.approx(88.0)
    assert loaded_char.stamina == pytest.approx(45.0)
    assert loaded_char.equipment["weapon"] == "oak_staff"
    assert "health_potion" in loaded_char.inventory
    assert loaded_char.modifiers["fire_intensity"] == 2
    assert loaded_char.unlocked_skills["fireball"] == 1
    assert len(loaded_char.strategies) == 1
    assert loaded_char.active_buffs["ration_satiated"] == 500
    assert loaded["current_room_id"] == "town_square"
    assert loaded["last_campfire_room_id"] == "inn"


def test_load_nonexistent_player_returns_none(load_game_data):
    """Loading a player that doesn't exist should return None."""
    result = load_player("NoSuchPlayer_12345")
    assert result is None
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_persistence_roundtrip.py -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_persistence_roundtrip.py
git commit -m "test: add persistence roundtrip test for complex character data"
```

---

### Task 4: Strengthen Weak Assertions

**Files:**
- Modify: `tests/test_phase03_utility_skills.py`

- [ ] **Step 1: Find and fix weak assertions**

Search for patterns:
- `assert output` (bare truthiness check)
- `assert "no" in output.lower()` (too broad)
- `or` chains with 3+ alternatives

Replace with specific message checks:

```python
# Before:
output = "".join(collected).lower()
assert output  # BAD: passes if ANY output

# After:
output = "".join(collected).lower()
assert "don't have" in output or "no lockpick" in output  # Specific expected messages
```

```python
# Before:
assert "unknown" in output.lower() or "not found" in output.lower() or "no such" in output.lower()

# After:
assert any(phrase in output.lower() for phrase in ["unknown skill", "not found", "don't know"])
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_phase03_utility_skills.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_phase03_utility_skills.py
git commit -m "test: strengthen weak assertions in utility skill tests"
```

---

### Task 5: Fix Non-Deterministic Tests

**Files:**
- Modify: `tests/test_phase02_combat_penalties.py`
- Modify: `tests/test_phase07_wizard_spell_overhaul.py`

- [ ] **Step 1: Fix RNG-dependent combat penalty test**

```python
# In test_phase02_combat_penalties.py, find tests that use random.seed(42):

# Before:
import random
random.seed(42)
session._resolve_attack(attacker, target, log, is_player_side=True)
assert damage_dealt == 7  # exact value from seed — fragile!

# After:
# Test the LOGIC, not the RNG output:
session._resolve_attack(attacker, target, log, is_player_side=True)
assert target.hp < target.max_hp  # attack dealt some damage
assert target.hp >= 0             # didn't go below zero
```

- [ ] **Step 2: Fix probabilistic wizard damage test**

```python
# In test_phase07_wizard_spell_overhaul.py, find:

# Before:
results = {mage.roll_damage() for _ in range(50)}
assert len(results) > 1  # probabilistic — could theoretically fail

# After:
import random
random.seed(42)
results = [mage.roll_damage() for _ in range(20)]
assert min(results) >= 1              # minimum damage is at least 1
assert max(results) <= mage.max_damage  # never exceeds max
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_phase02_combat_penalties.py tests/test_phase07_wizard_spell_overhaul.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase02_combat_penalties.py tests/test_phase07_wizard_spell_overhaul.py
git commit -m "fix: replace non-deterministic test assertions with logic-based checks"
```

---

### Task 6: Add Integration Test (Full Game Flow)

**Files:**
- Create: `tests/test_integration_flow.py`

- [ ] **Step 1: Write end-to-end integration test**

```python
# tests/test_integration_flow.py

import asyncio
import pytest
from unittest.mock import AsyncMock
from server.engine.game import GameSession, State
from server.engine.world import WorldMap
from server.engine.world_clock import WorldClock
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "server", "data")


def test_full_game_flow_connect_to_combat(load_game_data):
    """Integration: CONNECT → CREATE → NAVIGATE → LOOK → STATUS → SAVE."""
    collected = []

    async def send(text):
        collected.append(text)

    # Load world
    world = WorldMap()
    world.load(DATA_DIR)

    # Load class defs
    with open(os.path.join(DATA_DIR, "classes", "classes.json")) as f:
        class_defs = json.load(f)

    clock = WorldClock.__new__(WorldClock)
    clock.total_minutes = 480  # 8 AM game time
    clock._hour = 8
    clock._minute = 0
    clock._day = 1
    clock._weather = "clear"
    clock._temperature = 65
    clock._subscribers = []

    session = GameSession(
        send_fn=send, world=world, class_defs=class_defs,
        clock=clock, sessions={},
    )

    loop = asyncio.new_event_loop()

    # Step 1: Start (should prompt for name)
    loop.run_until_complete(session.start())
    assert session.state == State.CONNECT
    assert any("name" in t.lower() for t in collected)

    # Step 2: Enter name
    collected.clear()
    loop.run_until_complete(session.handle_input("TestHero"))
    assert session.state == State.CREATION

    # Step 3: Choose class
    collected.clear()
    loop.run_until_complete(session.handle_input("WARRIOR"))

    # Step 4: Auto-suggest stats and finalize
    collected.clear()
    loop.run_until_complete(session.handle_input("SUGGEST"))
    loop.run_until_complete(session.handle_input("DONE"))

    # Step 5: Skip strategy editing
    collected.clear()
    loop.run_until_complete(session.handle_input("DONE"))
    assert session.state == State.NAVIGATION

    # Step 6: LOOK
    collected.clear()
    loop.run_until_complete(session.handle_input("LOOK"))
    assert any("town" in t.lower() or "square" in t.lower() for t in collected)

    # Step 7: STATUS
    collected.clear()
    loop.run_until_complete(session.handle_input("STATUS"))
    assert any("hunger" in t.lower() or "thirst" in t.lower() for t in collected)

    # Step 8: SAVE
    collected.clear()
    loop.run_until_complete(session.handle_input("SAVE"))
    assert any("saved" in t.lower() for t in collected)

    loop.close()
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_integration_flow.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_flow.py
git commit -m "test: add full game flow integration test (connect → create → navigate → save)"
```
