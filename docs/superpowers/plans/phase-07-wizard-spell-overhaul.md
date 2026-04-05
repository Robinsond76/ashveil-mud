# Plan: Phase 7 — Wizard & Spell Overhaul

**Spec:** [phase-07-wizard-spell-overhaul.md](../specs/phase-07-wizard-spell-overhaul.md)
**Depends on:** Phase 1 (combat system, lighting ✅), Phase 3 (mana rework)
**Status:** NOT STARTED

---

## Overview

Mages become glass-cannon channelers: armor penalizes spell power, non-staff weapons deal 1 damage, weight cap is stricter, and spells have cast times with staged progress messages. AoE spells target a grid cell affecting multiple combatants. Taking damage during a cast triggers an INT-based concentration save.

---

## Phase A — Glass Cannon Constraints

1. Add `spell_power_modifier() -> float` to `Character` in `server/engine/character.py`:
   - Only applies if `class_type == "mage"`
   - Reads equipped body slot armor `armor_type`:
     - `cloth` / `robe` / `None` → 1.0
     - `leather` → 0.9
     - `chain` → 0.7
     - `plate` → 0.0 (cannot cast)
   - Adds `spell_power_bonus` from equipped weapon if it's a staff
   - Adds `spell_power_bonus` from any spellbook in inventory
   - Returns combined float multiplier

2. Mage melee guard in `character.py` `roll_damage()`:
   - If `class_type == "mage"` and equipped weapon `weapon_type != "staff"`:
     - Return `1` (minimum damage, no roll)

3. Mage weight cap in `carry_weight_cap` property (Phase 5 added this property):
   - If `class_type == "mage"`: return `int(self.INT * 1.5)` instead of the standard formula

---

## Phase B — Staff & Spellbook Items

4. Add mage staffs to `server/data/items/weapons.json`:
   ```json
   {
     "id": "apprentice_staff",
     "name": "Apprentice Staff",
     "type": "weapon",
     "weapon_type": "staff",
     "class_requirement": "mage",
     "stats": { "damage_min": 2, "damage_max": 6 },
     "spell_power_bonus": 5,
     "weight": 4,
     "value": 40
   }
   ```
   Add at minimum: `apprentice_staff`, `oaken_staff`, `arcane_staff`

5. Add spellbooks to `server/data/items/misc.json`:
   ```json
   {
     "id": "basic_spellbook",
     "name": "Basic Spellbook",
     "type": "accessory",
     "class_requirement": "mage",
     "effect_type": "spellbook",
     "grants_spells": ["arcane_bolt", "arcane_light"],
     "spell_power_bonus": 3,
     "weight": 2,
     "value": 60
   }
   ```
   Add at minimum: `basic_spellbook`, `advanced_spellbook`

6. In `spell_power_modifier()`: check all items in `character.inventory` for `effect_type == "spellbook"` and sum their `spell_power_bonus` values

---

## Phase C — Spell Data

7. Update `server/data/skills/mage_skills.json` — add these fields to each spell entry:
   ```json
   {
     "cast_time_seconds": 9,
     "target_type": "grid_2x2",
     "damage_type": "fire",
     "spell_power_scale": 0.5,
     "cast_messages": [
       "{name} begins tracing a sigil in the air.",
       "{name} breathes deeply, heat shimmering around their hands.",
       "{name} screams the word of ignition!",
       "A fireball detonates across the battlefield!"
     ]
   }
   ```
8. Add all 7 base spells from the spec:

   | Spell | Mana | Cast Time | Target | Effect |
   |-------|------|-----------|--------|--------|
   | `arcane_bolt` | 5 | 0s | single | Minor magic damage |
   | `magic_missile` | 8 | 3s | single | Magic damage, guaranteed hit |
   | `frost_bolt` | 10 | 6s | single | Cold damage + slow |
   | `fireball` | 18 | 9s | grid_2x2 | Fire damage AoE |
   | `chain_lightning` | 22 | 6s | all_enemies | Lightning, reduced per target |
   | `arcane_shield` | 12 | 3s | self | Temporary magic barrier |
   | `blink` | 8 | 0s | self | 50% dodge chance next hit |

---

## Phase D — Skill Dataclass Update

9. Update `Skill` dataclass in `server/engine/skills.py` with new optional fields:
   ```python
   cast_time_seconds: int = 0
   target_type: str = "single"
   damage_type: str = "physical"
   spell_power_scale: float = 1.0
   cast_messages: list[str] = field(default_factory=list)
   ```

---

## Phase E — Cast Time System

