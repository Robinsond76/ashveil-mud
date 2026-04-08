# Ashveil MUD — Architecture & Test Improvements

## Executive Summary

A comprehensive review of all 12 engine files and 17 test files identified **19 architecture findings** and **14 test suite findings** across three severity levels. This document catalogs every finding and links to detailed implementation plans.

**Recommended execution order:** 03 → 01 → 02 → 04 → 05 → 06 → 07
(Data model cleanup first, then decompose game.py, then combat, async, config, and tests last.)

---

## Architecture Findings

### Critical (5)

| ID | Finding | Primary File(s) | Plan |
|----|---------|-----------------|------|
| A1 | **God Object — `game.py` is 1,855 lines** with 65+ methods on `GameSession`, handling all states, all commands, survival, chat, mounts, cart, light, help topics (107 entries at line 72), and display | `server/engine/game.py` | [Improvement 01](docs/superpowers/plans/improvement-01-game-session-decomposition.md) |
| A2 | **Character/NPC inheritance leaks** — `Character` dataclass carries `strategies`, `grid_row`, `grid_col`, `active_buffs` that are only meaningful in combat/NPC context; no shared `Combatant` protocol | `server/engine/character.py`, `server/engine/npc.py` | [Improvement 03](docs/superpowers/plans/improvement-03-data-model-cleanup.md) |
| A3 | **Global mutable state without synchronization** — `WorldMap.room_occupants` (line 114), `WorldClock._subscribers`, and `_sessions` dict are mutated by concurrent async tasks with no `asyncio.Lock` | `server/engine/world.py`, `server/engine/world_clock.py`, `server/main.py` | [Improvement 04](docs/superpowers/plans/improvement-04-async-safety.md) |
| A4 | **CombatSession ↔ GameSession bidirectional coupling** — `CombatSession.__init__()` (line 169) takes `on_end` callback that calls back into `GameSession._end_combat_victory/defeat`; cannot reuse combat independently | `server/engine/combat.py`, `server/engine/game.py` | [Improvement 02](docs/superpowers/plans/improvement-02-combat-architecture.md) |
| A5 | **String-based action dispatch** — `evaluate_strategy()` returns raw strings like `"USE_SKILL fireball"`; `_do_action()` (line 493) parses them with `.startswith()` checks | `server/engine/strategy.py`, `server/engine/combat.py` | [Improvement 02](docs/superpowers/plans/improvement-02-combat-architecture.md) |

### Important (8)

| ID | Finding | Primary File(s) | Plan |
|----|---------|-----------------|------|
| A6 | **Implicit combat state machine** — `_check_combat_end()` (line 467) sets `self.state` without atomic guard; multiple combatant tasks can race to set VICTORY/DEFEAT | `server/engine/combat.py` | [Improvement 02](docs/superpowers/plans/improvement-02-combat-architecture.md) |
| A7 | **Survival stat logic scattered across 3 files** — drain rates in `character.py` (line 240), tick callbacks in `game.py` (line 845), clock subscription in `game.py` (line 770) | `character.py`, `game.py`, `world_clock.py` | [Improvement 01](docs/superpowers/plans/improvement-01-game-session-decomposition.md) |
| A8 | **NPC respawn only ticks during combat** — `tick_respawns()` (world.py line 174) is called from combat end, not from a periodic global tick; rooms never respawn while idle | `server/engine/world.py` | [Improvement 04](docs/superpowers/plans/improvement-04-async-safety.md) |
| A9 | **Light source expiry not persisted** — `_lit_sources` dict (game.py line 754) tracks burning torches/lanterns but is NOT included in `Character.to_dict()` or `save_player()` | `server/engine/game.py`, `server/engine/persistence.py` | [Improvement 05](docs/superpowers/plans/improvement-05-config-and-validation.md) |
| A10 | **Missing ownership/permission system** — Any player can EQUIP, DISMISS, or GIVE items to another player's companions in multiplayer; no `owner` field on Character/NPC | `server/engine/game.py` | [Improvement 03](docs/superpowers/plans/improvement-03-data-model-cleanup.md) |
| A11 | **Fragile combat position assignment** — `_assign_positions()` (line 198) silently clamps overflow to column 2 with `min(back_col, 2)`; parties >6 silently drop members | `server/engine/combat.py` | [Improvement 02](docs/superpowers/plans/improvement-02-combat-architecture.md) |
| A12 | **Magic numbers throughout** — `2.0` stamina per move (game.py:1682), `1.0` sit recovery (game.py:857), `0.40` flee chance (combat.py:485), `1.5` crit multiplier (character.py:167) | Multiple files | [Improvement 05](docs/superpowers/plans/improvement-05-config-and-validation.md) |
| A13 | **Error handling gaps at system boundaries** — DB commit failures logged but don't block progression; WebSocket handler catches all exceptions generically; no save schema version check | `server/main.py`, `server/engine/persistence.py` | [Improvement 05](docs/superpowers/plans/improvement-05-config-and-validation.md) |

