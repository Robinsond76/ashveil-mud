# Command Shorthands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 20+ command shorthands (aliases) across the game, update all help documentation to show these aliases, and update GETTING_STARTED.md.

**Architecture:** Add aliases to `NavigationHandler.commands` dict in `navigation.py`, update `_HELP_TOPICS` in `help_registry.py` to show aliases in usage lines, and update command tables in `GETTING_STARTED.md`.

**Tech Stack:** Python 3 (FastAPI), JSON-like help registry, Markdown documentation

---

## Overview of Changes

**Files to Modify:**
1. `server/engine/states/navigation.py` - Add 20 aliases to commands dict
2. `server/engine/help_registry.py` - Update 20+ help entries to show aliases
3. `GETTING_STARTED.md` - Update command reference tables

**Aliases to Add:**
- `l` → look
- `x` → examine  
- `eq` → equip
- `uneq` → unequip
- `k` → attack
- `p` → party
- `sk` → skills
- `ss` → status
- `b` → buffs
- `t` → talk
- `dis` → dismiss
- `sv` → save
- `'` → say
- `ti` → time
- `wea` → weather
- `upg` → upgrade
- `lrn` → learn
- `dr` → drink
- `ea` → eat
- `giv` → give
- `hor` → horses

---

## Phase 1: Add Command Aliases to Navigation Handler

### Task 1: Add All Shorthands to Commands Dict

- [ ] **Step 1: Write the failing test**

Create comprehensive test for all new aliases:

```python
# tests/server/engine/test_navigation_aliases.py
import pytest
from server.engine.states.navigation import NavigationHandler


# Define all expected aliases and their primary commands
EXPECTED_ALIASES = {
    "l": "look",
    "x": "examine",
    "eq": "equip",
    "uneq": "unequip",
    "k": "attack",
    "p": "party",
    "sk": "skills",
    "ss": "status",
    "b": "buffs",
    "t": "talk",
    "dis": "dismiss",
    "sv": "save",
    "'": "say",
    "ti": "time",
    "wea": "weather",
    "upg": "upgrade",
    "lrn": "learn",
    "dr": "drink",
    "ea": "eat",
    "giv": "give",
    "hor": "horses",
}


def test_all_aliases_exist():
    """Verify all expected command aliases are registered."""
    handler = NavigationHandler()
    
    for alias, primary in EXPECTED_ALIASES.items():
        assert alias in handler.commands, f"Alias '{alias}' not found in commands dict"
        primary_handler = handler.commands.get(primary)
        alias_handler = handler.commands.get(alias)
        assert alias_handler == primary_handler, f"Alias '{alias}' should map to same handler as '{primary}'"


def test_no_conflicting_aliases():
    """Ensure no alias conflicts with existing commands."""
    handler = NavigationHandler()
    
    # These are the built-in directional commands that must not be overridden
    reserved = {"n", "s", "e", "w", "u", "d", "go"}
    
    for reserved_cmd in reserved:
        assert reserved_cmd not in EXPECTED_ALIASES, f"'{reserved_cmd}' is reserved and cannot be an alias"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/server/engine/test_navigation_aliases.py -v
```

Expected: FAIL - most aliases not in commands dict yet.

- [ ] **Step 3: Add all aliases to commands dict**

Edit `server/engine/states/navigation.py`, add aliases to the `commands` dict in `__init__`:

**Find the commands dict (around line 51-107) and add these entries:**

