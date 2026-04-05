# Phase 6: Horses & Mounts
**Status: NOT STARTED**
**Depends on: Phase 2 (stamina), Phase 5 (cart vehicle logic)**

## Overview
Horses reduce stamina drain during travel. They behave similarly to the cart — automatically staying outside indoor/underground rooms. Full stamina reduction requires one horse per party member; partial otherwise.

---

## Horse Rules

### Behaviour
- Horses are items in the party's possession (not characters)
- They follow the party automatically in `outdoor` rooms
- On entering `indoor` or `underground` rooms, horses are left outside automatically
  - Message: *"Your horses wait outside at [room name]."*
- On returning to outdoor, horses rejoin automatically
  - Message: *"Your horses fall back into step with the party."*
- During combat, all riders are **automatically dismounted**
  - Message: *"The party dismounts as combat begins."*
- After combat, riders **automatically remount**
  - Message: *"The party remounts and continues on."*
- While fleeing combat, horses come along (treated as fleeing with the party)

### Stamina Reduction
| Horses : Party Members | Stamina Drain Reduction |
|------------------------|------------------------|
| 0 horses | 0% reduction |
| 1 horse per 2+ members | 25% reduction |
| 1 horse per member (full) | 60% reduction |
| More horses than members | Capped at 60% |

Formula:
```
ratio = min(1.0, horse_count / max(1, party_size))
stamina_multiplier = 1.0 - (0.60 * ratio)
```

---

## Commands

| Command | Description |
|---------|-------------|
| `RIDE` | Mount all available horses (one per member, auto-assigned) |
| `DISMOUNT` | Manually dismount the entire party |
| `HORSES` | Show how many horses the party has |

---

## Horse Item Definition

```json
{
  "id": "horse",
  "name": "Horse",
  "description": "A sturdy riding horse. Mounts automatically when travelling and reduces how quickly your party tires.",
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

### Variants (future)
| Item | Reduction (full) | Notes |
|------|-----------------|-------|
| Horse | 60% | Standard |
| Warhorse | 60% + combat buff | Doesn't fully break in combat |
| Mule | 40% | Cheaper, slower |
| Draft Horse | 30% + +50 cart weight | Primarily for cart hauling |

---

## Data Changes

### GameSession fields to add
```python
_horses: list[str] = []            # list of "horse" item_ids in party possession
_mounted: bool = False             # is the party currently mounted?
_horses_outside: bool = False      # horses waiting outside current room
```

### Movement hook
In `_do_move()`:
- Check `room.room_type` of destination
- If `indoor` or `underground` and mounted → dismount, set `_horses_outside = True`, print message
- If returning to `outdoor` and `_horses_outside` → remount (if player was mounted before), print message

### Combat hooks
- Combat start: if mounted → dismount, store mounted state
- Combat end (victory/flee): restore mounted state

---

## Help entries to add
- `HELP RIDE`, `HELP DISMOUNT`, `HELP HORSES`, `HELP MOUNTS`

---

## Notes
- A party with 4 members and 2 horses gets partial reduction. Player is informed with `HORSES` command.
- Horses cannot enter combat as active combatants (future: cavalry charge could be a warrior skill)
- Cart + horses together create a travel-mode party that must "gear down" for dungeons
- Horse purchase locations: stable in Ashveil (future vendor)
