# Phase 2: Survival Stats — Hunger, Thirst & Stamina
**Status: NOT STARTED**
**Depends on: Phase 1 (temperature affects thirst rate)**

## Overview
Introduce party-level survival pressure. Each character tracks hunger, thirst, and stamina individually, but these are exposed to the player as a single averaged party stat. Survival stats create meaningful resource management and interact with the world clock, temperature, and resting.

---

## Per-Character Stats

| Stat | Max | Drain Rate | Notes |
|------|-----|------------|-------|
| Stamina | 100 | Movement & combat | Recovers while sitting/resting |
| Hunger | 100 | Slow decay over time | Reduced by eating food |
| Thirst | 100 | Faster decay than hunger | Accelerated in hot/scorching weather |

### Thirst Drain Modifiers (from WorldClock temperature)
| Temp label | Thirst multiplier |
|------------|------------------|
| Freezing–Cool | 1.0× (base) |
| Comfortable | 1.0× |
| Hot | 1.5× |
| Scorching | 2.0× |

---

## Party-Wide Aggregation

The party stat is a **pooled fraction**:

```
party_hunger = sum(member.hunger) / sum(member.max_hunger)
```

### Example
- Player: hunger 35/100
- NPC joins with hunger 70/100
- Party hunger = 105/200 = 52.5%

When a party member joins or leaves, the aggregate recalculates automatically. Penalties are applied to the **whole party** based on the aggregate.

---

## Penalties

Penalties apply when the **party aggregate** falls below thresholds.

### Stamina Penalties
| Stamina % | Effect |
|-----------|--------|
| > 30% | None |
| 10–30% | -15% to all combat stats |
| 0–10% | Party cannot move; must rest |
| 0% | Movement blocked until >= 10% restored |

### Hunger / Thirst Penalties (applied together when both are low)
| H/T aggregate % | Effect |
|-----------------|--------|
| > 40% | None |
| 20–40% | -10% to combat stats |
| < 20% | -25% to combat stats; stamina drains 50% faster |
| 0% | Heavy penalties across all combat rolls |

---

## Stamina Drain

| Action | Drain amount |
|--------|-------------|
| Moving one room | 2 stamina (party average) |
| Combat encounter (per tick) | 1 per combatant per action |
| Fleeing | 5 (flat drain) |

---

## Recovery

### Resting
- Sitting (out of combat, no action) → +1 stamina/game-minute
- Campfire rest (`REST` command) → full stamina restore, resets hunger/thirst drain timer
- Sleep (future: beds in inns) → full restore + slower hunger drain for next period

---

## Commands

| Command | Description |
|---------|-------------|
| `STATUS` | Show party survival stats (hunger %, thirst %, stamina %) |
| `SIT` / `REST` | Begin passive stamina recovery (out of combat) |
| `STAND` | Stop resting |
| `DRINK <item>` | Drink a water/beverage item from inventory |
| `EAT <item>` | Eat a food item from inventory |

### Enhanced Commands
- `PARTY`: add a survival row (Stamina / Hunger / Thirst aggregate %)
- `LOOK`: if party stamina is 0, show a warning line

---

## Data Changes

### Character fields to add
```python
hunger: float = 100.0
max_hunger: float = 100.0
thirst: float = 100.0
max_thirst: float = 100.0
stamina: float = 100.0
max_stamina: float = 100.0
```

### Items to add
- Water Flask (restores 40 thirst)
- Waterskin (restores 80 thirst, refillable at wells/streams — future)
- Hard Bread (restores 30 hunger)
- Dried Meat (restores 50 hunger)
- Rations (restores 40 hunger + 20 thirst)

### Help entries to add
- `HELP STATUS`, `HELP STAMINA`, `HELP HUNGER`, `HELP REST`

---

## Notes
- Survival stats are NOT persisted mid-combat; they save to DB on REST or SAVE
- Phase 4 (Food & Consumables) adds buff-granting food items on top of this system
- Phase 6 (Horses) will reduce stamina drain from movement when mounted