```python
self.commands: dict[str, Callable] = {
    # Existing entries remain...
    "look": self._do_look,
    "l": self._do_look,                    # NEW: shorthand
    "examine": self._do_examine,
    "x": self._do_examine,                 # NEW: shorthand
    "inventory": self._do_inventory,
    "inv": self._do_inventory,
    "i": self._do_inventory,
    "equip": self._do_equip,
    "eq": self._do_equip,                  # NEW: shorthand
    "unequip": self._do_unequip,
    "uneq": self._do_unequip,              # NEW: shorthand
    "drop": self._do_drop,
    "pick": self._do_pick_up,
    "take": self._do_pick_up,
    "get": self._do_pick_up,
    "give": self._do_give,
    "giv": self._do_give,                  # NEW: shorthand
    "load": self._do_load_cart,
    "stash": self._do_load_cart,
    "unload": self._do_unload_cart,
    "stats": self._do_stats,
    "stat": self._do_stats,
    "skills": self._do_skills,
    "sk": self._do_skills,                 # NEW: shorthand
    "learn": self._do_learn,
    "lrn": self._do_learn,                 # NEW: shorthand
    "modifiers": self._do_modifiers,
    "mods": self._do_modifiers,
    "upgrade": self._do_upgrade,
    "upg": self._do_upgrade,               # NEW: shorthand
    "party": self._do_party,
    "p": self._do_party,                   # NEW: shorthand
    "talk": self._do_talk,
    "t": self._do_talk,                    # NEW: shorthand
    "dismiss": self._do_dismiss,
    "dis": self._do_dismiss,               # NEW: shorthand
    "campfire": self._do_campfire,
    "rest": self._do_campfire,
    "status": self._do_status,
    "ss": self._do_status,                 # NEW: shorthand
    "sit": self._do_sit,
    "stand": self._do_stand,
    "eat": self._do_eat,
    "ea": self._do_eat,                    # NEW: shorthand
    "drink": self._do_drink,
    "dr": self._do_drink,                  # NEW: shorthand
    "buffs": self._do_buffs,
    "b": self._do_buffs,                    # NEW: shorthand
    "attack": self._do_attack,
    "k": self._do_attack,                  # NEW: shorthand
    "use": self._do_use,
    "save": self._do_save,
    "sv": self._do_save,                   # NEW: shorthand
    "time": self._do_time,
    "ti": self._do_time,                   # NEW: shorthand
    "weather": self._do_weather,
    "wea": self._do_weather,               # NEW: shorthand
    "light": self._do_light,
    "lighting": self._do_light,
    "envdetails": self._do_envdetails,
    "env": self._do_envdetails,
    "lit": self._do_lit,
    "extinguish": self._do_extinguish,
    "douse": self._do_extinguish,
    "ride": self._do_ride,
    "dismount": self._do_dismount,
    "horses": self._do_horses,
    "hor": self._do_horses,                # NEW: shorthand
    "say": self._do_say,
    "'": self._do_say,                     # NEW: apostrophe shorthand
    "emote": self._do_emote,
    "me": self._do_emote,
    "shout": self._do_shout,
    "ooc": self._do_shout,
    "help": self._do_help,
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/server/engine/test_navigation_aliases.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/states/navigation.py tests/server/engine/test_navigation_aliases.py
git commit -m "feat: add 20 command shorthands/aliases

Added common MUD-style shorthand commands:
- Navigation: l (look), k (attack)
- Inventory: eq (equip), uneq (unequip), x (examine)
- Character: sk (skills), ss (status), b (buffs), upg (upgrade)
- Party: p (party), t (talk), dis (dismiss)
- Survival: ea (eat), dr (drink)
- Environment: ti (time), wea (weather)
- Combat: k (attack)
- System: sv (save), giv (give), hor (horses), lrn (learn)
- Chat: ' (apostrophe for say)"
```

---

## Phase 2: Update Help Registry

### Task 2: Update All Help Topics with Shorthand Notation

- [ ] **Step 1: Write the failing test**

```python
# tests/server/test_help_registry_aliases.py
import pytest
from server.engine.help_registry import _HELP_TOPICS


def test_aliases_in_help_text():
    """Verify help topics mention their shorthand forms."""
    # Map of primary command to expected shorthand notation in help
    expected_aliases_in_help = {
        "LOOK": ["L"],
        "EXAMINE": ["X"],
        "EQUIP": ["EQ"],
        "UNEQUIP": ["UNEQ"],
        "ATTACK": ["K"],
        "PARTY": ["P"],
        "SKILLS": ["SK"],
        "STATUS": ["SS"],
        "BUFFS": ["B"],
        "TALK": ["T"],
        "DISMISS": ["DIS"],
        "SAVE": ["SV"],
        "SAY": ["'"],
        "TIME": ["TI"],
        "WEATHER": ["WEA"],
        "UPGRADE": ["UPG"],
        "LEARN": ["LRN"],
        "DRINK": ["DR"],
        "EAT": ["EA"],
        "GIVE": ["GIV"],
        "HORSES": ["HOR"],
    }
    
    for command, aliases in expected_aliases_in_help.items():
        help_text = _HELP_TOPICS.get(command, "")
        help_upper = help_text.upper()
        
        # Check that at least one alias form appears
        found_alias = False
        for alias in aliases:
            # Look for patterns like "(or X)" or "Usage: COMMAND (or X)"
            if f"(or {alias})" in help_upper or f"/ {alias}" in help_upper:
                found_alias = True
                break
        
        assert found_alias, f"Help for {command} should mention aliases {aliases}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/server/test_help_registry_aliases.py -v
```

