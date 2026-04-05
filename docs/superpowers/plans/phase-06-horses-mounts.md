# Plan: Phase 6 — Horses & Mounts

**Spec:** [phase-06-horses-mounts.md](../specs/phase-06-horses-mounts.md)
**Depends on:** Phase 2 (stamina drain), Phase 5 (cart outdoor-only pattern as reference)
**Status:** NOT STARTED

---

## Overview

Horses reduce travel stamina drain. They behave like the cart: outdoor-only, auto-detaching on entering indoor/underground rooms. Stamina reduction scales by horse-to-party-member ratio. Horses auto-dismount when combat begins and auto-remount when it ends.

---

## Phase A — Horse Item

1. Add `horse` to `server/data/items/misc.json`:
   ```json
   {
     "id": "horse",
     "name": "Horse",
     "description": "A sturdy riding horse. Reduces travel stamina drain and stays outside buildings and caves.",
     "type": "mount",
     "effect_type": "mount",
     "effect_params": {
       "stamina_reduction": 0.60,
       "outdoor_only": true
     },
     "weight": 0,
     "value": 200
   }
   ```

---

## Phase B — GameSession State

2. Add to `GameSession` in `game.py`:
   ```python
   _mounted: bool = False
   _horses_outside: bool = False
   _was_mounted: bool = False   # stores pre-combat mounted state for remount
   ```
3. Add `_horse_count() -> int` helper: counts items with `type == "mount"` across all party member inventories (not cart)
4. Add `_stamina_multiplier() -> float` implementing the formula from spec:
   ```python
   ratio = min(1.0, horse_count / max(1, party_size))
   multiplier = 1.0 - (0.60 * ratio)
   return multiplier if _mounted else 1.0
   ```

---

## Phase C — Movement Hook

5. In `_do_move()`, after resolving destination room type:
   - If destination is `indoor` or `underground` and `_mounted`:
     - `_mounted = False`
     - `_horses_outside = True`
     - Print: `"Your horses wait outside at [current room name]."`
   - If destination is `outdoor` and `_horses_outside`:
     - `_horses_outside = False`
     - `_mounted = True`
     - Print: `"Your horses fall back into step with the party."`
6. Apply `_stamina_multiplier()` to the 2-stamina travel drain in `_do_move()`:
   ```python
   stamina_drain = 2 * self._stamina_multiplier()
   ```

---

## Phase D — Combat Hooks

7. In `GameSession._start_combat()` (wherever CombatSession is instantiated):
   - If `_mounted`:
     - `_was_mounted = True`
     - `_mounted = False`
     - Print: `"The party dismounts as combat begins."`
8. In `GameSession._on_combat_end()` (victory and flee paths):
   - If `_was_mounted` and current room `room_type == "outdoor"`:
     - `_mounted = True`
     - `_was_mounted = False`
     - Print: `"The party remounts and continues on."`
   - If current room is not outdoor: `_was_mounted = False` (leave dismounted)

---

## Phase E — Commands

9. Add `RIDE` handler in `_handle_navigation()`:
   - Check `_horse_count() > 0`; error if no horses
   - Check current room `room_type == "outdoor"`; error if indoors/underground
   - Set `_mounted = True`
   - Print: `"The party mounts up and prepares to ride."`
10. Add `DISMOUNT` handler:
    - Set `_mounted = False`
    - Print: `"The party dismounts."`
11. Add `HORSES` handler:
    - Print horse count, party size, current stamina drain reduction %
    - Format: `"Horses: 2 | Party: 4 | Stamina drain: -30%"`

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/data/items/misc.json` | Horse item definition |
| `server/engine/game.py` | `_mounted`, `_horses_outside`, `_was_mounted` state; `_horse_count()`, `_stamina_multiplier()`; movement hook; combat hooks; RIDE, DISMOUNT, HORSES handlers |

---

## Verification Checklist

- [ ] Acquire horse; `RIDE` in outdoor room → mounted state confirmed
- [ ] Walk 10 rooms while mounted (1 horse, 1 member) → stamina drains at 40% of normal rate (60% reduction)
- [ ] Walk 10 rooms while mounted (1 horse, 4 members) → ~25% reduction (ratio = 0.25)
- [ ] `DISMOUNT` → stamina drain returns to full rate
- [ ] Enter building while mounted → *"Your horses wait outside"* message; `_mounted = False`
- [ ] Exit building → *"Your horses fall back into step"* message; `_mounted = True`
- [ ] Start combat while mounted → *"The party dismounts as combat begins."*
- [ ] Win combat in outdoor room → *"The party remounts and continues on."*
- [ ] Win combat in dungeon → party stays dismounted
- [ ] `HORSES` command → shows correct horse count and reduction percentage
- [ ] `RIDE` indoors → error message
- [ ] `RIDE` with no horses in inventory → error message
