# Phase 7: Wizard & Spell Overhaul
**Status: NOT STARTED**
**Depends on: Phase 1 (combat system, lighting), Phase 3 (mana rework)**

## Overview
Mages become glass-cannon channelers. They cannot wear heavy armor, have strict weight limits, carry no melee capability, and rely entirely on mana for offense. Spells have cast times with staged progress messages and support AoE targeting on the combat grid.

---

## Glass Cannon Constraints

### Armor Restrictions
| Armor Type | Mage Penalty |
|------------|-------------|
| Cloth/Robes | Full spell power, no penalty |
| Light armor (leather) | −10% spell power |
| Medium armor (chain) | −30% spell power, disadvantage on spell rolls |
| Heavy armor (plate) | Cannot cast. At all. |

Implementation: `Character.spell_power_modifier()` reads equipped armor, returns multiplier.

### Melee
- Mages have **no melee proficiency**. Attacking with a non-staff weapon deals minimum (1) damage.
- Staffs are the only valid weapon for mages (provide melee option + spell power bonus).

### Weight Limits
- Mages have a stricter carry weight ceiling: `INT * 1.5` pounds (warriors use `STR * 3`).
- Exceeding limit: same overweight penalty as all classes, but triggers earlier.

---

## Staff & Spellbook Items

### Staffs
```json
{
  "id": "apprentice_staff",
  "name": "Apprentice Staff",
  "type": "weapon",
  "class_requirement": "mage",
  "damage_min": 2,
  "damage_max": 6,
  "spell_power_bonus": 5,
  "weight": 4,
  "value": 40
}
```
- `spell_power_bonus` adds to all spell damage and healing rolls.

### Spellbooks
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
- Spellbook must be in inventory (not necessarily equipped) to cast granted spells.
- No spellbook = can only cast class-default spells at base power.

---

## Channeled Spells

### Cast Time System
Each spell has a `cast_time_seconds` field. The client receives broadcast messages at 3-second intervals.

Standard interval messages (4 stages):
1. `"[Name] begins chanting under their breath."` — on cast start
2. `"[Name] continues their chant, hands moving in patterns."` — at 1/3 of cast time
3. `"[Name] raises their staff, crackling with energy."` — at 2/3 of cast time
4. `"[Name] releases the spell!"` — on cast complete → effect fires

Custom messages can be specified per spell.

### Interruption
- Taking damage during casting: INT-based save roll to maintain concentration
  - Fail → spell cancelled, half mana cost refunded, message: *"[Name]'s concentration breaks!"*
- Moving rooms: always cancels cast

### Spell Data Structure
```json
{
  "id": "fireball",
  "name": "Fireball",
  "class": "mage",
  "mana_cost": 18,
  "cast_time_seconds": 9,
  "target_type": "grid_2x2",
  "damage_type": "fire",
  "damage_dice": "3d8",
  "spell_power_scale": 0.5,
  "description": "Calls down a sphere of fire engulfing a 2x2 section of the battlefield.",
  "cast_messages": [
    "{name} begins tracing a sigil in the air.",
    "{name} breathes deeply, heat shimmering around their hands.",
    "{name} screams the word of ignition!",
    "A fireball detonates across the battlefield!"
  ]
}
```

---

## AoE Grid Targeting

### Target Types
| `target_type` | Grid Coverage | Description |
|---------------|--------------|-------------|
| `"single"` | 1 combatant | Standard single-target |
| `"grid_1x1"` | 1 cell (1 combatant) | Precise strike |
| `"grid_1x2"` | 1 row, 2 cols = up to 2 combatants | Line/cone |
| `"grid_2x2"` | 2 rows, 2 cols = up to 4 combatants | Blast zone |
| `"all_enemies"` | Entire enemy side | Full-room AoE |

### Combat Grid (reference)
```
         Col 0    Col 1    Col 2
Row 0   [Front]  [Front]  [Front]
Row 1   [Back ]  [Back ]  [Back ]
```
AoE damage is split among all hit combatants: full damage each (not split total).

### Targeting Command
```
CAST FIREBALL 0 1       ← targets grid cell row 0, col 1
CAST CHAIN_LIGHTNING    ← all_enemies type needs no target
CAST FROST_BOLT ARTIS   ← single-target by name
```

---

## Zero Mana State

When a mage reaches 0 MP:
- Cannot initiate any spell cast
- In combat: mage's action is forced to `DODGE`
- Message on attempting to cast: *"You reach for the arcane but find nothing. You can only brace yourself."*
- Recovery: only through rest (Phase 3 rule) or mana potions (Phase 4)

---

## Base Spell List (Mage)

| Spell | Mana | Cast Time | Target | Effect |
|-------|------|-----------|--------|--------|
| Arcane Bolt | 5 | 0s (instant) | single | Minor magic damage |
| Magic Missile | 8 | 3s | single | Magic damage, guaranteed hit |
| Frost Bolt | 10 | 6s | single | Cold damage + slow |
| Fireball | 18 | 9s | grid_2x2 | Fire damage AoE |
| Chain Lightning | 22 | 6s | all_enemies | Lightning, reduced per target |
| Arcane Shield | 12 | 3s | self | Temporary magic barrier |
| Blink | 8 | 0s (instant) | self | 50% dodge chance next attack |

---

## Data Changes

### skills/mage_skills.json
- Add `cast_time_seconds`, `target_type`, `damage_type`, `cast_messages`, `spell_power_scale`

### Character changes
- `spell_power_modifier() → float`: reads armor + staff bonuses
- `_channeling: dict | None`: holds in-progress cast task, spell, target

### CombatSession changes
- `_do_action()`: if actor is mage and action is CAST, spawn channeling task
- Channeling task sends interval messages, checks interruption, then fires effect
- `_interrupt_cast()`: called when caster takes damage

### items/weapons.json
- Add mage staffs with `spell_power_bonus` field

### items/misc.json
- Add spellbooks with `grants_spells` and `spell_power_bonus`

---

## Help entries to add
- `HELP WIZARD`, `HELP SPELLS`, `HELP CASTING`, `HELP CAST`, `HELP FIREBALL` (per spell)