Expected: FAIL - aliases not yet in help text.

- [ ] **Step 3: Update help topics with aliases**

Edit `server/engine/help_registry.py`. For each help topic, update the usage line to show the alias.

**Updates needed:**

```python
# Line 15-30: LOOK and L already exist, good

# Add new EXAMINE entry and X alias (line 31, after WEST)
"EXAMINE": _box("HELP: EXAMINE", [
    "  Examine an item or NPC in detail.",
    "  Usage: EXAMINE <target>  (or X <target>)",
    "  Examples:",
    "    EXAMINE sword",
    "    X gareth",
    "  See also: LOOK, L, INV",
]),
"X": _box("HELP: EXAMINE (X)", [
    "  Examine an item or NPC in detail.",
    "  Usage: EXAMINE <target>  (or X <target>)",
    "  Examples:",
    "    EXAMINE sword",
    "    X gareth",
    "  See also: LOOK, L, INV",
]),

# Update EQUIP (line 92)
"EQUIP": _box("HELP: EQUIP", [
    "  Equip an item on a party member.",
    "  Usage: EQUIP <member> <item>  (or EQ <member> <item>)",
    "  Examples:",
    "    EQUIP Hero iron_sword",
    "    EQ Mira leather_armor",
    "  Details:",
    "    Equipping replaces whatever is in that slot.",
    "    Mages suffer spell power penalties for heavy armor.",
    "  See also: UNEQUIP, UNEQ, INV, WIZARD",
]),
"EQ": _box("HELP: EQUIP (EQ)", [
    "  Equip an item on a party member.",
    "  Usage: EQUIP <member> <item>  (or EQ <member> <item>)",
    "  Examples:",
    "    EQUIP Hero iron_sword",
    "    EQ Mira leather_armor",
    "  See also: UNEQUIP, UNEQ, INV, WIZARD",
]),

# Update UNEQUIP (line 103)
"UNEQUIP": _box("HELP: UNEQUIP", [
    "  Remove an equipped item from a slot.",
    "  Usage: UNEQUIP <member> <slot>  (or UNEQ <member> <slot>)",
    "  Examples:",
    "    UNEQUIP Hero weapon",
    "    UNEQ Mira body",
    "  Details:",
    "    Slots: weapon, body, head, hands, feet, back",
    "  See also: EQUIP, EQ, INV",
]),
"UNEQ": _box("HELP: UNEQUIP (UNEQ)", [
    "  Remove an equipped item from a slot.",
    "  Usage: UNEQUIP <member> <slot>  (or UNEQ <member> <slot>)",
    "  Examples:",
    "    UNEQUIP Hero weapon",
    "    UNEQ Mira body",
    "  See also: EQUIP, EQ, INV",
]),

# Update ATTACK (line 160)
"ATTACK": _box("HELP: ATTACK", [
    "  Engage in combat with hostile creatures in the room.",
    "  Usage: ATTACK [group]  (or K [group])",
    "  Examples:",
    "    ATTACK           — target the first hostile group",
    "    K                — same as ATTACK",
    "    ATTACK A         — target group A (Gauntlet arena)",
    "  Details:",
    "    Combat is automatic — your party fights by strategy.",
    "    Cannot attack in pitch black conditions.",
    "  Type HELP COMBAT for more on the combat system.",
    "  See also: COMBAT, STRATEGY, LIGHT, K",
]),
"K": _box("HELP: ATTACK (K)", [
    "  Engage in combat with hostile creatures in the room.",
    "  Usage: ATTACK [group]  (or K [group])",
    "  Examples:",
    "    ATTACK           — target the first hostile group",
    "    K                — same as ATTACK",
    "    ATTACK A         — target group A (Gauntlet arena)",
    "  See also: COMBAT, STRATEGY, LIGHT, ATTACK",
]),

# Update SKILLS (line 151)
"SKILLS": _box("HELP: SKILLS", [
    "  Show known skills and their effects.",
    "  Usage: SKILLS [COMBAT | UTILITY]  (or SK [COMBAT | UTILITY])",
    "  Examples:",
    "    SKILLS           — show all skills",
    "    SK               — same as SKILLS",
    "    SKILLS COMBAT    — show only combat skills",
    "  See also: STATS, LEARN, LRN",
]),
"SK": _box("HELP: SKILLS (SK)", [
    "  Show known skills and their effects.",
    "  Usage: SKILLS [COMBAT | UTILITY]  (or SK [COMBAT | UTILITY])",
    "  Examples:",
    "    SKILLS           — show all skills",
    "    SK               — same as SKILLS",
    "  See also: STATS, LEARN, LRN",
]),

# Add STATUS and SS (line 180)
"STATUS": _box("HELP: STATUS", [
    "  Show party survival stats: hunger, thirst, and stamina.",
    "  Usage: STATUS  (or SS)",
    "  Details:",
    "    Survival bars drain over time and affect performance.",
    "    Use EAT, EA and DRINK, DR to restore hunger and thirst.",
    "    Use REST or SIT to recover stamina.",
    "  See also: HUNGER, THIRST, STAMINA, SURVIVAL, SS",
]),
"SS": _box("HELP: STATUS (SS)", [
    "  Show party survival stats: hunger, thirst, and stamina.",
    "  Usage: STATUS  (or SS)",
    "  See also: HUNGER, THIRST, STAMINA, SURVIVAL, STATUS",
]),

# Update SIT/STAND to mention SS (line 189)
"SIT": _box("HELP: SIT / STAND", [
    "  Begin or end passive stamina recovery.",
    "  Usage: SIT   — sit down to slowly recover stamina",
    "         STAND — stand up and stop recovering",
    "  Details:",
    "    Sitting recovers stamina outside of combat.",
    "    You cannot move while sitting.",
    "    Full REST at campfire recovers much faster.",
    "  See also: STAMINA, REST, SS (status)",
]),

# Update LIGHT to mention aliases (line 227)
"LIGHT": _box("HELP: LIGHT", [
    "  Show current lighting conditions and active light sources.",
    "  Usage: LIGHT  (or LIGHTING)",
    "  Details:",
    "    Light levels affect combat accuracy and dodge chance.",
    "    Pitch black rooms forbid player-initiated combat.",
    "    Use LIT <item> to light a torch or lantern.",
    "    Use EXTINGUISH, DOUSE <item> to put one out.",
    "  See also: LIT, EXTINGUISH, DOUSE, ENVDETAILS, ENV, COMBAT",
]),

# Update ENVDETAILS (line 247)
"ENVDETAILS": _box("HELP: ENVDETAILS", [
    "  Display full numeric environmental information.",
    "  Usage: ENVDETAILS  (or ENV)",
    "  Details:",
    "    Shows exact temperature, light percentages, moon phase, fuel remaining.",
    "  See also: TIME, TI, WEATHER, WEA, LIGHT",
]),

# Update LIT/EXTINGUISH (line 261)
"LIT": _box("HELP: LIT / EXTINGUISH", [
    "  Light a torch or lantern from your inventory.",
    "  Usage: LIT <item>",
    "  Examples:",
    "    LIT TORCH",
    "    LIT LANTERN",
    "  Details:",
    "    Torches burn for 60 game-minutes then go out automatically.",
    "    Lanterns require an Oil Flask to fill; they burn for 90 game-minutes.",
    "    ENVDETAILS, ENV shows fuel remaining.",
    "  See also: EXTINGUISH, DOUSE, LIGHT, ENVDETAILS, ENV",
]),

# Update PARTY (line 365)
"PARTY": _box("HELP: PARTY", [
    "  Show all party member status: HP, MP, survival stats.",
    "  Usage: PARTY  (or P)",
    "  Details:",
    "    PARTY works in NAVIGATION and CAMPFIRE states.",
    "    Shows survival aggregate row (hunger, thirst, stamina).",
    "  See also: STATUS, SS, STATS",
]),
"P": _box("HELP: PARTY (P)", [
    "  Show all party member status: HP, MP, survival stats.",
    "  Usage: PARTY  (or P)",
    "  See also: STATUS, SS, STATS, PARTY",
]),

# Update REST (line 356)
"REST": _box("HELP: REST", [
    "  Rest the party at campfire to recover HP, MP, and stamina.",
    "  Usage: REST  (used in CAMPFIRE mode)",
    "  Details:",
    "    REST recovers full HP, MP, and stamina over time.",
    "    Bless Camp (cleric skill) boosts HP recovery rate.",
    "    Enter campfire mode with CAMP from NAVIGATION.",
    "  See also: CAMP, STAMINA, SIT, SS (status)",
]),

# Update SAY (line 608)
"SAY": _box("HELP: SAY", [
    "  Speak to all players in the same room.",
    "  Usage: SAY <message>  (or ' <message>)",
    "  Examples:",
    "    SAY Hello, traveler!",
    "    ' Hello, traveler!",
    "  Receivers see: [YourName says]: \"message\"",
    "  See also: EMOTE, ME, SHOUT, OOC, PLAYERS",
]),
"'": _box("HELP: SAY (')", [
    "  Speak to all players in the same room.",
    "  Usage: SAY <message>  (or ' <message>)",
    "  Examples:",
    "    SAY Hello, traveler!",
    "    ' Hello, traveler!",
    "  See also: EMOTE, ME, SHOUT, OOC, PLAYERS, SAY",
]),

# Update SHOUT (line 634)
"SHOUT": _box("HELP: SHOUT / OOC", [
    "  Broadcast a message to all connected players regardless of room.",
    "  Usage: SHOUT <message>  (or OOC <message>)",
    "  Examples:",
    "    SHOUT Is anyone at the inn?",
    "    OOC Is anyone at the inn?",
    "  See also: SAY, ', EMOTE, ME, PLAYERS",
]),
"OOC": _box("HELP: SHOUT / OOC", [
    "  Broadcast a message to all connected players regardless of room.",
    "  Usage: SHOUT <message>  (or OOC <message>)",
    "  See also: SAY, ', EMOTE, ME, PLAYERS, SHOUT",
]),

# Update EMOTE (line 616)
"EMOTE": _box("HELP: EMOTE / ME", [
    "  Perform an emote visible to all players in the room.",
    "  Usage: EMOTE <action>  (or ME <action>)",
    "  Examples:",
    "    EMOTE waves cheerfully.",
    "    ME bows deeply.",
    "  Everyone in the room (including you) sees: * YourName action",
    "  See also: SAY, ', SHOUT, OOC",
]),

# Update PLAYERS (line 648)
"PLAYERS": _box("HELP: PLAYERS", [
    "  Shows who else is currently in your room.",
    "  Usage: LOOK, L  (other players appear under \"Also here:\")",
    "  Details:",
    "    Players in the same room can see each other's SAY and EMOTE messages.",
    "    Use SHOUT, OOC to reach players in other rooms.",
    "  See also: SAY, ', EMOTE, ME, SHOUT, OOC, LOOK, L",
]),
```