10. Add `_channeling: asyncio.Task | None = None` to `Combatant` dataclass in `server/engine/combat.py`
11. In `CombatSession._do_action()`: if actor is mage and action is a spell cast:
    - If `spell.cast_time_seconds == 0`: resolve effect immediately (existing path)
    - Else: spawn `asyncio.create_task(_channeling_task(combatant, spell, target))` and store in `combatant._channeling`; do NOT resolve effect yet

12. Implement `_channeling_task(combatant, spell, target)` coroutine:
    - Calculate interval: `interval = cast_time_seconds / 3` (3 intermediate stages)
    - Send `cast_messages[0]` (cast start) to all players in the combat
    - `await asyncio.sleep(interval)` — send `cast_messages[1]`
    - `await asyncio.sleep(interval)` — send `cast_messages[2]`
    - `await asyncio.sleep(interval)` — send `cast_messages[3]`
    - Call `_resolve_spell_effect(combatant, spell, target)` to fire damage/effect

---

## Phase F — Interruption

13. In `CombatSession._apply_damage(target, amount)`: after applying damage, if `target._channeling is not None`:
    - Roll INT save: `random.randint(1, 20) + int_modifier >= 12`
    - On fail: `target._channeling.cancel()`, refund `spell.mana_cost // 2` MP, broadcast `"[Name]'s concentration breaks!"`
    - On success: channel continues uninterrupted

14. In `game.py` `_do_move()`: if player is in combat and `player_combatant._channeling is not None`:
    - Cancel the task
    - Print: `"Moving breaks your concentration!"`

---

## Phase G — AoE Grid Targeting

15. Implement `_resolve_aoe_targets(target_type: str, row: int, col: int, combatants: list[Combatant]) -> list[Combatant]` in `combat.py`:

    | `target_type` | Coverage |
    |---------------|----------|
    | `single` | One named target |
    | `grid_1x1` | One cell (row, col) |
    | `grid_1x2` | Same row, col and col+1 |
    | `grid_2x2` | Rows row and row+1, cols col and col+1 |
    | `all_enemies` | All combatants on enemy side |

16. Update `CAST` command parsing in `game.py`:
    - `CAST <spell> <row> <col>` → grid targeting
    - `CAST <spell> <name>` → single target by name
    - `CAST <spell>` → `all_enemies` type needs no target; single target spells default to nearest enemy
17. Apply spell damage to **each** target in resolved list at full power (not split)

---

## Phase H — Zero Mana State

18. In `CombatSession` strategy evaluation for mage combatants:
    - If `character.mp == 0` and action resolves to a spell cast → force action to `DODGE`
    - On first occurrence per combat: send message `"[Name] reaches for the arcane but finds nothing. They can only brace themselves."`

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/engine/character.py` | `spell_power_modifier()`, mage melee guard in `roll_damage()`, mage weight cap in `carry_weight_cap` |
| `server/engine/combat.py` | `_channeling` on Combatant, `_channeling_task()`, interruption in `_apply_damage()`, `_resolve_aoe_targets()`, 0 MP fallback |
| `server/engine/skills.py` | New optional fields on `Skill` dataclass |
| `server/engine/game.py` | CAST command parsing, channel cancel on move |
| `server/data/skills/mage_skills.json` | All 7 spells with full cast data |
| `server/data/items/weapons.json` | Mage staffs |
| `server/data/items/misc.json` | Spellbooks |

---

## Verification Checklist

- [ ] Mage in cloth armor: `spell_power_modifier()` returns 1.0
- [ ] Mage in chain mail: spell power at 70%; spells deal 70% of base
- [ ] Mage in plate: action forced to something other than cast; cannot cast
- [ ] Mage attacks with iron sword: always deals exactly 1 damage
- [ ] Mage attacks with staff: normal damage roll (2–6 for apprentice_staff)
- [ ] `CAST fireball 0 1` → 9-second cast time with 4 staged messages; hits up to 4 enemies in 2×2
- [ ] Mage takes damage during cast: INT save roll; concentration break message on failure
- [ ] Mage takes damage during cast and passes save: cast continues
- [ ] Move during cast: *"Moving breaks your concentration!"*
- [ ] `CAST arcane_bolt` (instant): fires immediately with no staged messages
- [ ] Mage at 0 MP: forced to DODGE in combat; message displayed on first occurrence
- [ ] Staff in hand: `spell_power_bonus` of staff adds to spell output damage
- [ ] Spellbook in inventory: `spell_power_bonus` adds to spells; `grants_spells` spells become castable
