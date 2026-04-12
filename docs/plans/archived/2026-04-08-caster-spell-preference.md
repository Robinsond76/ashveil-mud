# Caster Spell Preference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all caster classes (mage, cleric) automatically cast their basic attack spell rather than fighting melee, with a cascade fallback so that expensive spells gracefully downgrade to the basic spell before ever hitting melee — and melee only occurs when mana is completely exhausted.

**Architecture:** Three coordinated changes. (1) Data layer: add `arcane_bolt` to the mage skill tree as a free cantrip, add `starter_skills` and `basic_spell` fields to caster class definitions, update default strategies to cast the basic spell, and propagate `arcane_bolt` to all mage NPC `unlocked_skills`. (2) Character creation: auto-unlock `starter_skills` during `_finalize_character_stats`. (3) Combat: add a `CASTER_BASIC_SPELLS` lookup table and a cascade in `_resolve_skill` — when an expensive spell fails due to insufficient MP, the engine tries the basic spell before ever falling back to melee.

**Tech Stack:** JSON data files, Python `server/engine/game.py`, `server/engine/combat.py`.

---

## File Map

| File | Change |
|------|--------|
| `server/data/classes/classes.json` | Add `basic_spell`, `starter_skills`; add `arcane_bolt` to mage tree; update mage + cleric default strategies |
| `server/engine/game.py` | Auto-unlock `starter_skills` in `_finalize_character_stats` |
| `server/engine/combat.py` | Add `CASTER_BASIC_SPELLS`; cascade in `_resolve_skill` |
| `server/data/npcs/monsters.json` | Add `arcane_bolt` to mage monster `unlocked_skills` |
| `server/data/npcs/recruitables.json` | Add `arcane_bolt` to mage recruitable `unlocked_skills`; remove explicit MP% attack fallback rules; update cleric ALWAYS rule to `USE_SKILL smite` |
| `tests/test_caster_spell_preference.py` | New — tests for starter skills, cascade logic, cleric behavior |

---

### Task 1: Write Failing Caster Tests

**Files:**
- Create: `tests/test_caster_spell_preference.py`

- [ ] **Step 1: Create the test file**

