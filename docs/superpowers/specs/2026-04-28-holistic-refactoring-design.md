# Holistic Codebase Refactoring — Design Spec

**Date:** 2026-04-28
**Status:** Design approved — pending implementation plan
**Scope:** Production code architecture (A2-A19). Test findings (T1-T14) deferred.

---

## 1. Goal

Reorganize `server/engine/` into domain-focused subpackages, eliminate all 18 remaining architecture findings from IMPROVEMENTS.md, and establish clean import boundaries with no circular dependencies.

**Priority:** Best structure. Tests updated to match, not preserved as-is.

---

## 2. Target Package Structure

```
server/
  main.py                   # FastAPI entry (unchanged)
  config.py                 # All constants (unchanged)
  engine/
    domain/                 # Pure data models — no game logic
      __init__.py
      character.py          # Character dataclass (player only)
      npc.py                # NPC dataclass (extends Character)
      combatant.py          # Combatant Protocol (upgraded)
      items.py              # Item dataclass + catalogue
      skills.py             # Skill dataclass + catalogue
    combat/                 # Everything battle-related
      __init__.py
      session.py            # CombatSession (decoupled from game.py)
      actions.py            # Attack, Defend, Flee, UseSkill, UseItem (enum dispatch)
      strategy.py           # NPC AI evaluation (enum-based action returns)
      grid.py               # Position grid, assignments
      rewards.py            # Loot, XP, gold distribution
    display/                # Output formatting — no game logic
      __init__.py
      formatting.py         # _box(), divider, colors, shared display utils
      context_panel.py      # Context panel data gathering (from game.py)
      help_data.py          # Help topic catalogue (from help_registry.py)
    world/                  # World simulation
      __init__.py
      map.py                # WorldMap (from world.py)
      clock.py              # WorldClock (from world_clock.py)
      environment.py        # Weather, light, temperature
    systems/                # Game mechanics
      __init__.py
      inventory.py          # Inventory operations (from inventory_ops.py)
      survival.py           # Hunger, thirst, stamina drain, recovery
      campfire.py           # Rest, formation, manage
      chat.py               # Say, emote, shout
      mounts.py             # Horses, carts (extracted from game.py)
      utility_skills.py     # Non-combat skill effects (extracted from game.py)
    persistence.py          # Save/load + schema validation (upgraded)
    states/                 # State handlers
      __init__.py            # State enum + registry (unchanged)
      base.py               # StateHandler Protocol (unchanged)
      connect.py            # Connect handler
      creation.py           # Character creation
      combat.py             # Combat handler (simplified)
      campfire.py           # Campfire handler (simplified)
      strategy.py           # Strategy editor
      contexts.py           # Context panel helpers
      navigation.py         # Navigation handler (~150 lines — dispatches to submodules)
      navigation/
        __init__.py
        inventory.py        # Inventory, equip, unequip, drop
        party.py            # Stats, gold, skills, learn, modifiers, upgrade
        social.py           # Say, emote, shout, examine
        interaction.py      # Attack, talk, pick up, give
        mounts.py           # Ride, dismount, horses, cart commands
        quick_look.py       # LOOKMODE, BATTLELOOK
```

### What stays unchanged
- `server/config.py` — constants already extracted
- `server/main.py` — FastAPI entry point
- `server/data/` — JSON data files
- `client/` — browser terminal
- `pyproject.toml`, `pytest.ini`

---

## 3. Finding-by-Finding Resolution

### Critical (A2-A5)

| ID | Finding | Resolution |
|----|---------|------------|
| **A2** | Character/NPC inheritance leaks | NPC extends Character but `combat_speed`, `grid_row`, `grid_col`, `strategies`, `active_buffs` move to a `CombatantState` wrapper created when combat starts. NPC never carries combat-only state outside combat. |
| **A3** | Global mutable state without locks | `WorldMap._occupants_lock` (asyncio.Lock) protects `room_occupants`. `WorldClock._sub_lock` protects `_subscribers`. `SessionRegistry` dataclass in `main.py` holds `_sessions` with its own lock. |
| **A4** | CombatSession↔GameSession bidirectional coupling | Remove `on_end` callback. `CombatSession.run_and_get_result()` returns `CombatResult`. Caller (state handler) decides next steps. No combat code references game.py. |
| **A5** | String-based action dispatch | `evaluate_strategy()` returns `StrategyAction` enum objects. Combat dispatch uses `match/case` on action type. |

### Important (A6-A13)

