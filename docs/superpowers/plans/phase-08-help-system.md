# Plan: Phase 8 — Help System Overhaul

**Spec:** [phase-08-help-system.md](../specs/phase-08-help-system.md)
**Depends on:** Phase 1 (partial help implementation already in place ✅)
**Status:** NOT STARTED

---

## Overview

Make `HELP` contextual by game state, centralize all help strings into a module-level `_HELP_TOPICS` dict, and fill in every missing topic entry. Every command listed in any help screen must have its own `HELP <cmd>` entry.

---

## Step 1 — Extract Existing Help Strings

1. In `server/engine/game.py`, locate the existing `_send_help()` method
2. Extract all existing help strings (currently inline in `_send_help()`) into a module-level constant at the top of the file:
   ```python
   _HELP_TOPICS: dict[str, str] = {
       "COMBAT": "...",
       "LIGHT": "...",
       "WEATHER": "...",
       ...
   }
   ```
3. Keys are uppercase topic names; values are the full multi-line help string

---

## Step 2 — State-Aware Bare HELP

4. Add `_help_for_state(state: State) -> str` helper function in `game.py`
5. Returns the contextual command list for the given state:

   **CONNECT / CREATION:**
   ```
   --- HELP ---
   You are creating a character. Available choices:

     HELP RACES       — learn about available races
     HELP CLASSES     — learn about available classes

   Type your responses as prompted.
   ```

   **NAVIGATION:**
   ```
   --- HELP ---
   You are exploring [room name]. Available commands:

     Movement         NORTH / N, SOUTH / S, EAST / E, WEST / W
     Look             LOOK / L
     Inventory        INV / INVENTORY, EQUIP, UNEQUIP, DROP, TAKE
     Character        STATS, SKILLS, STATUS
     Combat           ATTACK <target>
     Environment      TIME, WEATHER, LIGHT, ENVDETAILS / ENV
     Lighting         LIT <item>, EXTINGUISH / DOUSE
     Camping          CAMP (enter campfire mode)

   Type HELP <command> for details on any command.
   ```

   **CAMPFIRE:**
   ```
   --- HELP ---
   You are resting at camp. Available commands:

     REST             Rest the party (recovers HP, MP, stamina)
     PARTY            Show party status
     STRATEGY <name>  Set a combatant's strategy
     LEAVE            Break camp and return to exploring

   Type HELP <command> for details on any command.
   ```

   **STRATEGY:**
   ```
   --- HELP ---
   You are setting combat strategies. Available commands:

     STRATEGY <name> <tactic>   Set strategy for named party member or enemy
     DONE                       Confirm strategies and return

     Tactics: AGGRESSIVE, DEFENSIVE, SUPPORT, FLEE
     Type HELP STRATEGY for full details.
   ```

   **COMBAT:**
   ```
   --- HELP ---
   You are in combat. Available commands:

     ATTACK <target>  Attack the named enemy
     CAST <spell>     Cast a spell (mage only)
     USE <item>       Use a consumable item
     FLEE             Attempt to flee combat
     PARTY            Show party HP/MP status

   Battles are tick-based. Your strategy runs automatically.
   Type HELP COMBAT for full details.
   ```

6. Update `_send_help(topic: str = "")`:
   - `topic == ""` → call `_help_for_state(self._state)` and send result
   - `topic != ""` → look up `_HELP_TOPICS[topic.upper()]`; if not found, send: `"No help found for '{topic}'. Type HELP for available commands."`

---

## Step 3 — Fill In All Missing Topic Entries

Add every entry from the spec registry table to `_HELP_TOPICS`. The formatting standard for all entries:
```
--- HELP: <TOPIC> ---
<brief description>

Usage: <COMMAND> [args]

Examples:
  <example 1>
  <example 2>

See also: <related commands>
```