```python
"""
Tests for caster spell preference: starter skills, basic-spell cascade, cleric smite default.
"""
import pytest
from unittest.mock import AsyncMock

from server.engine.character import Character
from server.engine.npc import NPC

DATA_DIR = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "server", "data"
)


def _load_skills():
    from server.engine.skills import _SKILL_REGISTRY
    if not _SKILL_REGISTRY:
        from server.engine.skills import load_skills
        load_skills(DATA_DIR)


def _make_enemy(name="Goblin"):
    npc = NPC(
        name=name, class_type="warrior", level=1,
        hp=50, max_hp=50, mp=0, max_mp=0,
        STR=10, DEX=10, INT=10, WIS=10, CON=10, AGI=10,
        xp_reward=10, gold_range=(0, 5), template_id="goblin",
    )
    npc.status_effects = {}
    return npc


def _make_session(caster, enemy):
    from server.engine.combat import CombatSession
    return CombatSession(
        player_party=[caster],
        enemy_party=[enemy],
        send=AsyncMock(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Starter skills auto-unlock at character creation
# ─────────────────────────────────────────────────────────────────────────────

class TestStarterSkills:
    def test_new_mage_has_arcane_bolt_unlocked(self, load_game_data):
        """A freshly created mage must have arcane_bolt unlocked without spending skill points."""
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        mage_def = class_defs["mage"]
        assert "starter_skills" in mage_def, "mage must have starter_skills field"
        assert "arcane_bolt" in mage_def["starter_skills"]

    def test_new_cleric_has_heal_and_smite_unlocked(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        cleric_def = class_defs["cleric"]
        assert "starter_skills" in cleric_def
        assert "heal" in cleric_def["starter_skills"]
        assert "smite" in cleric_def["starter_skills"]

    def test_arcane_bolt_is_in_mage_skill_tree(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        tree_ids = [node["id"] for node in class_defs["mage"]["skill_tree"]]
        assert "arcane_bolt" in tree_ids

    def test_arcane_bolt_is_free_in_mage_skill_tree(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        node = next(n for n in class_defs["mage"]["skill_tree"] if n["id"] == "arcane_bolt")
        assert node["unlock_cost"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Basic spell cascade in _resolve_skill
# ─────────────────────────────────────────────────────────────────────────────

class TestMageCascade:
    def test_mage_uses_arcane_bolt_when_fireball_mp_insufficient(self, load_game_data):
        """Mage with MP < fireball cost but MP >= arcane_bolt cost casts arcane_bolt."""
        _load_skills()
        mage = Character(name="Lyria", class_type="mage", INT=14)
        mage.mp = 10        # fireball costs 18; arcane_bolt costs 5
        mage.max_mp = 60
        mage.unlocked_skills = {"fireball": 1, "arcane_bolt": 1}
        mage.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(mage, enemy)
        actor = session.player_combatants[0]
        allies = [mage]
        enemies = [enemy]

        log = []
        session._resolve_skill(actor, "fireball", enemy, allies, enemies, log)

        # MP should have dropped by arcane_bolt cost (5), not fireball cost (18)
        assert mage.mp == 5  # 10 - 5
        # Log should mention the downgrade
        full_log = " ".join(log).lower()
        assert "low on mp" in full_log or "arcane bolt" in full_log

    def test_mage_goes_melee_when_no_mp_for_arcane_bolt(self, load_game_data):
        """Mage with MP < arcane_bolt cost falls to melee (no infinite cascade)."""
        _load_skills()
        mage = Character(name="Lyria", class_type="mage", INT=14)
        mage.mp = 3         # arcane_bolt costs 5 — can't afford it
        mage.max_mp = 60
        mage.unlocked_skills = {"fireball": 1, "arcane_bolt": 1}
        mage.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(mage, enemy)
        actor = session.player_combatants[0]
        allies = [mage]
        enemies = [enemy]

        log = []
        session._resolve_skill(actor, "fireball", enemy, allies, enemies, log)

        # MP unchanged (no spell cast)
        assert mage.mp == 3
        # Log should mention attacking instead
        full_log = " ".join(log).lower()
        assert "attacking instead" in full_log or "insufficient" in full_log

    def test_cascade_does_not_loop_when_basic_spell_is_requested_spell(self, load_game_data):
        """If the strategy directly requests arcane_bolt and MP is too low → melee, not infinite loop."""
        _load_skills()
        mage = Character(name="Lyria", class_type="mage", INT=14)
        mage.mp = 2         # arcane_bolt costs 5
        mage.max_mp = 60
        mage.unlocked_skills = {"arcane_bolt": 1}
        mage.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(mage, enemy)
        actor = session.player_combatants[0]
        allies = [mage]
        enemies = [enemy]

        log = []
        # Should not raise RecursionError
        session._resolve_skill(actor, "arcane_bolt", enemy, allies, enemies, log)
        assert mage.mp == 2  # unchanged


# ─────────────────────────────────────────────────────────────────────────────
# Cleric smite as default attack
# ─────────────────────────────────────────────────────────────────────────────

class TestClericSmiteDefault:
    def test_cleric_default_strategy_last_rule_is_smite(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        last_strategy = class_defs["cleric"]["default_strategies"][-1]
        assert "smite" in last_strategy["action"].lower()

    def test_cleric_casts_smite_when_mp_available(self, load_game_data):
        """Cleric with smite unlocked and sufficient MP casts smite, not melee."""
        _load_skills()
        cleric = Character(name="Aldric", class_type="cleric", WIS=14)
        cleric.mp = 40       # smite costs 10
        cleric.max_mp = 45
        cleric.unlocked_skills = {"heal": 1, "smite": 1}
        cleric.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(cleric, enemy)
        actor = session.player_combatants[0]
        allies = [cleric]
        enemies = [enemy]

        hp_before = enemy.hp
        log = []
        session._resolve_skill(actor, "smite", enemy, allies, enemies, log)

        assert cleric.mp == 30  # 40 - 10
        assert enemy.hp < hp_before  # enemy took damage
        full_log = " ".join(log).lower()
        assert "smite" in full_log

    def test_cleric_falls_to_melee_when_mp_depleted(self, load_game_data):
        """Cleric with MP < smite cost falls to melee."""
        _load_skills()
        cleric = Character(name="Aldric", class_type="cleric", WIS=14)
        cleric.mp = 5        # smite costs 10
        cleric.max_mp = 45
        cleric.unlocked_skills = {"heal": 1, "smite": 1}
        cleric.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(cleric, enemy)
        actor = session.player_combatants[0]
        allies = [cleric]
        enemies = [enemy]

        log = []
        session._resolve_skill(actor, "smite", enemy, allies, enemies, log)

        assert cleric.mp == 5   # unchanged — no spell cast
        full_log = " ".join(log).lower()
        assert "attacking instead" in full_log or "insufficient" in full_log
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_caster_spell_preference.py -v
```