| ID | Finding | Resolution |
|----|---------|------------|
| **A6** | Implicit combat state machine | `CombatPhase` class with atomic transitions. `asyncio.Lock` guards state changes. |
| **A7** | Survival logic scattered | Centralized in `systems/survival.py`. Single `SurvivalTickHandler` function called from GameSession's clock tick callback. |
| **A8** | NPC respawn only during combat | `WorldMap.tick_respawns()` runs on WorldClock tick loop. Configurable `RESPAWN_CHECK_INTERVAL` (default: 5 game-minutes). |
| **A9** | Light sources not persisted | `lit_sources` added to `Character.to_dict()`/`from_dict()`. Schema version = 2. Migration reads v1 saves gracefully. |
| **A10** | Missing ownership enforcement | `NPC.owner` field validated in equip/dismiss/give. Mismatch returns error. |
| **A11** | Fragile position assignment | `CombatTooManyMembers` exception instead of silent clamping. Handled gracefully at combat init. |
| **A12** | Magic numbers | Verified all extracted to `config.py`. Remove any remaining inline constants. |
| **A13** | Error handling gaps | Persistence functions return `Result[T, Error]`. Schema version check on load. Player receives feedback on failure. |

### Nice-to-Have (A14-A19)

| ID | Finding | Resolution |
|----|---------|------------|
| **A14** | Flat MODIFIER_CATALOGUE | Split into `WEAPON_PROFS` and `SPELL_INTENSIFIERS`. `ModifierType` enum distinguishes them. |
| **A15** | No JSON schema validation | Pydantic models validate room, item, NPC, skill JSON at load time. Invalid data fails fast at startup. |
| **A16** | Implicit item effects | `ItemEffect` enum replaces string matching. Dispatch uses match-case on enum. |
| **A17** | Display mixed with logic | Help text → `display/help_data.py`. Combat banners → `display/formatting.py`. Pure formatting functions. |
| **A18** | XP table hardcoded | Already in config.py. Add `MAX_LEVEL` constant and table-length validation. |
| **A19** | Sitting recovery timing implicit | `SIT_STAMINA_RECOVERY_RATE` already configurable. `systems/survival.py` uses it explicitly. |

---

## 4. Major Refactoring Details

### 4.1 NavigationHandler Split (884 → ~150 lines)

Current `states/navigation.py` handles 30+ commands via method dispatch dict. After split:

```
states/navigation.py (~150 lines)
  - Class skeleton: on_enter, on_exit, handle
  - Direction aliases, _do_move, _do_look
  - Attribute delegates to submodule functions

states/navigation/inventory.py
  - Functions: do_inventory, do_equip, do_unequip, do_drop
  - Each takes (session, args) → async

states/navigation/party.py
  - Functions: do_stats, do_gold, do_skills, do_learn, do_modifiers, do_upgrade

states/navigation/social.py
  - Functions: do_say, do_emote, do_shout, do_examine

states/navigation/interaction.py
  - Functions: do_attack, do_talk, do_pick_up, do_give

states/navigation/mounts.py
  - Functions: do_ride, do_dismount, do_horses, load_cart, unload_cart

states/navigation/quick_look.py
  - Functions: do_lookmode, do_battlelook
```

Each submodule is a flat module (no class). NavigationHandler's command dict imports and calls these functions.

### 4.2 GameSession Cleanup (1058 → ~300 lines)

**Kept in game.py:**
- Session lifecycle (`__init__`, `start`, `handle_input`, `transition_to`)
- Core services (`send`, `broadcast_to_room`)
- Clock subscription/unsubscription
- State property + transition
- `_load_save` (persistence glue)
- `_send_help` (delegates to display module)
- `_try_recruit_response` (tightly coupled to pending_recruit state)

**Moved out:**

| Section | Lines | Destination |
|---------|-------|-------------|
| `_box()` | 5 | `display/formatting.py` |
| Context panel (_gather_context + helpers) | 180 | `display/context_panel.py` |
| Utility skill handler (_handle_use_skill, _execute_utility_effect) | 115 | `systems/utility_skills.py` |
| Campfire helpers (_do_formation, _do_manage, _do_show_party, _do_learn, _do_modifiers, _do_upgrade, _do_dismiss) | 90 | `states/campfire.py` or `systems/campfire.py` |
| Combat init (_start_combat) | 45 | `states/combat.py` |
| Mount/cart logic (_do_ride, _do_dismount, _do_horses, stamina_multiplier, horse_count, _party_has_cart) | 55 | `systems/mounts.py` |
| Survival/environment wrappers (_do_*) | 90 | Delete — callers import from `systems/` directly |
| Backward-compatible wrappers | 200 | **Delete** — existing callers updated to use handlers directly |
| Duplicate `_handle_campfire` method | 14 | Delete (appears twice on lines 699/705) |

