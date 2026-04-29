# GoMud Engine Analysis — Findings for Ashveil-Mud

Analysis date: 2026-04-29

## GoMud vs Ashveil-Mud Feature Comparison

### Features GoMud Has That ashveil-mud Doesn't

| Feature | GoMud | ashveil-mud |
|---------|-------|-------------|
| **Quests** | Full quest engine with progress tracking | None |
| **Clans/Guilds** | Clan system with member management | None |
| **Mudmail** | In-game mail between players | None |
| **Auctions** | Player auction house | None |
| **Gambling** | Dice/card games | None |
| **Leaderboards** | Kill stats, rankings, top players | None |
| **Alt characters** | Multiple characters per account | Single character |
| **Telnet support** | Ports 33333, 44444, 9999 | WebSocket only |
| **SSH support** | Port 33332 | None |
| **Web admin panel** | /admin/ with config, HTTPS, player mgmt | None |
| **GMCP/MCP** | Telnet sub-protocol for client integration | None |
| **Corpse system** | Lootable corpses on death | Death is a stat reset |
| **Permadeath** | Configurable lives/perma death | None |
| **Copyover** | Hot restart without dropping connections | None |
| **Discord integration** | Webhook for player events | None |
| **Localization** | Translation file system (localize/) | Hardcoded English |
| **Audio** | MUD Sound Protocol | None |
| **Mob conversations** | Dialogue trees via scripting | Static dialogue JSON |
| **Mob boredom/despawn** | Auto-cleanup idle mobs | Persistent respawn timers |
| **Room unloading** | Memory management for inactive rooms | All rooms always loaded |

### Shared Features (both have)

- 4 player classes (Warrior, Mage, Thief, Cleric/healer variant)
- Skill trees with prerequisites
- Grid-based tactical combat
- Party system with NPC companions
- Day/night cycle
- Light/visibility mechanics
- Inventory & equipment with slots
- Weather system
- Survival/hunger mechanics
- Browser-based WebSocket client
- JSON/YAML data files for world content

---

## Key Architectural Differences

### 1. Plugin/Module System

**GoMud:** Self-contained feature packages in `modules/` that auto-register via Go `init()`. Each module bundles its own data files, commands, web pages, scripts, and event subscriptions. Adding a feature means dropping a new folder — no core engine changes.

**ashveil-mud:** Features are hardcoded into state handlers (`states/navigation.py`, `states/campfire.py`). Chat, mounts, campfires, and survival are all inlined in the same handler files.

**Lesson:** An event-driven plugin architecture would decouple features from core and enable third-party extensions.

### 2. Event Bus

**GoMud:** Dedicated `internal/events/` package with typed events (`NewRound{}`, `LevelUp{}`, `PlayerEnter{}`), listener registration, event queue, and logging. Modules subscribe to events without coupling.

**ashveil-mud:** Bidirectional coupling — `CombatSession` takes `GameSession` callbacks as constructor parameters. IMPROVEMENTS.md A4 explicitly calls this out.

**Lesson:** An event bus would fix the A4 coupling issue and enable future feature composition.

### 3. Config System

**GoMud:** YAML with layered overrides: `config.yaml` → `world/default/config-overrides.yaml` → environment variables. Base config ships with the repo and is never edited by users. All gameplay values (combat formulas, death penalties, PVP rules, timings) are configurable.

**ashveil-mud:** `server/config.py` has 200+ lines of hardcoded constants. Changing balance requires editing Python.

**Lesson:** Move tuning values to a YAML config with layered overrides.

### 4. Scripting Engine

**GoMud:** Full scripting VM (`internal/scripting/`) — 16 Go source files. Scripts control room behavior, mob AI, dialogue, item interactions, spell effects. Timeout limits prevent runaway scripts. Scripting functions exposed for rooms, mobs, items, spells, parties, and utilities.

**ashveil-mud:** Room behavior is static JSON. Mob AI is string-based strategy rules parsed with `.startswith()` (IMPROVEMENTS.md A5).

**Lesson:** A lightweight scripting layer would let world designers add dynamic content without touching engine code.

### 5. Data Organization

**GoMud:** World data under `_datafiles/world/default/` — rooms, mobs, items, quests, spells, buffs, races, biomes, mutators, conversations, templates, users, plugin-data. YAML format with multiline strings for room descriptions.

**ashveil-mud:** JSON files in `server/data/` organized by type. Missing entire categories: quests, buffs, biomes, mutators, conversations, templates.

### 6. Room Tags for Extensibility

**GoMud:** Room struct carries `Tags []string` — a flat list of labels like `pvp-enabled`, `no-magic`, `underground`. Modules check tags to modify behavior without knowing about each other.

**ashveil-mud:** Rooms have a single `room_type` field (indoor/outdoor/underground). Tags would be a cheap extensibility boost.

### 7. Developer Infrastructure

**GoMud** has a Makefile with 12+ targets, Docker Compose, CI/CD with auto-release, code generation for module wiring.

**ashveil-mud** has only manual commands in AGENTS.md.

---

## Recommended Adoption Priority

### High Impact, Low Effort (Phase 1)

1. **Event Bus** — A simple `dict[str, list[Callable]]` dispatcher. Fixes A4 coupling, enables future features.
2. **YAML Config File** — Move `config.py` constants to `config.yaml` with layered overrides. Fixes hardcoded magic numbers.
3. **Makefile** — `make run`, `make test`, `make lint`. Standardize dev workflow.

### High Impact, Medium Effort (Phase 2)

4. **Quests System** — Data-driven quest definitions + progress tracker.
5. **Telnet Support** — asyncio telnet server for MUD client compatibility.
6. **Corpse/Looting System** — Makes death mechanics meaningful.

### Medium Impact, High Effort (Phase 3)

7. **Module/Plugin System** — Feature packages that auto-register via events. Natural follow-up to event bus.
8. **Scripting Engine** — Sandboxed Python for room/mob behavior. Enables player-created content.

### Architectural Patterns (Any Phase)

- Room tags as extension hooks
- Strongly typed events (Python dataclasses)
- Nested AGENTS.md for subsystems
- Config-driven gameplay formulas
