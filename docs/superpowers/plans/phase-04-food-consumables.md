# Plan: Phase 4 — Food & Consumables

**Spec:** [phase-04-food-consumables.md](../specs/phase-04-food-consumables.md)
**Depends on:** Phase 2 (hunger/thirst stats), Phase 3 (stamina cost system)
**Status:** NOT STARTED

---

## Overview

Expand the consumable system with food and drink items that restore hunger/thirst and grant timed buffs. Buff expiry is tracked per-character using the world clock's `total_minutes`. Buff types each hook into a specific stat calculation, not a generic multiplier.

---

## Phase A — Data Model

1. Add `active_buffs: dict[str, int]` to `Character` in `server/engine/character.py`
   - Key: buff name (e.g. `"alertness"`)
   - Value: expiry world-clock game-minute (`clock.total_minutes + duration`)
2. Add `apply_food_buff(buff_name: str, duration_minutes: int, clock: WorldClock)` method to `Character`:
   - Sets or replaces expiry (new buff overwrites old of same type)
3. Add `get_active_buffs(clock: WorldClock) -> list[str]` method to `Character`:
   - Returns list of buff names whose expiry > `clock.total_minutes`

---

## Phase B — Buff Effect Hooks

Wire each buff type into the relevant stat method. All hooks follow the pattern: check `get_active_buffs(clock)` and apply modifier if the buff is active.

4. `alertness` → `character.dodge_bonus()`: add +15 percentage points
5. `energised` → stamina recovery rate in `_on_clock_tick()` (passive sit recovery): multiply +1/min base by 1.5
6. `fortified` → stamina drain in `game.py` `_do_move()` and `combat.py` tick drain: multiply drain by 0.7
7. `satiated` → hunger drain per clock tick: multiply by 0.6
8. `quenched` → thirst drain per clock tick: multiply by 0.6
9. `focused` → spell intensity scale in `combat.py` `_resolve_action()` for CAST actions: multiply spell output by 1.1

---

## Phase C — Food Items

10. Add the following 9 items to `server/data/items/consumables.json`:

    | ID | Hunger | Thirst | Buff | Duration (min) |
    |----|--------|--------|------|----------------|
    | `hard_bread` | +30 | 0 | — | — |
    | `dried_meat` | +50 | 0 | — | — |
    | `ration_pack` | +40 | +20 | — | — |
    | `waterskin` | 0 | +80 | — | — |
    | `hearty_stew` | +70 | +30 | `fortified` | 120 |
    | `forest_berries` | +20 | +15 | `alertness` | 60 |
    | `adventure_bread` | +45 | 0 | `satiated` | 180 |
    | `mountain_tea` | 0 | +50 | `focused` | 60 |
    | `warrior_chow` | +60 | +10 | `energised` | 90 |

    JSON structure per item:
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

## Phase D — EAT / DRINK Commands (Full Implementation)

These were stubs in Phase 2. Replace the stubs with full logic here.

11. Implement `_do_eat(item_name: str)` in `game.py`:
    - Find item in party inventory matching name, with `effect_type == "food"`
    - Restore hunger by `effect_params["hunger"]` on the carrying character (capped at MAX_HUNGER)
    - Restore thirst by `effect_params["thirst"]` if present
    - If `effect_params` has `"buff"`: call `apply_food_buff(buff, buff_duration, clock)` on all party members
    - Remove one instance of item from the carrying character's inventory

12. Implement `_do_drink(item_name: str)` in `game.py`:
    - Same flow as EAT for items with `effect_type == "drink"` or `effect_type == "food"` (waterskin is food type with hunger 0)

---

## Phase E — BUFFS Command

13. Add `BUFFS` handler in `_handle_navigation()`:
    - For each party member: call `get_active_buffs(clock)`
    - Display buff name and remaining minutes (`expiry - clock.total_minutes`)
    - Show "No active buffs." if none

---

## Phase F — Goblin Loot

14. In `server/data/npcs/monsters.json`: add `ration_pack` to goblin loot table with ~30% drop chance

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/engine/character.py` | `active_buffs` field, `apply_food_buff()`, `get_active_buffs()`, buff hooks in `dodge_bonus()` |
| `server/engine/game.py` | Full `_do_eat()`, `_do_drink()`, `BUFFS` handler; drain rate hooks in clock tick |
| `server/engine/combat.py` | `fortified` stamina drain hook, `focused` spell scale hook |
| `server/data/items/consumables.json` | 9 new food/drink items |
| `server/data/npcs/monsters.json` | Goblin loot table update |

---

## Verification Checklist

- [ ] `EAT hearty_stew` → hunger +70, thirst +30, `fortified` buff applied for 120 game-minutes
- [ ] `BUFFS` → shows `fortified` with correct remaining time
- [ ] Travel 10 rooms while `fortified` active → stamina drain is 30% less than normal
- [ ] Wait for buff to expire → drain returns to normal
- [ ] `EAT forest_berries` → `alertness` active; dodge rolls increase in next combat
- [ ] `EAT mountain_tea` → `focused` active; spell damage visibly higher in next combat encounter
- [ ] Eating same buff type twice → expiry resets (does not stack duration)
- [ ] Kill goblin → ration_pack drops on ~30% of kills
- [ ] `EAT` with no item by that name in inventory → error message
- [ ] Hunger/thirst capped at 100 even if item would push over
