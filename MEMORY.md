# Ashveil MUD — Project Memory

## What Is This?
A Python-based text MUD (Multi-User Dungeon) with a web terminal client. Players connect via WebSocket, explore rooms, fight monsters in tick-based combat, manage a party, and progress through skills and gear.

## Stack
| Layer | Technology |
|-------|-----------|
| Server | Python 3.x, asyncio, FastAPI |
| Transport | WebSocket (`/ws`) |
| Database | SQLAlchemy + SQLite (per-player JSON blob) |
| Client | HTML + vanilla JS terminal (`client/`) |

## Architecture
- `GameSession` — one per WebSocket connection. Owns all player state for the session.
- `WorldMap` — shared singleton. Holds all `Room` objects and their item/NPC lists.
- `WorldClock` — shared singleton. Background asyncio tick loop for time, weather, temperature.
- `CombatSession` — spawned per encounter. Async task per combatant; tick-based.
- State machine: `CONNECT → CREATION → NAVIGATION → CAMPFIRE → STRATEGY → COMBAT`
- Data loaded at startup from JSON files in `server/data/`

## Directory Layout
```
server/
  config.py            — constants (tick rates, weather, game time)
  main.py              — FastAPI app, WebSocket entrypoint, startup hooks
  engine/
    character.py       — Character dataclass, stat rolls
    combat.py          — CombatSession, tick loop, attack resolution
    game.py            — GameSession, all command handling
    items.py           — Item/Inventory logic
    npc.py             — NPC dataclass, factory
    persistence.py     — save_player / load_player (SQLAlchemy)
    skills.py          — Skill registry and resolution
    strategy.py        — Combat strategy enum and AI
    world.py           — Room, WorldMap, room loader
    world_clock.py     — WorldClock (NEW — Phase 1)
  data/
    classes/classes.json
    items/armor.json, weapons.json, consumables.json, misc.json
    npcs/monsters.json, recruitables.json
    rooms/town.json, forest.json, dungeon.json, testing_grounds.json
    skills/warrior_skills.json, mage_skills.json, thief_skills.json, cleric_skills.json
client/
  index.html           — browser terminal UI
  terminal.js          — WebSocket client logic
docs/
  superpowers/
    specs/             — feature spec files (see below)
```

---

## Phases Overview

| # | Phase | Status | Spec File |
|---|-------|--------|-----------|
| 1 | World Clock & Environment | ✅ COMPLETED | [phase-01-world-clock-environment.md](docs/superpowers/specs/phase-01-world-clock-environment.md) |
| 2 | Survival Stats | ✅ COMPLETED | [phase-02-survival-stats.md](docs/superpowers/specs/phase-02-survival-stats.md) |
| 3 | Utility Skills & Mana Rework | ✅ COMPLETED | [phase-03-utility-skills-mana.md](docs/superpowers/specs/phase-03-utility-skills-mana.md) |
| 4 | Food & Consumables | 🔲 NOT STARTED | [phase-04-food-consumables.md](docs/superpowers/specs/phase-04-food-consumables.md) |
| 5 | Inventory & Weight Overhaul | 🔲 NOT STARTED | [phase-05-inventory-weight.md](docs/superpowers/specs/phase-05-inventory-weight.md) |
| 6 | Horses & Mounts | 🔲 NOT STARTED | [phase-06-horses-mounts.md](docs/superpowers/specs/phase-06-horses-mounts.md) |
| 7 | Wizard & Spell Overhaul | 🔲 NOT STARTED | [phase-07-wizard-spell-overhaul.md](docs/superpowers/specs/phase-07-wizard-spell-overhaul.md) |
| 8 | Help System Overhaul | 🔲 NOT STARTED | [phase-08-help-system.md](docs/superpowers/specs/phase-08-help-system.md) |
| 9 | Multiplayer Foundations | 🔲 NOT STARTED | [phase-09-multiplayer-foundations.md](docs/superpowers/specs/phase-09-multiplayer-foundations.md) |

---

## Phase 3 — What Was Built