**Also update the _help_for_state() function at the bottom to show aliases:**

```python
def _help_for_state(state) -> str:
    if state.value in ("connect", "creation"):
        return _box("HELP", [
            "  You are creating a character. Available choices:",
            "",
            "    HELP RACES    — learn about available races",
            "    HELP CLASSES  — learn about available classes",
            "",
            "  Type your responses as prompted.",
        ])
    elif state.value == "navigation":
        return _box("HELP", [
            "  You are exploring Ashveil. Available commands:",
            "",
            "    Movement     NORTH / N, SOUTH / S, EAST / E, WEST / W",
            "    Look         LOOK / L",
            "    Examine      EXAMINE / X",
            "    Inventory    INV / INVENTORY, EQUIP / EQ, UNEQUIP / UNEQ",
            "    Character    STATS, SKILLS / SK, STATUS / SS, BUFFS / B",
            "    Upgrade      UPGRADE / UPG, LEARN / LRN",
            "    Party        PARTY / P, TALK / T, DISMISS / DIS",
            "    Combat       ATTACK / K",
            "    Environment  TIME / TI, WEATHER / WEA, LIGHT",
            "    Lighting     LIT <item>, EXTINGUISH / DOUSE",
            "    Camping      CAMP (enter campfire mode)",
            "    Survival     EAT / EA, DRINK / DR, SIT, SS",
            "    Communication SAY / ', EMOTE / ME, SHOUT / OOC",
            "    System       SAVE / SV, GIVE / GIV, HORSES / HOR",
            "",
            "  Type HELP <command> for details on any command.",
        ])
    # ... rest unchanged
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/server/test_help_registry_aliases.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/engine/help_registry.py tests/server/test_help_registry_aliases.py
git commit -m "docs: update all help topics with command shorthands

Updated help registry to show shorthand aliases in usage lines:
- All primary commands show '(or ALIAS)' format
- State help summaries updated with common aliases
- New help entries created for single-letter aliases
- Cross-references added between primary and alias entries"
```

