# Phase 3: Utility Skills & Mana Rework
**Status: NOT STARTED**
**Depends on: Phase 2 (some utility skills consume stamina)**

## Overview
Introduce skills usable outside of combat via direct player commands. Also tighten the mana economy: mana now only recovers through resting (not potions in combat), making spell casters a deliberate resource to manage between encounters.

---

## Two Skill Categories

| Category | When Used | Triggered By | MP/Stamina Cost |
|----------|-----------|-------------|----------------|
| **Combat skills** | In combat | Strategy rules (automatic) | MP (as now) |
| **Utility skills** | Outside combat | Direct player command | MP or Stamina |

---

## Mana Rework

### Current behaviour (to change)
- Mana potions restore MP mid-combat
- Mana potions remain valid as items

### New behaviour
- Mana recovers **only** via the `REST` command at a campfire
- Mana potions still restore MP immediately — but they become scarce/valuable
- No passive regeneration out of combat
- `REST` restores full HP **and** MP
- If a caster reaches 0 MP during combat, they must rely on basic attacks and dodging only

### Why
This makes wizard/cleric mana a true resource across multiple encounters, not just within one.

---

## Utility Skills

### Design Rules
1. Utility skills are listed separately from combat skills in the skill tree
2. Each has a `use_context: "utility"` flag in the skill JSON
3. Some require an item in party inventory before use
4. Activation: `USE <skill_id>` command in NAVIGATION state

### Skill Item Requirements
When a utility skill requires an item, the system checks party inventory (any member). If found, the item is consumed on use (or stays — defined per skill).

```json
{
  "required_items": ["lockpick"],
  "consumes_item": false
}
```

### Planned Utility Skills (examples)

| Class | Skill ID | Cost | Requires | Effect |
|-------|----------|------|----------|--------|
| Thief | `lockpick` | 5 stamina | Lockpick item | Opens a locked door or chest in the room |
| Thief | `detect_traps` | 10 MP | — | Reveals hidden traps in room |
| Mage | `arcane_light` | 15 MP | — | Provides 80% light level for 120 game-minutes |
| Mage | `identify` | 20 MP | — | Reveals all stats of an unidentified item |
| Cleric | `bless_camp` | 25 MP | — | Reduces hunger drain rate 50% for next rest |
| Cleric | `purify_food` | 10 MP | Food item | Makes spoiled food safe to eat |
| Warrior | `fortify` | 10 stamina | — | Party takes -10% damage until next combat |

---

## Commands

| Command | Description |
|---------|-------------|
| `USE <skill_id>` | Activate a utility skill |
| `SKILLS UTILITY` | Show only utility skills (with MP/stamina costs) |
| `SKILLS COMBAT` | Show only combat skills |
| `SKILLS` | Show all (both categories) |

### Help entries to add
- `HELP USE`, `HELP UTILITY SKILLS`, `HELP MANA`

---

## Data Changes

### Skill JSON additions
```json
{
  "use_context": "utility",
  "stamina_cost": 5,
  "required_items": ["lockpick"],
  "consumes_item": false,
  "effect_type": "unlock_door"
}
```

### Items to add
- Lockpick (stackable, consumed on use if lock is hard)
- Thieves' Tools (reusable, higher success chance)

### Help entries to add
- `HELP USE`, `HELP MANA`, `HELP UTILITY`

---

## Notes
- `arcane_light` utility spell is the in-combat-equivalent of a torch/lantern — provides the highest light level (80%) and persists until caster rests
- Phase 7 (Wizard overhaul) builds on this with channeled AoE combat spells
- The `lockpick` utility skill sets up Phase 5's dungeon chests and locked rooms