### Modified Files
- `server/engine/skills.py` — `Skill` dataclass gets 4 new optional fields: `use_context` (default `"combat"`), `stamina_cost` (default `0`), `required_items` (default `[]`), `consumes_item` (default `False`). Added `get_utility_skills()`, `get_combat_skills()` filter helpers. Added `render_skills_section()`, `_render_combat_section()`, `_render_utility_section()` for filtered SKILLS display.
- `server/engine/game.py` — `USE <skill_id>` command in NAVIGATION state (`_handle_use_skill` + `_execute_utility_effect`). SKILLS command now accepts `UTILITY`/`COMBAT` filter arg (bare SKILLS shows both sections with headers). USE blocked with clear message in COMBAT/CAMPFIRE states. Added `_fortify_active`, `_bless_camp_active`, `_arcane_light_until` session flags.
- `server/data/skills/thief_skills.json` — Added `lockpick` (5 stamina, requires lockpick item) and `detect_traps` (10 MP) utility skills.
- `server/data/skills/mage_skills.json` — Added `arcane_light` (15 MP, provide_light 120 game-min) and `identify` (20 MP) utility skills.
- `server/data/skills/cleric_skills.json` — Added `bless_camp` (25 MP, sets bless flag) and `purify_food` (10 MP, requires food item) utility skills.
- `server/data/skills/warrior_skills.json` — Added `fortify` (10 stamina, sets fortify flag, -10% party damage) utility skill.
- `server/data/items/misc.json` — Added `lockpick` (stackable, weight 0, value 5) and `thieves_tools` (reusable, weight 1, value 25).

### Mana Rework
- REST at campfire already restored full MP (no change needed).
- Confirmed no passive MP regen in out-of-combat tick — tests verify this.
- Mana potions continue to work as instant MP restores in combat.