---

## Phase 3: Update Getting Started Guide

### Task 3: Update GETTING_STARTED.md Command Reference

- [ ] **Step 1: Update Exploration section**

Find the "Exploration" section (around line 196) and update:

```markdown
### Exploration
```
LOOK / L                   — describe current room
X <item>                   — examine an item or NPC
TIME / TI                  — show game time and day
WEATHER / WEA              — show current weather
LIGHT / LIGHTING           — show light level in room
HELP [topic]               — in-game help system
```
```

- [ ] **Step 2: Update Inventory & Equipment section**

Find the "Inventory & Equipment" section (around line 206) and update:

```markdown
### Inventory & Equipment
```
INV                        — list all party inventory
EQUIP / EQ <member> <item> — equip item on a party member
UNEQUIP / UNEQ <member> <slot> — remove equipped item
DROP <item>                — drop item on the ground
TAKE <item>                — pick up item from ground
GIVE / GIV <item> <member> — transfer item between members
```
```

- [ ] **Step 3: Update Skills section**

Find the "Skills" section (around line 216) and update:

```markdown
### Skills
```
SKILLS / SK                — list unlocked skills
SKILLS UTILITY             — utility skills only
LEARN / LRN <skill>        — unlock a skill (costs skill points)
UPGRADE / UPG <modifier>   — upgrade a stat modifier
USE <skill>                — activate a utility skill
BUFFS / B                  — show active buffs and effects
```
```

