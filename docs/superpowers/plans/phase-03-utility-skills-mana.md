# Plan: Phase 3 — Utility Skills & Mana Rework

**Spec:** [phase-03-utility-skills-mana.md](../specs/phase-03-utility-skills-mana.md)
**Depends on:** Phase 2 (some utility skills consume stamina)
**Status:** NOT STARTED

---

## Overview

Split skills into combat/utility contexts, add a `USE <skill_id>` command for out-of-combat activation, and restrict mana recovery to REST only (no passive regen). Mana potions remain valid as instant restores.

---

## Phase A — Mana Rework

1. In `game.py` `_do_rest()` (CAMPFIRE state): restore full MP for all party members in addition to HP (MP restore may already exist — confirm and add if missing)
2. Audit `world_clock.py` and `game.py` for any passive MP regen out-of-combat tick — remove or guard with a comment
3. Mana potions (already in item data): confirm `effect_type: "restore_mp"` works in `_do_use_item()` — no change needed, just verify

---

## Phase B — Skill JSON Additions

4. Add the following optional fields to each skill entry in all class skill JSON files:
   ```json
   {
     "use_context": "utility",
     "stamina_cost": 5,
     "required_items": ["lockpick"],
     "consumes_item": false,
     "effect_type": "unlock_door"
   }
   ```
   - `use_context` defaults to `"combat"` if omitted (backward-compatible)
5. Add the 7 planned utility skills to the appropriate class skill JSON files:

   | File | Skills to Add |
   |------|--------------|
   | `thief_skills.json` | `lockpick`, `detect_traps` |
   | `mage_skills.json` | `arcane_light`, `identify` |
   | `cleric_skills.json` | `bless_camp`, `purify_food` |
   | `warrior_skills.json` | `fortify` |

---

## Phase C — Skill Registry

6. Update `Skill` dataclass in `server/engine/skills.py` to include new optional fields with defaults:
   ```python
   use_context: str = "combat"
   stamina_cost: int = 0
   required_items: list[str] = field(default_factory=list)
   consumes_item: bool = False
   ```
7. Add `SkillRegistry.get_utility_skills(class_type: str) -> list[Skill]` filter helper
8. Add `SkillRegistry.get_combat_skills(class_type: str) -> list[Skill]` filter helper

---

## Phase D — USE Command

9. Add `_handle_use_skill(skill_id: str)` in `game.py`, only callable from NAVIGATION state:
   - Validate state == NAVIGATION (error if in combat or campfire)
   - Look up skill; error if not found or not unlocked
   - Check `use_context == "utility"`; error if combat skill
   - Check character has sufficient MP or stamina
   - Check party inventory for each item in `required_items` (any member's inventory counts)
   - Deduct MP cost or stamina cost
   - If `consumes_item == true` and item found: remove one instance from inventory
   - Dispatch to `_execute_utility_effect(skill, room)` switching on `effect_type`

10. Implement each utility effect handler:

    | `effect_type` | Behaviour |
    |--------------|-----------|
    | `unlock_door` | If room has a locked exit: mark it unlocked, print success |
    | `reveal_traps` | Print trap info for hidden traps in room (future rooms can have trap flags) |
    | `provide_light` | Set temporary +80% light override on room for 120 game-minutes |
    | `identify_item` | Print full stats of first unidentified item in party inventory |
    | `bless_camp` | Set flag to reduce hunger drain 50% for next rest period |
    | `purify_food` | Mark first spoiled food item in inventory as safe |
    | `fortify_party` | Apply -10% incoming damage modifier until next combat ends |

---

## Phase E — SKILLS Command Update

11. Update `_handle_skills()` in `game.py` to accept optional argument:
    - `SKILLS UTILITY` → call `get_utility_skills()`, display with stamina/MP cost and required items
    - `SKILLS COMBAT` → call `get_combat_skills()`, display as before
    - Bare `SKILLS` → show both sections with headers

---

## Phase F — New Items

12. Add to `server/data/items/misc.json`:
    ```json
    { "id": "lockpick", "name": "Lockpick", "type": "misc", "stackable": true, "weight": 0, "value": 5 },
    { "id": "thieves_tools", "name": "Thieves' Tools", "type": "misc", "stackable": false, "weight": 1, "value": 25 }
    ```

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/data/skills/thief_skills.json` | Add `lockpick`, `detect_traps` utility skills |
| `server/data/skills/mage_skills.json` | Add `arcane_light`, `identify` utility skills |
| `server/data/skills/cleric_skills.json` | Add `bless_camp`, `purify_food` utility skills |
| `server/data/skills/warrior_skills.json` | Add `fortify` utility skill |
| `server/data/items/misc.json` | Add lockpick, thieves_tools |
| `server/engine/skills.py` | Skill dataclass additions, filter helpers |
| `server/engine/game.py` | USE handler, SKILLS filter, REST MP restore |

---

## Verification Checklist

- [ ] `REST` at campfire → MP fully restored for all party members
- [ ] Out-of-combat tick: MP does not regenerate passively
- [ ] `USE lockpick` without lockpick in inventory → error message
- [ ] `USE lockpick` with lockpick in any party member's inventory → door unlocked
- [ ] `SKILLS UTILITY` → shows only utility skills with costs and item requirements
- [ ] `SKILLS COMBAT` → shows only combat skills
- [ ] Bare `SKILLS` → shows both sections
- [ ] `USE fortify` (warrior, in NAVIGATION state) → party takes -10% damage in next combat
- [ ] Mage at 0 MP in combat → forced to DODGE, message displayed (this constraint enforced in Phase 7 but mana rework verified here)
- [ ] Mana potion used in combat → MP restored immediately