### Key Design Decisions (Phase 3)
- **Utility skills are NOT in the class skill_tree** (classes.json). They exist only in the skill JSON files and players unlock them separately via `unlocked_skills` dict.
- **USE command validates**: state == NAVIGATION, skill exists, skill is unlocked, use_context == "utility", MP/stamina sufficient, required items present in party inventory (any member's inv counts).
- **Effect flags** (`_fortify_active`, `_bless_camp_active`, `_arcane_light_until`) are set as dynamic session attributes — no dataclass field needed.
- **SKILLS bare** shows both COMBAT (tree-based) and UTILITY (registry-based) sections with clear headers.

---

## Phase 1 — What Was Built

### New Files
- `server/engine/world_clock.py` — `WorldClock` class with background asyncio loop, weather state machine, moon cycle, ambient lighting calc, temperature calc, combat penalty lookup, weather broadcast subscriber pattern

### Modified Files
- `server/config.py` — Added `GAME_MINS_PER_REAL_MIN`, `WORLD_TICK_SECONDS`, `GAME_START_HOUR`, weather duration constants
- `server/engine/world.py` — `Room` gets `room_type` ("outdoor"/"indoor"/"underground") and `base_temp_f`; `render()` accepts `env_footer`
- `server/engine/character.py` — `roll_hit()` gets `hit_penalty=0.0` parameter
- `server/engine/npc.py` — `NPC` gets `darkvision: bool = False`
- `server/engine/combat.py` — `CombatSession` accepts `lighting=1.0`; applies hit/dodge penalties from `lighting_combat_penalties()`; darkvision NPCs bypass darkness penalties
- `server/engine/game.py` — Clock wired in, `_carried_light()`, `_effective_light()`, new commands: `TIME`, `WEATHER`, `LIGHT`/`LIGHTING`, `ENVDETAILS`/`ENV`, `LIT`, `EXTINGUISH`/`DOUSE`; pitch-black combat block; contextual HELP for env commands
- `server/main.py` — `WorldClock` instantiated and started on startup; passed to `GameSession`
- All 4 room JSON files — added `room_type` and `base_temp_f` to every room
- `server/data/npcs/monsters.json` — skeleton gets `"darkvision": true`
- `server/data/items/misc.json` — new items: torch (60 min fuel, light 0.5), lantern (oil-based, light 0.7), oil flask (refuels lantern +90 min)

### Key Design Decisions
- **1 real minute = 10 game minutes** (configurable via `GAME_MINS_PER_REAL_MIN`)
- **Lighting tiers:** Pitch black (0–5%), Very dim (5–20%), Dim (20–40%), Moderate (40–65%), Bright (65–90%), Daylight (90–100%)
- **Players see labels** (e.g. "Dim"), use `ENVDETAILS` for raw numbers
- **Pitch black = combat forbidden** unless at least one enemy has darkvision
- **Torch burnout** is structurally supported (fuel_minutes field) but active countdown not yet wired into the tick loop
- **Indoor = constructed buildings only** (caves are underground; context-free caves default to outdoor unless marked)
- **Weather** has 5 states with transition advance-warning broadcasts: Clear, Overcast, Rain, Storm, Fog

---

## Key Architecture Decisions (All Phases)

| Decision | Rationale |
|----------|-----------|
| JSON data files | Easy to edit content without touching code |
| Single asyncio event loop | Avoids threading complexity; WebSocket + combat + clock all cooperative |
| `WorldClock` subscribers | Decouples weather broadcast from session polling |
| Per-session `CombatSession` | Keeps combat isolated; multiplayer combat joins are future work |
| Darkvision on NPC not race | Simpler; monsters drive the rule, not player metadata |
| `room_type` over `is_outdoor` flag | Three-way distinction needed (outdoor/indoor/underground) |

---

## Next Steps (Recommended Order)

1. **Phase 3 — Utility Skills & Mana Rework**: Mana only recovers via rest (not ticks). `USE <skill>` command for out-of-combat utility skills (lockpick, arcane light, detect traps). Skill JSON gets `use_context` field.

2. **Phase 4 — Food & Consumables**: Food items with buff effects (alertness, fortified, quenched, etc.). `Character.active_buffs` dict. Buff duration ticks down on world clock.

3. **Phase 5 — Inventory & Weight**: Party-wide inventory display. Backpack slot rules. Weight system with thresholds. Cart (outdoor-only vehicle for extra capacity).

---

## Phase 2 — What Was Built

### New Files
- `tests/` — pytest test suite (55 tests, all passing)
- `tests/conftest.py` — session-scoped fixture: loads items + NPCs from JSON
- `tests/test_phase02_character.py` — Phase A: survival fields on Character
- `tests/test_phase02_party_aggregate.py` — Phase B: `_party_survival_aggregate` + `_apply_survival_penalties`
- `tests/test_phase02_drain.py` — Phase C: `_drain_survival_tick` + movement stamina drain/blocking
- `tests/test_phase02_combat_penalties.py` — Phase D: combat `survival_multiplier` + FLEE stamina drain
- `tests/test_phase02_recovery.py` — Phase E: REST restores stamina; SIT/STAND + `_sitting_stamina_tick`
- `tests/test_phase02_commands.py` — Phase F: STATUS, EAT, DRINK, LOOK warning

### Modified Files
- `server/engine/character.py` — Added `hunger`, `thirst`, `stamina` (and max_ variants) fields; `hunger_drain_rate()` and `thirst_drain_rate(temp_label)` helpers; serialization round-trip; module-level `_THIRST_MULTIPLIERS` dict
- `server/engine/game.py` — `_sitting` flag; `_party_survival_aggregate()`; `_apply_survival_penalties()`; `_drain_survival_tick(temp_label)`; `_sitting_stamina_tick()`; updated `_subscribe_clock` to drain+recover per tick; `_do_move` drains 2 stamina + blocks at 0; REST in `_handle_campfire` restores stamina; SIT/STAND/STATUS/EAT/DRINK commands; `_do_survival_status`, `_do_eat`, `_do_drink` handlers; LOOK appends exhaustion warning at stamina=0; PARTY output includes survival aggregate row; passes `survival_multiplier` to `CombatSession`
- `server/engine/combat.py` — `CombatSession` accepts `survival_multiplier=1.0`; `_resolve_attack` applies multiplier to player-side damage; FLEE now drains 5 stamina from the fleeing combatant
- `server/data/items/consumables.json` — Added food/drink items: `hard_bread`, `dried_meat`, `rations`, `water_flask`, `waterskin`

### Key Design Decisions
- `_THIRST_MULTIPLIERS` moved to module level (not dataclass field) to avoid dataclass mutable-default error
- Survival multiplier is static at combat-start (computed once when `CombatSession` is created)
- `_sitting_stamina_tick()` only fires when `_sitting=True` AND not in combat (checked in clock callback)
- EAT/DRINK look items up by partial name match against inventory (tolerant UX)


5. **Phase 6 — Horses**: Mount system, stamina reduction formula, auto-detach on indoor/underground entry.

6. **Phase 7 — Wizard Overhaul**: Channeled spell system, armor restrictions, AoE grid targeting, zero-MP dodge-only state.

7. **Phase 8 — Help System**: Full contextual `HELP` per `State`, topic registry, formatting standard.

8. **Phase 9 — Multiplayer**: Session registry, room occupancy, presence broadcasts, `SAY`/`EMOTE`, shared item state.

---

## Smoke Test Commands (Phase 1)
```bash
cd server
python -c "from engine.world_clock import WorldClock; c = WorldClock(); print(c.env_footer('outdoor', 65.0, 0.0))"
python -c "from engine.world import WorldMap; wm = WorldMap(); wm.load(); r = wm.get_room('town_square'); print(r.room_type, r.base_temp_f)"
python -c "from engine.npc import NPC; from engine.world import WorldMap; wm = WorldMap(); wm.load(); n = wm.get_room('dungeon_entrance') and print('ok')"
python -c "from engine.npc import NPC; import json; d=json.load(open('data/npcs/monsters.json')); print([m for m in d if m['id']=='skeleton'])"
```
All tests passed after Phase 1 implementation.