Expected: Multiple failures — `starter_skills` key missing from JSON, cascade not implemented yet, cleric ALWAYS rule is still `ATTACK`.

---

### Task 2: Update `classes.json` — Mage

**Files:**
- Modify: `server/data/classes/classes.json` (mage block)

- [ ] **Step 3: Add `basic_spell`, `starter_skills`, and `arcane_bolt` to mage skill tree**

In `server/data/classes/classes.json`, find the mage block. After `"recommended_modifiers": ["fire_intensity", "frost_intensity", "lightning_intensity"],` add these two fields:

```json
    "basic_spell": "arcane_bolt",
    "starter_skills": ["arcane_bolt"],
```

In the mage `"skill_tree"` array, add `arcane_bolt` as the first entry (before `fireball`):

```json
      {
        "id": "arcane_bolt",
        "unlock_cost": 0,
        "prerequisites": []
      },
```

- [ ] **Step 4: Update mage default strategies**

Find the mage `"default_strategies"` array:

```json
    "default_strategies": [
      { "priority": 1, "condition": "HP_SELF < 20%", "action": "DEFEND", "target": "SELF" },
      { "priority": 2, "condition": "MP_SELF < 10%", "action": "ATTACK", "target": "NEAREST_ENEMY" },
      { "priority": 3, "condition": "ALWAYS", "action": "USE_SKILL fireball", "target": "STRONGEST_ENEMY" }
    ]
```

Replace with:

```json
    "default_strategies": [
      { "priority": 1, "condition": "HP_SELF < 20%", "action": "DEFEND", "target": "SELF" },
      { "priority": 2, "condition": "ALWAYS", "action": "USE_SKILL arcane_bolt", "target": "NEAREST_ENEMY" }
    ]
```

The `MP_SELF < 10%` melee rule is removed — the cascade in `_resolve_skill` handles graceful fallback. The ALWAYS rule uses `arcane_bolt` (5 MP, instant) as the spam cantrip. Players can manually add a fireball rule via the campfire strategy editor if desired.

---

### Task 3: Update `classes.json` — Cleric

**Files:**
- Modify: `server/data/classes/classes.json` (cleric block)

- [ ] **Step 5: Add `basic_spell`, `starter_skills` to cleric**

In the cleric block, after `"recommended_modifiers": ["heal_power", "mace_prof", "curse_intensity"],` add:

```json
    "basic_spell": "smite",
    "starter_skills": ["heal", "smite"],
```

(`smite` is already in the cleric skill tree with `unlock_cost: 1` — no tree change needed. It is auto-unlocked via `starter_skills`.)

- [ ] **Step 6: Update cleric default strategies — change ALWAYS rule to smite**

Find the cleric `"default_strategies"` array:

```json
    "default_strategies": [
      { "priority": 1, "condition": "HP_ALLY < 30%", "action": "USE_SKILL heal", "target": "LOWEST_HP_ALLY" },
      { "priority": 2, "condition": "HP_SELF < 30%", "action": "USE_SKILL heal", "target": "SELF" },
      { "priority": 3, "condition": "ALWAYS", "action": "ATTACK", "target": "NEAREST_ENEMY" }
    ]
```

Replace the last rule:

```json
    "default_strategies": [
      { "priority": 1, "condition": "HP_ALLY < 30%", "action": "USE_SKILL heal", "target": "LOWEST_HP_ALLY" },
      { "priority": 2, "condition": "HP_SELF < 30%", "action": "USE_SKILL heal", "target": "SELF" },
      { "priority": 3, "condition": "ALWAYS", "action": "USE_SKILL smite", "target": "NEAREST_ENEMY" }
    ]
```

---

### Task 4: Auto-Unlock Starter Skills in `game.py`

**Files:**
- Modify: `server/engine/game.py` (`_finalize_character_stats`, ~line 483)

- [ ] **Step 7: Add the starter-skills unlock loop after strategy setup**

In `_finalize_character_stats`, find the block that appends default strategies:

```python
        # Default starting strategies from class definition
        for i, strat_raw in enumerate(cd.get("default_strategies", []), start=1):
            self.player.strategies.append({
                "priority": i,
                "condition": strat_raw["condition"],
                "action": strat_raw["action"],
                "target": strat_raw["target"],
            })
```