### Nice-to-Have (6)

| ID | Finding | Primary File(s) | Plan |
|----|---------|-----------------|------|
| A14 | **Skill/modifier system complexity** — `MODIFIER_CATALOGUE` (character.py line 43) is a flat dict mixing weapon proficiencies and spell intensifiers; no dependency graph validation | `server/engine/skills.py`, `server/engine/character.py` | [Improvement 03](docs/superpowers/plans/improvement-03-data-model-cleanup.md) |
| A15 | **No JSON schema validation on data load** — `world.py:load()` doesn't validate exit references, NPC template IDs, or room connectivity | `server/engine/world.py` | [Improvement 05](docs/superpowers/plans/improvement-05-config-and-validation.md) |
| A16 | **Implicit item effects** — Item effects are raw dicts; `_do_action()` in combat manually checks `et == "heal"` (line 615), `et == "restore_mp"` (line 640) | `server/engine/combat.py`, `server/engine/items.py` | [Improvement 03](docs/superpowers/plans/improvement-03-data-model-cleanup.md) |
| A17 | **Display output deeply nested in domain logic** — `_HELP_TOPICS` (107 entries at game.py line 72), combat banners (combat.py line 867) mix formatting with game rules | `server/engine/game.py`, `server/engine/combat.py` | [Improvement 01](docs/superpowers/plans/improvement-01-game-session-decomposition.md) |
| A18 | **XP table hardcoded as array** — `XP_TABLE` (character.py line 27) is a fixed 10-element list; can't extend past level 10 or tune difficulty without code edits | `server/engine/character.py` | [Improvement 05](docs/superpowers/plans/improvement-05-config-and-validation.md) |
| A19 | **Sitting recovery timing implicit** — `_sitting_stamina_tick()` fires inside the weather/clock callback (game.py line 854); recovery speed is implicitly coupled to world tick rate | `server/engine/game.py` | [Improvement 01](docs/superpowers/plans/improvement-01-game-session-decomposition.md) |

---

## Test Suite Findings

### Critical (5)

| ID | Finding | File(s) | Plan |
|----|---------|---------|------|
| T1 | **Trivial pass tests** — 10+ tests in `test_phase02_character.py` only check `assert c.hunger == 100.0` (field initialization); 185 individual tests in `test_phase08_help_system.py` that should be 1 parametrized test | `test_phase02_character.py`, `test_phase08_help_system.py` | [Improvement 06](docs/superpowers/plans/improvement-06-test-organization.md) |
| T2 | **Weak assertions** — Tests like `assert output` (passes if ANY text returned, not checking correctness); OR-chain assertions accept 3+ error messages interchangeably | `test_phase02_commands.py`, `test_phase03_utility_skills.py` | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |
| T3 | **No error path testing** — Missing: MP cost edge cases, party full capacity, wrong-state commands, malformed input | Multiple | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |
| T4 | **Excessive mocking hides real bugs** — `WorldMap.__new__()` bypasses `__init__()` (test_phase02_drain.py); `MagicMock()` for clock is permissive (test_phase04_buff_hooks.py) | `test_phase02_drain.py`, `test_phase04_buff_hooks.py` | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |
| T5 | **No async/concurrency testing** — Zero tests for two combats in parallel, concurrent broadcasts, race conditions on `room_occupants` | `test_phase09_multiplayer_foundations.py` | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |

