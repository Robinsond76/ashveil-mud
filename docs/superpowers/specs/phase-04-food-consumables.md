# Phase 4: Food & Consumables
**Status: NOT STARTED**
**Depends on: Phase 2 (survival stats), Phase 3 (stamina costs)**

## Overview
Expand the consumable item system to include food and drinks that don't just restore hunger/thirst but also provide temporary buffs. Food items create meaningful decisions about what to carry and consume before hard fights.

---

## Food System Additions

### Base Food Behaviour
Food items restore hunger (and food+drink combos restore both). This is the Phase 2 mechanic.

### Buff Food
Some food items grant a **temporary buff** on top of basic sustenance.

| Buff Type | Effect | Duration (game-min) |
|-----------|--------|---------------------|
| `alertness` | +15% dodge chance | 60 |
| `fortified` | Slower stamina consumption (−30%) | 120 |
| `satiated` | Slower hunger drain (−40%) | 180 |
| `quenched` | Slower thirst drain (−40%) | 120 |
| `energised` | Stamina recovery rate +50% | 90 |
| `focused` | +10% spell intensity for next encounter | 60 |

### Buff Stacking
- Only one buff of each type is active at a time (new one replaces old one)
- Buff duration tracked in game-minutes (world clock `total_minutes + duration`)

---

## Planned Food Items

| Item ID | Name | Hunger | Thirst | Buff |
|---------|------|--------|--------|------|
| `hard_bread` | Hard Bread | +30 | 0 | none |
| `dried_meat` | Dried Meat | +50 | 0 | none |
| `ration_pack` | Travel Rations | +40 | +20 | none |
| `waterskin` | Waterskin | 0 | +80 | none |
| `hearty_stew` | Hearty Stew | +70 | +30 | `fortified` 120 min |
| `forest_berries` | Forest Berries | +20 | +15 | `alertness` 60 min |
| `adventure_bread` | Spiced Bread | +45 | 0 | `satiated` 180 min |
| `mountain_tea` | Mountain Tea | 0 | +50 | `focused` 60 min |
| `warrior_chow` | Warrior's Chow | +60 | +10 | `energised` 90 min |

---

## Item JSON Structure

```json
{
  "id": "hearty_stew",
  "name": "Hearty Stew",
  "description": "A thick, filling stew made from forest game and root vegetables.",
  "type": "consumable",
  "effect_type": "food",
  "effect_params": {
    "hunger": 70,
    "thirst": 30,
    "buff": "fortified",
    "buff_duration": 120
  },
  "weight": 2,
  "value": 18
}
```

---

## Commands

| Command | Description |
|---------|-------------|
| `EAT <item>` | Consume a food item from party inventory |
| `DRINK <item>` | Consume a drink item |
| `BUFFS` | Show active food/drink buffs and remaining duration |

### Help entries to add
- `HELP EAT`, `HELP DRINK`, `HELP BUFFS`, `HELP FOOD`

---

## Where to Get Food
- Town markets / inn (restocking vendors — future merchant system)
- Forest foraging (future)
- Dropped by certain enemies (goblins drop ration packs)
- Crafted at campfire with ingredients (future Phase crafting)

---

## Data Changes

### Character fields to add
```python
active_buffs: dict[str, int] = {}  # buff_name → expiry_game_minute
```

### Helper needed
`apply_food_buff(character, buff_name, duration_minutes, clock)` — sets or refreshes expiry.

`get_active_buffs(character, clock)` — returns list of unexpired buffs.

---

## Notes
- Food buffs apply globally to all party combat stats (targeting the party aggregate model from Phase 2)
- `alertness` specifically hooks into `character.dodge_bonus()` as a temporary additive modifier
- Phase 5 inventory overhaul will allow food to be bulk-stored in backpacks/cart