### Navigation Topics (add if missing)
| Key | Content |
|-----|---------|
| `LOOK` / `L` | Shows current room description and exits |
| `NORTH` / `SOUTH` / `EAST` / `WEST` / `MOVE` | Move in the given direction |
| `INV` / `INVENTORY` | List all items carried by the party |
| `EQUIP` | Equip an item: `EQUIP <member> <item>` |
| `UNEQUIP` | Unequip a slot: `UNEQUIP <member> <slot>` |
| `DROP` | Drop an item from inventory into the room |
| `TAKE` / `PICK` | Pick up an item from the room |
| `STATS` | Show character statistics |
| `SKILLS` | List known skills; `SKILLS UTILITY`, `SKILLS COMBAT` |
| `ATTACK` | Start combat: `ATTACK <enemy name>` |
| `CAMP` | Enter campfire mode |
| `STATUS` | Show party survival stats (hunger, thirst, stamina) |
| `SIT` / `STAND` | Begin or end passive stamina recovery |

### Environment Topics (Phase 1 — verify these exist, add if missing)
| Key | Content |
|-----|---------|
| `TIME` | Current game time, day, moon phase |
| `WEATHER` | Current weather and forecast |
| `LIGHT` / `LIGHTING` | Current light level and tier |
| `ENVDETAILS` / `ENV` | Numeric breakdown of environment conditions |
| `LIT` | Light a carried torch or lantern |
| `EXTINGUISH` / `DOUSE` | Put out a lit light source |

### Combat Topics
| Key | Content |
|-----|---------|
| `COMBAT` | Overview of tick-based combat, targeting, strategies |
| `FLEE` | How flee attempts work; success factors |
| `STRATEGY` / `STRATEGIES` | Tactics: AGGRESSIVE, DEFENSIVE, SUPPORT, FLEE |
| `CAST` | Casting syntax; see also `HELP <spell name>` |

### Campfire Topics
| Key | Content |
|-----|---------|
| `REST` | HP/MP/stamina recovery rates at camp |
| `PARTY` | Show all party member status |

### Survival Topics (Phase 2+)
| Key | Content |
|-----|---------|
| `HUNGER` | Hunger mechanic, drain rate, penalties |
| `THIRST` | Thirst mechanic, temperature modifiers |
| `STAMINA` | Travel drain, combat penalty, recovery |
| `SURVIVAL` | Overview of all three survival stats |

### Inventory / Weight Topics (Phase 5+)
| Key | Content |
|-----|---------|
| `WEIGHT` | Carry weight thresholds, overweight penalty |
| `BACKPACK` | Backpack slot rules, `back` equipment slot |
| `CART` | Cart usage: outdoor-only, weight limit |
| `GIVE` | Transfer items between party members |
| `STASH` / `LOAD` | Load items into the cart |
| `UNLOAD` | Retrieve items from the cart |

### Mount Topics (Phase 6+)
| Key | Content |
|-----|---------|
| `RIDE` | Mount available horses |
| `DISMOUNT` | Dismount the party |
| `HORSES` / `MOUNTS` | Party horse count and stamina reduction |

### Wizard Topics (Phase 7+)
| Key | Content |
|-----|---------|
| `WIZARD` | Mage class overview: constraints, strengths |
| `SPELLS` | List of known spells with mana cost and cast time |
| `CASTING` | Cast times, interruption, cancellation |
| Per-spell entries | One entry per spell ID (e.g. `FIREBALL`, `FROST_BOLT`) |

### Multiplayer Topics (Phase 9+)
| Key | Content |
|-----|---------|
| `SAY` | Send a message to players in the same room |
| `EMOTE` / `ME` | Perform a visible action |
| `SHOUT` | Broadcast to all connected players |
| `PLAYERS` | List all currently connected players |
| `MULTIPLAYER` | Overview of multiplayer features |

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/engine/game.py` | `_HELP_TOPICS` constant, `_help_for_state()` helper, updated `_send_help()` |

*All changes are in a single file.*

---

## Verification Checklist

- [ ] In NAVIGATION state: bare `HELP` shows navigation command list, not combat list
- [ ] In CAMPFIRE state: bare `HELP` shows campfire commands only
- [ ] In COMBAT state: bare `HELP` shows combat commands only
- [ ] `HELP HUNGER` from any state → shows hunger mechanics entry
- [ ] `HELP REST` → shows rest recovery details
- [ ] `HELP FIREBALL` → shows fireball spell entry
- [ ] `HELP NONEXISTENT` → graceful fallback message (no crash)
- [ ] Every command listed in each state's HELP output has a corresponding `HELP <cmd>` entry
- [ ] No dead ends: following HELP links never leads to a missing topic
