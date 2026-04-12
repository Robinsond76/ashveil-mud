# Phase 1: World Clock & Environment
**Status: IMPLEMENTED**

## Overview
A shared, server-side world clock that drives day/night progression, weather, temperature, and lighting. All players on the same server share the same world time.

---

## Time System

### Speed
- 1 real second = `WORLD_TICK_SECONDS` (6.0) game-minutes advance
- 1 real minute = 10 game-minutes
- 1 full game day = 144 real minutes (2.4 real hours)
- Config: `GAME_START_HOUR = 8` (world starts at 8:00 AM on Day 1)

### Time Periods
| Period | Hours | Outdoor Light |
|--------|-------|---------------|
| Deep Night | 0:00–4:59 | Moon-dependent |
| Dawn | 5:00–6:59 | 60% → 100% gradient |
| Day | 7:00–17:59 | 100% |
| Dusk | 18:00–19:59 | 100% → 60% gradient |
| Evening/Night | 20:00–23:59 | Moon-dependent |

### Moon Phase (28-day cycle)
| Phase | Night Light |
|-------|-------------|
| New moon | 5% |
| Waxing/Waning crescent | 15% |
| First/Last quarter | 35% |
| Waxing/Waning gibbous | 55% |
| Full moon | 70% |

---

## Weather System

### States
`sunny`, `cloudy`, `rainy`, `windy`, `stormy`

### Behaviour
- Only affects outdoor and indoor rooms (underground is immune)
- Duration: `WEATHER_MIN_DURATION` (90) to `WEATHER_MAX_DURATION` (240) game-minutes
- Warning broadcast `WEATHER_WARN_MINUTES` (60) game-minutes before change
- All connected players in non-underground rooms receive broadcast prose

### Weather Effects
| Weather | Temp Modifier (°F) | Light Modifier (outdoor) |
|---------|-------------------|--------------------------|
| Sunny | +5 | 0% |
| Cloudy | -2 | 0% |
| Rainy | -5 | -10% |
| Windy | -8 | 0% |
| Stormy | -12 | -20% |

---

## Temperature System

### Display
- Player-facing: descriptive labels only
- `ENVDETAILS` command shows exact °F value

### Labels
| Range (°F) | Label |
|------------|-------|
| > 95 | Scorching |
| 80–95 | Hot |
| 60–80 | Comfortable |
| 45–60 | Cool |
| 30–45 | Cold |
| 10–30 | Bitter Cold |
| < 10 | Freezing |

### Room Types
- `outdoor`: full day/night + weather temperature modifier
- `indoor` (constructed buildings only): sheltered, weather modifier still applies
- `underground`: thermally stable, weather-immune, uses `base_temp_f` unchanged

### Room base_temp_f values assigned
| Zone | Temp |
|------|------|
| Town (outdoor) | 65°F |
| Blacksmith forge | 82°F |
| Inn / indoor town | 65–68°F |
| Forest | 60–62°F |
| Dungeon (underground) | 52°F |

---

## Lighting System

### Room Ambient Light
- `outdoor`: sky-based (time + moon + weather)
- `indoor`: constant 85%
- `underground`: 0% (pure darkness)

### Carried Light Sources
| Item | Light Level | Fuel |
|------|-------------|------|
| Torch | 50% | 60 game-minutes |
| Hooded Lantern | 70% | 90 game-minutes per Oil Flask |

### Effective Light = `max(ambient, best_carried_source)`

### Combat Penalties by Light Level
| Light | Hit Penalty | Dodge Penalty |
|-------|-------------|---------------|
| 80–100% | none | none |
| 60–80% | -5% | -10% |
| 40–60% | -15% | -20% |
| 20–40% | -30% | -40% |
| 5–20% | -50% | -75% |
| 0–5% (pitch black) | Combat FORBIDDEN | — |

### Pitch Black Rules
- Players CANNOT initiate combat
- Exception: enemy group contains a creature with `darkvision: true` — they can initiate combat against the player party at full penalty
- Darkvision creatures ignore all lighting penalties (both hit and dodge)
- Currently assigned: `skeleton` has `darkvision: true`

---

## New Commands

| Command | Description |
|---------|-------------|
| `TIME` | Shows current time, day, moon phase |
| `WEATHER` | Shows weather and temperature label |
| `LIGHT` | Shows effective lighting and active sources |
| `ENVDETAILS` / `ENV` | Full numeric details (°F, %, moon %, etc.) |
| `LIT <item>` | Light a torch or lantern |
| `EXTINGUISH <item>` / `DOUSE <item>` | Put out a light source |

### Enhanced Existing Commands
- `LOOK`: appends one-line environment footer (e.g., `[Evening — Stormy — Cold — Very dark]`)
- `HELP <topic>`: now accepts topics — `HELP COMBAT`, `HELP LIGHT`, `HELP LIT`, `HELP WEATHER`, `HELP TIME`, `HELP ENVDETAILS`

---

## Files Changed

| File | Change |
|------|--------|
| `server/config.py` | Added world clock and weather constants |
| `server/engine/world_clock.py` | **NEW** — WorldClock class |
| `server/engine/world.py` | Room gets `room_type`, `base_temp_f`; `render()` gets `env_footer` param |
| `server/engine/character.py` | `roll_hit()` accepts `hit_penalty` param |
| `server/engine/npc.py` | NPC gets `darkvision: bool` field |
| `server/engine/combat.py` | `CombatSession` accepts `lighting`; penalties applied in `_resolve_attack` |
| `server/engine/game.py` | Clock wired in; new commands; pitch-black combat block |
| `server/main.py` | WorldClock instantiated, started on startup, passed to sessions |
| `server/data/rooms/*.json` | `room_type` and `base_temp_f` added to all rooms |
| `server/data/npcs/monsters.json` | Skeletons flagged `darkvision: true` |
| `server/data/items/misc.json` | **NEW** — Torch, Hooded Lantern, Oil Flask |
| `server/data/rooms/town.json` | Alchemist shop stocks torches, lanterns, oil flasks |
| `server/data/rooms/dungeon.json` | Storeroom has a torch |

---

## Future Hooks (Phase 2+)
- Temperature will apply survival penalties (clothing warmth stat) — stub is in `base_temp_f` per room
- Torch burnout message system is live; full item-condition tracking comes in Phase 5
- Weather type `fog`, `blizzard`, `heatwave` reserved but inactive