### 4.3 Import Architecture

Dependency graph flows top-down, no cycles:

```
┌──────────────────────────────────────────────────────┐
│  config.py          domain/                          │
│  (zero deps)        (zero deps — pure data)          │
├──────────────────────────────────────────────────────┤
│  world/             persistence.py                   │
│  (domain + config)  (domain + config)                │
├──────────────────────────────────────────────────────┤
│  systems/           combat/           display/       │
│  (domain+world+     (domain+config)   (domain+world+ │
│   config)                              config)       │
├──────────────────────────────────────────────────────┤
│  states/                                              │
│  (domain + systems + combat + display + world)       │
├──────────────────────────────────────────────────────┤
│  game.py                                              │
│  (states + world + config — thin coordinator)        │
└──────────────────────────────────────────────────────┘
```

**Key rules:**
- `domain/` imports nothing from `server.engine` (only stdlib + config)
- `combat/` imports nothing from `systems/`, `world/`, `states/`
- `display/` is purely formatting — no game logic
- `states/` is the integration layer — may import from all lower layers
- `game.py` imports states + world + config only
- No file imports from `game.py` except `main.py`

---

## 5. Combat Session Decoupling (A4 Detail)

### Before (current)
```python
class CombatSession:
    def __init__(self, ..., on_end: Callable):
        self._on_end = on_end  # Calls back into GameSession

    async def run_and_get_result(self) -> CombatResult:
        # ... combat loop ...
        if victory:
            await self._on_end("victory")  # Tight coupling
        else:
            await self._on_end("defeat")
```

### After
```python
class CombatSession:
    def __init__(self, player_party, enemy_party, send, lighting, survival_multiplier):
        # No on_end callback

    async def run_and_get_result(self) -> CombatResult:
        # ... combat loop ...
        return CombatResult(state="victory", summary=self.summary)

# Caller (CombatHandler) handles the result:
result = await combat.run_and_get_result()
await send("\n".join(result.summary))
if result.state == "victory":
    encounter_group.mark_defeated()
    combat.collect_rewards(player_party, class_defs)
    await self._handle_victory(session)
else:
    await self._handle_defeat(session)
```

---

## 6. Execution Order

1. **Display layer** — Extract `_box()` to `display/formatting.py`, migrate `help_registry.py` to `display/help_data.py`, extract context panel. Zero logic changes, purely moving formatting code.
2. **Domain layer** — Create `engine/domain/` package. Move `character.py`, `npc.py`, `items.py`, `skills.py`, `combatant.py`. Add `CombatantState` wrapper. Update all imports.
3. **World layer** — Create `engine/world/`. Move `map.py`, `clock.py`, `environment.py`. Add async locks. Fix A8 (respawn on tick).
4. **Systems layer** — Create `engine/systems/`. Move `survival.py`, `inventory.py`, `campfire.py`, `chat.py`. Create `mounts.py`, `utility_skills.py` from game.py extraction. Fix A7, A10, A19.
5. **Combat layer** — Create `engine/combat/`. Restructure `session.py`, `actions.py`, `strategy.py`, `grid.py`, `rewards.py`. Fix A4, A5, A6, A11, A16.
6. **GameSession cleanup** — Remove backward-compatible wrappers. Update callers. Delete duplicated methods. Fix A9 (persist light sources), A13 (error handling).
7. **Final polish** — Fix A14 (split MODIFIER_CATALOGUE), A15 (Pydantic validation), A17 (display cleanup), A18 (MAX_LEVEL validation).

Each step concludes with `pytest tests/` to catch regressions.

---

## 7. Risk Mitigation

- **Step granularity:** Each step touches 1-3 packages. Tests run after every step.
- **New code only:** Create new modules in new packages first. Keep old files until all callers are migrated.
- **Import migration:** Use the IDE/agent to update imports across the codebase automatically (search-replace on `from server.engine.X import` → `from server.engine.PACKAGE.X import`).
- **Rollback:** Each step is committed separately. Git revert any step if tests break unexpectedly.
- **help_registry.py safety:** The 1002-line dict moves to `display/help_data.py`. No logic changes — rename and fix imports. Only the `_box()` calls change (import from formatting.py).

---

## 8. What This Does NOT Change

- Public API (WebSocket protocol, message formats)
- Game balance or mechanics
- Data file formats (JSON in `server/data/`)
- Client-side code (`client/`)
- Configuration values
- Database schema (except version bump for lit_sources)
