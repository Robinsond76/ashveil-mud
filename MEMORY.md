# Ashveil MUD — Project Memory

## Phases Overview

| # | Phase | Status |
|---|-------|--------|
| 1 | World Clock & Environment | ✅ COMPLETED |
| 2 | Survival Stats | ✅ COMPLETED |
| 3 | Utility Skills & Mana Rework | ✅ COMPLETED |
| 4 | Food & Consumables | ✅ COMPLETED |
| 5 | Inventory & Weight Overhaul | ✅ COMPLETED |
| 6 | Horses & Mounts | ✅ COMPLETED |
| 7 | Wizard & Spell Overhaul | ✅ COMPLETED |
| 8 | Help System Overhaul | ✅ COMPLETED |
| 9 | Multiplayer Foundations | ✅ COMPLETED |

---

## Key Architecture Decisions (All Phases)

| Decision | Rationale |
|----------|-----------|
| JSON data files | Easy to edit content without touching code |
| Single asyncio event loop | Avoids threading complexity; WebSocket + combat + clock all cooperative |
| `WorldClock` subscribers | Decouples weather broadcast from session polling |
| Per-session `CombatSession` | Keeps combat isolated; multiplayer combat joins are future work |
| `room_type` over `is_outdoor` flag | Three-way distinction needed (outdoor/indoor/underground) |
| Effect flags on session | Dynamic attrs (`_fortify_active`, etc.) — no dataclass field needed |
| Utility skills NOT in class skill_tree | Exist only in skill JSON files; unlocked via `unlocked_skills` dict |
| `_sessions` dict in main.py | Keyed by player name; asyncio-safe (cooperative, no locks needed) |
| `room_occupants` on WorldMap | Room ID → list of player names; updated on enter/leave/connect/disconnect |

---

## Game Content Quick Reference

### Playable Classes
| Class | Base HP | Base MP | Primary Stat | Starting Weapon |
|-------|---------|---------|--------------|-----------------|
| Warrior | 60 | 10 | STR 16 | Rusty Sword |
| Mage | 25 | 60 | INT 18 | Oak Staff |
| Thief | 35 | 25 | DEX 18 | Iron Dagger |
| Cleric | 40 | 45 | WIS 18 | Wooden Mace |

All classes start with: 2× health_potion, campfire_kit.

### Character Creation Flow
1. **CONNECT** → enter name
2. **CREATION Step 1** → choose class (WARRIOR / MAGE / THIEF / CLERIC)
3. **CREATION Step 2** → point-buy stats (54 points; 3–18 range); commands: `SET STR 15`, `SUGGEST`, `STATS`, `DONE`
4. **CREATION Step 3** → strategy editor (set combat IF/THEN rules); `DONE` enters world
5. New players spawn in **Ashveil Town Square**

### State Machine
`CONNECT → CREATION → NAVIGATION → CAMPFIRE → STRATEGY → COMBAT`
- Commands are gated per state; most exploration commands work in NAVIGATION
- CAMPFIRE: full recovery, party/formation/skill management; `LEAVE` returns to NAVIGATION

### Key Command Groups (NAVIGATION)
- **Move**: `N/S/E/W/UP/DOWN`; costs 2 stamina per step
- **Info**: `LOOK`, `STATS`, `PARTY`, `STATUS`, `SKILLS`, `BUFFS`, `TIME`, `WEATHER`
- **Inventory**: `INV`, `EQUIP`, `UNEQUIP`, `DROP`, `TAKE`, `GIVE`, `STASH`, `UNLOAD CART`
- **Survival**: `EAT <food>`, `DRINK <item>`, `SIT` (stamina regen), `STAND`
- **Combat**: `ATTACK [group]`, `FLEE`
- **Mounts**: `RIDE`, `DISMOUNT`, `HORSES` (outdoor only; reduce stamina drain 60%)
- **Skills**: `LEARN <skill>`, `USE <skill>` (utility), `TALK <npc>` / `DISMISS <name>`
- **Chat**: `SAY`, `EMOTE/ME`, `SHOUT/OOC`
- **System**: `HELP [topic]`, `SAVE`, `QUIT`

### Starting Area (town.json)
| Room | Type | Key Exit(s) |
|------|------|-------------|
| Town Square | Outdoor | N→Blacksmith, E→Inn, S→South Gate, W→Apothecary |
| Blacksmith's Forge | Indoor | Sells iron_sword, hand_axe, leather_armor, iron_helm |
| The Rusty Flagon Inn | Indoor | ✅ Campfire; sells health_potion, mana_potion |
| Mirabel's Apothecary | Indoor | Sells potions, torch, lantern, oil_flask |
| South Gate | Outdoor | S→Thornwood Forest, E→Testing Grounds |

### Key Config Constants (config.py)
| Constant | Value |
|----------|-------|
| `COMBAT_TICK_INTERVAL` | 1.5 s |
| `STAT_POINT_BUY_BUDGET` | 54 pts |
| `GAME_MINS_PER_REAL_MIN` | 10 (1 day = 2.4 real hrs) |
| `WORLD_TICK_SECONDS` | 6.0 s |
| `DEBUG_NO_DEATH_PENALTY` | True |
| `MODIFIER_BONUS_PER_LEVEL` | +5% |

### Notable Mechanics to Remember
- **Survival stats**: Hunger + Thirst reduce combat damage when critically low; Stamina gates movement/flee
- **Combat**: Fully automatic via strategy rules; 1.5 s ticks; formation grid (2 rows × 3 cols)
- **Lighting**: Pitch black (<5% light) blocks player-initiated combat; some monsters have Darkvision
- **Horses**: Outdoor only; left behind when entering indoor rooms
- **Weight** (Phase 5): Encumbrance affects stamina drain
- **Mana** (Phase 3): Separate pool for spells/utility skills; regenerates at campfire
- **Party**: Up to 4 NPC companions; managed at campfire (formation, strategies, gear)

### Data File Map
| Content | File |
|---------|------|
| Classes | `server/data/classes/classes.json` |
| Weapons | `server/data/items/weapons.json` |
| Armor | `server/data/items/armor.json` |
| Consumables | `server/data/items/consumables.json` |
| Misc items | `server/data/items/misc.json` |
| Monsters | `server/data/npcs/monsters.json` |
| Recruitables | `server/data/npcs/recruitables.json` |
| Skills (per class) | `server/data/skills/<class>_skills.json` |
| Rooms | `server/data/rooms/{town,forest,dungeon,testing_grounds}.json` |