Immediately after that block (before `self.current_room_id = ...`), add:

```python
        # Auto-unlock free starter skills for this class (e.g. mage cantrip arcane_bolt)
        for skill_id in cd.get("starter_skills", []):
            self.player.unlocked_skills[skill_id] = 1
```

---

### Task 5: Add Cascade to `_resolve_skill` in `combat.py`

**Files:**
- Modify: `server/engine/combat.py` (module-level constant + `_resolve_skill`)

- [ ] **Step 8: Add `CASTER_BASIC_SPELLS` near the top of `combat.py`**

Find the existing class-set constants (after `RANGED_WEAPON_TYPES`):

```python
RANGED_WEAPON_TYPES = {"bow", "staff"}
```

Add directly after it:

```python
# Basic attack spell per caster class — tried before melee when an expensive spell fails MP check.
CASTER_BASIC_SPELLS: dict[str, str] = {
    "mage": "arcane_bolt",
    "cleric": "smite",
}
```

- [ ] **Step 9: Replace the insufficient-MP block in `_resolve_skill`**

In `_resolve_skill`, find:

```python
        if char.mp < skill.mp_cost:
            log.append(f"  {char.name} has insufficient MP for {skill.name}. Attacking instead.")
            self._resolve_attack(char, target, log)
            return
```

Replace with:

```python
        if char.mp < skill.mp_cost:
            # Cascade: try the class's basic spell before falling to melee.
            # Guard: don't cascade if the failing spell IS the basic spell (prevents infinite loop).
            basic_spell_id = CASTER_BASIC_SPELLS.get(char.class_type)
            if (
                basic_spell_id
                and basic_spell_id != skill_id
                and basic_spell_id in char.unlocked_skills
            ):
                basic_skill = get_skill(basic_spell_id)
                if basic_skill and char.mp >= basic_skill.mp_cost:
                    log.append(
                        f"  {char.name} is low on MP — casting {basic_skill.name}"
                        f" instead of {skill.name}."
                    )
                    self._resolve_skill(actor, basic_spell_id, target, allies, enemies, log)
                    return
            log.append(f"  {char.name} has insufficient MP for {skill.name}. Attacking instead.")
            self._resolve_attack(char, target, log)
            return
```

---

### Task 6: Update Mage NPC `unlocked_skills` in Data Files

Mages in the JSON data need `arcane_bolt` in their `unlocked_skills` or the cascade won't fire for them in combat (the cascade gate checks `basic_spell_id in char.unlocked_skills`).

**Files:**
- Modify: `server/data/npcs/monsters.json`
- Modify: `server/data/npcs/recruitables.json`

- [ ] **Step 10: Add `arcane_bolt` to mage monsters**

In `monsters.json`, find `goblin_shaman`:

```json
    "unlocked_skills": { "fireball": 1 },
```

Replace with:

```json
    "unlocked_skills": { "fireball": 1, "arcane_bolt": 1 },
```

Find `dungeon_mage`:

```json
    "unlocked_skills": { "fireball": 1, "frost_bolt": 1 },
```

Replace with:

```json
    "unlocked_skills": { "fireball": 1, "frost_bolt": 1, "arcane_bolt": 1 },
```

- [ ] **Step 11: Update mage recruitable Lyria**

In `recruitables.json`, find Lyria's `unlocked_skills`:

```json
    "unlocked_skills": { "fireball": 1 },
```

Replace with:

```json
    "unlocked_skills": { "fireball": 1, "arcane_bolt": 1 },
```

Find Lyria's `default_strategies`:

```json
      { "priority": 1, "condition": "HP_SELF < 20%", "action": "DEFEND", "target": "SELF" },
      { "priority": 2, "condition": "MP_SELF < 10%", "action": "ATTACK", "target": "NEAREST_ENEMY" },
      { "priority": 3, "condition": "ALWAYS", "action": "USE_SKILL fireball", "target": "STRONGEST_ENEMY" }
```

Replace with (remove the explicit ATTACK fallback — cascade handles it):

```json
      { "priority": 1, "condition": "HP_SELF < 20%", "action": "DEFEND", "target": "SELF" },
      { "priority": 2, "condition": "ALWAYS", "action": "USE_SKILL fireball", "target": "STRONGEST_ENEMY" }
```

- [ ] **Step 12: Update mage recruitable Vex**

Find Vex's `unlocked_skills`:

```json
    "unlocked_skills": { "frost_bolt": 1, "blizzard": 1 },
```

Replace with:

```json
    "unlocked_skills": { "frost_bolt": 1, "blizzard": 1, "arcane_bolt": 1 },
```

Find Vex's `default_strategies`:

```json
      { "priority": 1, "condition": "HP_SELF < 20%", "action": "DEFEND", "target": "SELF" },
      { "priority": 2, "condition": "ENEMY_COUNT > 2", "action": "USE_SKILL blizzard", "target": "NEAREST_ENEMY" },
      { "priority": 3, "condition": "MP_SELF < 15%", "action": "ATTACK", "target": "NEAREST_ENEMY" },
      { "priority": 4, "condition": "ALWAYS", "action": "USE_SKILL frost_bolt", "target": "STRONGEST_ENEMY" }
```

Replace with (remove MP_SELF attack fallback — cascade handles it; renumber):

```json
      { "priority": 1, "condition": "HP_SELF < 20%", "action": "DEFEND", "target": "SELF" },
      { "priority": 2, "condition": "ENEMY_COUNT > 2", "action": "USE_SKILL blizzard", "target": "NEAREST_ENEMY" },
      { "priority": 3, "condition": "ALWAYS", "action": "USE_SKILL frost_bolt", "target": "STRONGEST_ENEMY" }
```

- [ ] **Step 13: Update cleric recruitable Aldric ALWAYS rule**

Find Aldric's `default_strategies` last rule:

```json
      { "priority": 3, "condition": "ALWAYS", "action": "ATTACK", "target": "NEAREST_ENEMY" }
```

Replace with:

```json
      { "priority": 3, "condition": "ALWAYS", "action": "USE_SKILL smite", "target": "NEAREST_ENEMY" }
```

- [ ] **Step 14: Update cleric recruitable Sister Ophelia ALWAYS rule**

Find Sister Ophelia's `default_strategies` last rule:

```json
      { "priority": 5, "condition": "ALWAYS", "action": "ATTACK", "target": "NEAREST_ENEMY" }
```

Replace with:

```json
      { "priority": 5, "condition": "ALWAYS", "action": "USE_SKILL smite", "target": "NEAREST_ENEMY" }
```

---

### Task 7: Verify All Tests Pass

- [ ] **Step 15: Run the caster preference tests**

```
pytest tests/test_caster_spell_preference.py -v
```

Expected: All 9 tests `PASS`.

- [ ] **Step 16: Run the full test suite — no regressions**

```
pytest tests/ -v
```

Expected: All existing tests pass. The `test_zero_mp_mage_action_is_dodge` test in `test_phase07_wizard_spell_overhaul.py` tests `_do_action_mage_zero_mp` directly and is unaffected by this change.

- [ ] **Step 17: Commit**

```
git add server/data/classes/classes.json \
        server/engine/game.py \
        server/engine/combat.py \
        server/data/npcs/monsters.json \
        server/data/npcs/recruitables.json \
        tests/test_caster_spell_preference.py
git commit -m "feat: casters default to spell attacks; arcane_bolt cascade before melee fallback"
```

---

## Cascade Behavior Reference

| MP available | Strategy says | Result |
|-------------|---------------|--------|
| ≥ 18 | `USE_SKILL fireball` | Fireball fires normally |
| 5–17 | `USE_SKILL fireball` | Cascade → casts arcane_bolt (5 MP) |
| 0–4 | `USE_SKILL fireball` | No cascade possible → melee |
| ≥ 10 | `USE_SKILL smite` | Smite fires normally |
| 0–9 | `USE_SKILL smite` | smite IS basic spell → no cascade → melee |

## Decisions

- `arcane_bolt` is a **free cantrip** (`unlock_cost: 0`) — it doesn't consume the mage's one available starting skill point. Players buying the skill tree path to fireball still spend their points normally.
- The cascade only fires for `_resolve_skill` (i.e., spells). It does not change melee (`_resolve_attack`) or item behaviour.
- Cleric's `smite` already had `unlock_cost: 1` in the tree; auto-unlocking it via `starter_skills` bypasses the cost at character creation only (NPCs always had it in their JSON `unlocked_skills` manually).
- `_do_action_mage_zero_mp` (which sets a defending status) is an existing method tested directly but never wired into `_do_action`. It is intentionally out of scope — leaving it means truly exhausted mages still fall to melee rather than perpetually defending.
