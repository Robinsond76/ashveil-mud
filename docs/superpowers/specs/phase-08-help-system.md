# Phase 8: Help System Overhaul
**Status: NOT STARTED**
**Depends on: Phase 1 (partial implementation already in place)**

## Overview
The `HELP` command becomes fully contextual. With no arguments it shows only commands valid in the player's current `State`. Every command has a dedicated help entry. The Phase 1 implementation added help for environment commands — this phase extends coverage to all game commands.

---

## Design Principles

1. **Contextual bare `HELP`** — `HELP` with no args shows the command list for current state only.
2. **Always routable** — `HELP <topic>` works from any state regardless of context.
3. **No dead ends** — Every command listed in any help screen must itself have a `HELP <cmd>` entry.
4. **Consistent layout** — All topics follow the same format: command syntax, brief description, examples, see also.

---

## Help by State

### `CONNECT` / `CREATION`
```
--- HELP ---
You are creating a character. Available choices:

  HELP RACES       — learn about available races
  HELP CLASSES     — learn about available classes

Type your responses as prompted.
```

### `NAVIGATION` (most common state)
```
--- HELP ---
You are exploring Ashveil. Available commands:

  Movement         NORTH / N, SOUTH / S, EAST / E, WEST / W
  Look             LOOK / L
  Inventory        INV / INVENTORY, EQUIP, UNEQUIP, DROP, TAKE
  Character        STATS, SKILLS
  Combat           ATTACK <target>
  Environment      TIME, WEATHER, LIGHT, ENVDETAILS / ENV
  Lighting         LIT <item>, EXTINGUISH / DOUSE
  Camping          CAMP (enter campfire mode)

Type HELP <command> for details on any command.
```

### `CAMPFIRE`
```
--- HELP ---
You are resting at camp. Available commands:

  REST             Rest the party (recovers HP, MP, stamina)
  PARTY            Show party status
  STRATEGY <name>  Set a combatant's strategy
  LEAVE            Break camp and return to exploring

Type HELP <command> for details on any command.
```

### `STRATEGY`
```
--- HELP ---
You are setting combat strategies. Available commands:

  STRATEGY <name> <tactic>   Set strategy for named party member or enemy
  DONE                       Confirm strategies and return

  Tactics: AGGRESSIVE, DEFENSIVE, SUPPORT, FLEE
  Type HELP STRATEGY for full details.
```

### `COMBAT`
```
--- HELP ---
You are in combat. Available commands:

  ATTACK <target>  Attack the named enemy
  CAST <spell>     Cast a spell (mage only)
  USE <item>       Use a consumable item
  FLEE             Attempt to flee combat
  PARTY            Show party HP/MP status

Battles are tick-based. Your strategy runs automatically; use commands to override.
Type HELP COMBAT for full details.
```

---

## Topic Registry

All `HELP <topic>` entries to implement:

### Navigation
| Topic | Content |
|-------|---------|
| `HELP LOOK` / `HELP L` | Shows current room description and exits |
| `HELP NORTH` / `HELP MOVE` | Move in the given direction |
| `HELP INV` / `HELP INVENTORY` | List all items carried by the party |
| `HELP EQUIP` | Equip an item: `EQUIP <member> <item>` |
| `HELP UNEQUIP` | Unequip a slot: `UNEQUIP <member> <slot>` |
| `HELP DROP` | Drop an item from inventory |
| `HELP TAKE` / `HELP PICK` | Pick up an item from the room |
| `HELP STATS` | Show character statistics |
| `HELP SKILLS` | List known skills and their effects |
| `HELP ATTACK` | Start combat with a target: `ATTACK <name>` |
| `HELP CAMP` | Enter campfire mode |

### Environment (Phase 1, already partially done)
| Topic | Content |
|-------|---------|
| `HELP TIME` | Current game time, day, moon phase |
| `HELP WEATHER` | Current weather and forecast |
| `HELP LIGHT` / `HELP LIGHTING` | Current light level and tier |
| `HELP ENVDETAILS` / `HELP ENV` | Numeric breakdown of environment conditions |
| `HELP LIT` | Light a carried torch or lantern |
| `HELP EXTINGUISH` / `HELP DOUSE` | Put out a lit light source |

### Combat
| Topic | Content |
|-------|---------|
| `HELP COMBAT` | Overview of tick-based combat, targeting, strategies |
| `HELP FLEE` | How flee attempts work; success factors |
| `HELP STRATEGY` / `HELP STRATEGIES` | Tactics explained: AGGRESSIVE, DEFENSIVE, SUPPORT, FLEE |
| `HELP CAST` | Casting syntax; see also `HELP <spell name>` |

### Campfire
| Topic | Content |
|-------|---------|
| `HELP REST` | How resting works: HP/MP/stamina recovery rates |
| `HELP PARTY` | Show all party member status |

### Survival (Phase 2+)
| Topic | Content |
|-------|---------|
| `HELP HUNGER` | Hunger mechanic, drain rate, penalties |
| `HELP THIRST` | Thirst mechanic |
| `HELP STAMINA` | Stamina: travel drain, combat penalty |
| `HELP SURVIVAL` | Overview of all survival stats |

### Inventory / Weight (Phase 5+)
| Topic | Content |
|-------|---------|
| `HELP WEIGHT` | Carry weight, thresholds, overweight penalty |
| `HELP BACKPACK` | Backpack slot rules |
| `HELP CART` | Cart usage: outdoor-only, weight limit |

### Mounts (Phase 6+)
| Topic | Content |
|-------|---------|
| `HELP RIDE` | Mounting horses |
| `HELP DISMOUNT` | Dismounting |
| `HELP HORSES` | Party horse count and stamina effect |

### Wizard (Phase 7+)
| Topic | Content |
|-------|---------|
| `HELP WIZARD` | Mage class overview: constraints, strengths |
| `HELP SPELLS` | List of known spells |
| `HELP CASTING` | Cast times, interruption, cancel |

---

## Implementation Plan

### `game.py` changes

#### `_send_help(topic: str = "")`
- Already exists from Phase 1
- Currently handles: `COMBAT`, `LIGHT`, `LIT`, `WEATHER`, `TIME`, `ENVDETAILS`, `ATTACK`, bare

**Changes:**
- Add `self._state` awareness for bare `HELP`
- Add all missing topic entries from the registry table above
- Move help strings to a dedicated `_HELP_TOPICS: dict[str, str]` module-level constant for maintainability

```python
_HELP_TOPICS: dict[str, str] = {
    "LOOK": "...",
    "MOVE": "...",
    ...
}
```

#### `_help_for_state(state: State) -> str`
- New helper
- Returns contextual command list based on current `State`
- Called by `_send_help("")` when topic is empty

### Data changes
None required — help is entirely in-memory strings.

---

## Formatting Standard

Every `HELP <topic>` response follows:
```
--- HELP: <TOPIC> ---
<One-line description>

Usage:
  <CMD> [args]

Details:
  <2–4 bullet points of detail>

Examples:
  <CMD> <example1>
  <CMD> <example2>

See also: <RELATED>, <TOPICS>
```

---

## Notes
- Phase 1 implemented help for: `COMBAT`, `LIGHT`, `LIT`, `WEATHER`, `TIME`, `ENVDETAILS`, `ATTACK` — these need to be updated to match the new formatting standard
- Keep help strings short. Players are in a terminal; paragraphs are walls of text.
- `HELP <unknown>` → *"No help found for '<topic>'. Type HELP to see available commands."*
