# Plan: Phase 2 — Survival Stats (Hunger, Thirst & Stamina)

**Spec:** [phase-02-survival-stats.md](../specs/phase-02-survival-stats.md)
**Depends on:** Phase 1 (WorldClock — temperature labels for thirst multipliers) ✅ COMPLETED
**Status:** NOT STARTED

---

## Overview

Add three survival stats (hunger, thirst, stamina) to `Character`, aggregate them at party level, apply combat/movement penalties when low, and wire drain/recovery to the world clock and REST command.

---

## Phase A — Data Model

1. Add `hunger: float`, `thirst: float`, `stamina: float` (each default 100.0) to `Character` in `server/engine/character.py`
2. Add class constants `MAX_HUNGER = MAX_THIRST = MAX_STAMINA = 100`
3. Add `hunger_drain_rate() -> float` helper to `Character`
4. Add `thirst_drain_rate(temp_label: str) -> float` helper using the WorldClock temp-label → multiplier table:
   - `Freezing` / `Bitter Cold` / `Cold` / `Cool` / `Comfortable` → 1.0×
   - `Hot` → 1.5×
   - `Scorching` → 2.0×

---

## Phase B — Party Aggregation

5. Add `_party_survival_aggregate() -> tuple[float, float, float]` to `GameSession` in `server/engine/game.py`
   - Returns `(avg_hunger_pct, avg_thirst_pct, avg_stamina_pct)` across all party members
6. Add `_apply_survival_penalties() -> tuple[float, bool]` helper
   - Returns `(combat_stat_multiplier, movement_blocked)`
   - Applies thresholds from spec: hunger/thirst < 40% → 0.9×, < 20% → 0.75×, stamina < 30% → 0.85×

---

## Phase C — Drain Loop

7. In `GameSession._on_clock_tick()` (already subscribed for weather): decrement hunger and thirst per game-minute tick using each character's drain rates
8. Stamina drain:
   - Movement: deduct 2 (party average) in `_do_move()`
   - Combat: deduct 1 per combatant per action tick in `server/engine/combat.py`
   - Fleeing: deduct 5 flat in combat flee handler

---

## Phase D — Penalties Applied

9. In `combat.py` `_resolve_action()`: multiply damage and dodge rolls by the survival penalty multiplier from `_apply_survival_penalties()`
10. In `game.py` `_do_move()`: block move and print warning if `party_stamina_pct < 10%`; block entirely if `party_stamina_pct == 0%`

---

## Phase E — Recovery

11. In `GameSession._do_rest()` (CAMPFIRE state): restore stamina to 100 for all party members; reset hunger/thirst drain timer
12. Add `_sitting: bool` flag to `GameSession`
13. `SIT` command in NAVIGATION state: set `_sitting = True`, begin passive stamina flag
14. In `_on_clock_tick()`: if `_sitting` and not in combat → add +1 stamina/game-minute to all party
15. `STAND` command: set `_sitting = False`

---

## Phase F — Commands

16. Add `STATUS` handler in `_handle_navigation()` → display party hunger%, thirst%, stamina%
17. Add `SIT` and `STAND` handlers
18. Add `EAT <item>` stub handler: validate item type is `food`, restore hunger; full buff implementation in Phase 4
19. Add `DRINK <item>` stub handler: validate item type is `drink`/`consumable`, restore thirst; full implementation in Phase 4
20. Extend `PARTY` command output with a survival row (Stamina / Hunger / Thirst aggregate %)
21. Extend `LOOK` with a warning line if party stamina == 0

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/engine/character.py` | Add fields, drain rate helpers |
| `server/engine/game.py` | Commands, party aggregate, penalties, drain loop, recovery |
| `server/engine/combat.py` | Apply survival penalty multiplier to damage/dodge rolls, stamina drain per tick |
| `server/engine/world_clock.py` | Confirm temperature label is accessible from tick callback |

---

## Verification Checklist

- [ ] Walk 50 rooms → stamina depletes; at 0%, `LOOK` shows warning and movement is blocked
- [ ] `REST` at campfire → stamina returns to 100 for all party members
- [ ] In hot weather (temp label "Hot"): `STATUS` shows thirst draining at 1.5× rate
- [ ] In scorching weather: thirst drains at 2.0× rate
- [ ] Enter combat at <20% hunger+thirst aggregate → combat stat penalty visible in output
- [ ] Enter combat at <10% stamina → -15% to combat stats shown
- [ ] `EAT hard_bread` → hunger increases; `DRINK waterskin` (stub) → thirst increases
- [ ] Party with NPC companion: aggregate recalculates correctly when NPC joins/leaves