- [ ] **Step 4: Update System section**

Find the "System" section (around line 223) and update:

```markdown
### System
```
SAVE / SV                  — save your progress
QUIT / LOGOUT              — exit the game
PARTY / P                  — show party status
STATUS / SS                — show survival stats (hunger/thirst/stamina)
```
```

- [ ] **Step 5: Add new Party & Combat section**

Add after the System section:

```markdown
### Party & Combat
```
TALK / T <npc>             — speak with a recruitable NPC
DISMISS / DIS <name>       — remove a companion from party
ATTACK / K                 — engage in combat
HORSES / HOR               — show horse status
```
```

- [ ] **Step 6: Update Survival section in the main text**

Find the "Managing Survival" section (around line 157) and update the examples:

```markdown
| Stat | Restored By |
|------|------------|
| **Hunger** | `EAT <food>` or `EA <food>` (e.g., `EA ration_pack`) |
| **Thirst** | `DRINK <item>` or `DR <item>` (e.g., `DR water_flask`) |
| **Stamina** | `SIT` to rest; `REST` at campfire for full recovery |

Check them anytime with:

```
STATUS
```
or use the shorthand:

```
SS
```
```

- [ ] **Step 7: Update the Quick Start section**

Find the quick mention of commands (around line 115) and update:

```markdown
### Basic Loop

```
LOOK / L       — see your surroundings
N / S / E / W    — move between rooms
SS               — check hunger, thirst, stamina
STATS            — check HP, MP, level, equipment
INV              — show inventory
```
```

- [ ] **Step 8: Run tests to verify no regressions**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add GETTING_STARTED.md
git commit -m "docs: update GETTING_STARTED.md with command shorthands

Updated command reference sections to show all new aliases:
- Exploration: L, X, TI, WEA
- Inventory: EQ, UNEQ, GIV
- Character: SK, LRN, UPG, B
- System: SV, P, SS
- Party/Combat: T, DIS, K, HOR
- Survival shortcuts: EA, DR
- Chat shortcut: '
- Updated all examples to show shorthand usage"
```

---

## Summary

**21 new command aliases added:**
1. `l` → look
2. `x` → examine
3. `eq` → equip
4. `uneq` → unequip
5. `k` → attack
6. `p` → party
7. `sk` → skills
8. `ss` → status
9. `b` → buffs
10. `t` → talk
11. `dis` → dismiss
12. `sv` → save
13. `'` → say
14. `ti` → time
15. `wea` → weather
16. `upg` → upgrade
17. `lrn` → learn
18. `dr` → drink
19. `ea` → eat
20. `giv` → give
21. `hor` → horses

**Documentation updated:**
- Help registry: All primary commands now show "(or ALIAS)" format
- State help summaries: Show common aliases in command lists
- GETTING_STARTED.md: All command reference tables updated

**Testing:**
- New test file for alias existence
- New test file for help text alias mentions
- Full test suite should pass