### Important (5)

| ID | Finding | File(s) | Plan |
|----|---------|---------|------|
| T6 | **EAT/DRINK duplicated across Phase 2 & 4** — Nearly identical tests in `test_phase02_commands.py` (lines 31–95) and `test_phase04_commands.py` (lines 131–264) | `test_phase02_commands.py`, `test_phase04_commands.py` | [Improvement 06](docs/superpowers/plans/improvement-06-test-organization.md) |
| T7 | **`make_nav_session()` copied 3 times** — Same helper duplicated in `test_phase02_commands.py`, `test_phase03_utility_skills.py`, `test_phase04_buff_hooks.py` with minor variations | 3 test files | [Improvement 06](docs/superpowers/plans/improvement-06-test-organization.md) |
| T8 | **Unbalanced test file sizes** — `test_phase02_character.py` is 45 lines; `test_phase07_wizard_spell_overhaul.py` is 550+ lines | Multiple | [Improvement 06](docs/superpowers/plans/improvement-06-test-organization.md) |
| T9 | **Inconsistent test naming** — `test_look_shows_stamina_warning_when_zero` doesn't describe what LOOK does; `test_mage_spell_power_modifier_adds_staff_bonus` only checks attribute exists | Multiple | [Improvement 06](docs/superpowers/plans/improvement-06-test-organization.md) |
| T10 | **Untested commands** — SAY, EMOTE, SHOUT, EXAMINE have zero test coverage; `_handle_strategy()` state has no dedicated tests | `test_phase09_multiplayer_foundations.py` | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |

### Nice-to-Have (4)

| ID | Finding | File(s) | Plan |
|----|---------|---------|------|
| T11 | **Non-deterministic tests** — `random.seed(42)` in combat penalty tests; probabilistic `len(results) > 1` assertion in wizard tests | `test_phase02_combat_penalties.py`, `test_phase07_wizard_spell_overhaul.py` | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |
| T12 | **No integration test** — No test exercises the full flow: CONNECT → CREATE → NAVIGATE → ATTACK → REST → WIN | None exists | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |
| T13 | **No persistence roundtrip test** — `save_player()` / `load_player()` never actually called in tests; `to_dict()`/`from_dict()` tested trivially | `test_phase02_character.py` | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |
| T14 | **No performance/stress tests** — Large party, 1000-item inventory, concurrent combats never tested | None exists | [Improvement 07](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) |

---

## Priority Matrix

| Plan | Impact | Effort | Findings Addressed |
|------|--------|--------|-------------------|
| [Improvement 03 — Data Model Cleanup](docs/superpowers/plans/improvement-03-data-model-cleanup.md) | HIGH | MEDIUM | A2, A10, A14, A16 |
| [Improvement 01 — GameSession Decomposition](docs/superpowers/plans/improvement-01-game-session-decomposition.md) | HIGH | HIGH | A1, A7, A17, A19 |
| [Improvement 02 — Combat Architecture](docs/superpowers/plans/improvement-02-combat-architecture.md) | HIGH | HIGH | A4, A5, A6, A11 |
| [Improvement 04 — Async Safety](docs/superpowers/plans/improvement-04-async-safety.md) | HIGH | MEDIUM | A3, A8 |
| [Improvement 05 — Config & Validation](docs/superpowers/plans/improvement-05-config-and-validation.md) | MEDIUM | LOW | A9, A12, A13, A15, A18 |
| [Improvement 06 — Test Organization](docs/superpowers/plans/improvement-06-test-organization.md) | MEDIUM | LOW | T1, T6, T7, T8, T9 |
| [Improvement 07 — Test Coverage Gaps](docs/superpowers/plans/improvement-07-test-coverage-gaps.md) | MEDIUM | MEDIUM | T2, T3, T4, T5, T10, T11, T12, T13, T14 |

---

## Notes

- **Architecture improvements (01–05) should land before test improvements (06–07)** to avoid restructuring tests twice.
- **Improvement 03 (data model) should go first** because 01 and 02 both depend on cleaner Character/NPC boundaries.
- Run `pytest tests/` after every sub-step of every plan to catch regressions early.
