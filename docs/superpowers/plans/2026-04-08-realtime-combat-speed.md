# Real-Time Combat Speed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tick-multiplied attack interval with a direct per-character seconds-based interval so a thief (AGI 16) attacks every ~3 seconds and a heavy warrior (AGI 10, 40 lb gear) attacks every ~8 seconds, with the result shown in the STATS display.

**Architecture:** `character.action_interval` currently returns a floating number of *ticks* which the combat loop multiplies by `COMBAT_TICK_INTERVAL` (1.5 s) to get seconds — making attacks fire every 0.75–1.0 seconds. We change `action_interval` to return seconds directly using a new `BASE_ATTACK_SPEED` constant, remove both `* COMBAT_TICK_INTERVAL` multipliers from the combat loop (one for the recurring interval, one for the initial stagger), and display the result in `stats_summary`. `COMBAT_TICK_INTERVAL` stays in config — it is still used by battle_cry's cooldown-reduce-allies effect.

**Tech Stack:** Python dataclasses, asyncio sleep in `server/engine/combat.py`.

---

## File Map

| File | Change |
|------|--------|
| `server/config.py` | Add `BASE_ATTACK_SPEED`, `MIN_ATTACK_INTERVAL`, `MAX_ATTACK_INTERVAL` |
| `server/engine/character.py` | Update imports; rewrite `action_interval`; update `stats_summary` |
| `server/engine/combat.py` | Remove `* COMBAT_TICK_INTERVAL` from two lines in `_combatant_loop` |
| `tests/test_combat_speed.py` | New — tests for interval values and stats display |

---

### Task 1: Write Failing Speed Tests

**Files:**
- Create: `tests/test_combat_speed.py`

- [ ] **Step 1: Create the test file**

```python
"""
Tests for real-time per-character attack speed intervals.
"""
import pytest
from server.engine.character import Character


def _bare(class_type, AGI):
    """Character with no gear or carried items (clean speed calculation)."""
    c = Character(name="T", class_type=class_type, AGI=AGI)
    c.inventory = []
    c.equipment = {}
    return c


class TestActionIntervalSeconds:
    def test_thief_agility_16_attacks_every_3s(self, load_game_data):
        # 48.0 / 16 = 3.0
        char = _bare("thief", AGI=16)
        assert char.action_interval == pytest.approx(3.0)

    def test_warrior_agility_12_attacks_every_4s(self, load_game_data):
        # 48.0 / 12 = 4.0
        char = _bare("warrior", AGI=12)
        assert char.action_interval == pytest.approx(4.0)

    def test_mage_agility_12_attacks_every_4s(self, load_game_data):
        char = _bare("mage", AGI=12)
        assert char.action_interval == pytest.approx(4.0)

    def test_max_clamp_applies_for_very_low_speed(self, load_game_data):
        # AGI=3 (minimum stat), no gear → effective_speed=3 → 48/3=16.0 → clamped to MAX
        from server.config import MAX_ATTACK_INTERVAL
        char = _bare("warrior", AGI=3)
        assert char.action_interval == pytest.approx(MAX_ATTACK_INTERVAL)

    def test_min_clamp_applies(self, load_game_data):
        # If effective_speed is huge, interval must floor at MIN_ATTACK_INTERVAL
        from server.config import MIN_ATTACK_INTERVAL
        char = _bare("thief", AGI=18)
        # AGI=18 → 48/18 ≈ 2.67 > MIN (2.0) — patch speed to force the floor
        char.__class__ = type(
            "UltraFastChar",
            (Character,),
            {"effective_speed": property(lambda self: 100)},
        )
        # 48/100 = 0.48, clamped up to MIN_ATTACK_INTERVAL
        assert char.action_interval == pytest.approx(MIN_ATTACK_INTERVAL)

    def test_weight_penalty_slows_interval(self, load_game_data):
        # Warrior AGI=12, effective_speed=12; add weight so penalty=2 → speed=10 → 4.8s
        char = _bare("warrior", AGI=12)
        # Monkey-patch effective_speed (weight calculation tested separately)
        char.__class__ = type(
            "HeavyWarrior",
            (Character,),
            {"effective_speed": property(lambda self: 10)},
        )
        assert char.action_interval == pytest.approx(4.8)


class TestStatsDisplay:
    def test_stats_summary_shows_attack_interval(self, load_game_data):
        char = _bare("thief", AGI=16)
        summary = char.stats_summary()
        assert "3.0s/attack" in summary
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_combat_speed.py -v
```

Expected: `FAILED` — `ImportError: cannot import name 'BASE_ATTACK_SPEED'` or assertion errors (action_interval still returns ticks ≈ 0.5, not seconds ≈ 3.0).

---

### Task 2: Add Constants to `config.py`

**Files:**
- Modify: `server/config.py`

- [ ] **Step 3: Add three new constants after the `BASE_COOLDOWN_TICKS` block**

In `server/config.py`, find this block in the `# ── Combat ──` section:

```python
COMBAT_TICK_INTERVAL: float = 1.5  # Seconds between combat ticks
BASE_COOLDOWN_TICKS: int = 8       # Ticks before a speed-1 combatant acts
                                    # A speed-N combatant acts every
                                    # BASE_COOLDOWN_TICKS / N ticks (min 1)
```

Replace with:

```python
COMBAT_TICK_INTERVAL: float = 1.5  # Seconds between combat ticks (used by battle_cry only)
BASE_COOLDOWN_TICKS: int = 8       # Legacy — kept for combat.py import; no longer drives interval
BASE_ATTACK_SPEED: float = 48.0    # Numerator for attack interval (seconds):
                                    #   interval = BASE_ATTACK_SPEED / effective_speed
                                    # AGI 16 → 3.0 s | AGI 12 + 20 lb gear → 4.8 s
MIN_ATTACK_INTERVAL: float = 2.0   # Fastest any combatant may attack (seconds)
MAX_ATTACK_INTERVAL: float = 8.0   # Slowest any combatant may attack (seconds)
```

- [ ] **Step 4: Run tests to confirm they still fail (formula not updated yet)**

```
pytest tests/test_combat_speed.py -v
```

Expected: `ImportError` is gone; assertions still fail because `action_interval` still uses the old formula. Correct.

---

### Task 3: Rewrite `action_interval` in `character.py`

**Files:**
- Modify: `server/engine/character.py` (~line 21 imports, ~line 174 property, ~line 425 stats_summary)

- [ ] **Step 5: Update the config imports at the top of `character.py`**

Find:

```python
from server.config import (
    MODIFIER_BONUS_PER_LEVEL,
    WEIGHT_DIVISOR,
    BASE_COOLDOWN_TICKS,
    XP_TABLE,
)
```

Replace with:

```python
from server.config import (
    MODIFIER_BONUS_PER_LEVEL,
    WEIGHT_DIVISOR,
    BASE_ATTACK_SPEED,
    MIN_ATTACK_INTERVAL,
    MAX_ATTACK_INTERVAL,
    XP_TABLE,
)
```

(`BASE_COOLDOWN_TICKS` is removed from `character.py` only — it stays in `config.py` and `combat.py`'s own import.)

- [ ] **Step 6: Rewrite the `action_interval` property (~line 174)**

Find:

```python
    @property
    def action_interval(self) -> float:
        """Ticks between actions (float, used by CombatSession)."""
        return BASE_COOLDOWN_TICKS / self.effective_speed
```

Replace with:

```python
    @property
    def action_interval(self) -> float:
        """Seconds between attacks for this character.

        Formula: BASE_ATTACK_SPEED / effective_speed, clamped to [MIN, MAX].
        AGI 16, no gear → 3.0 s  |  AGI 12, 20 lb gear → 4.8 s
        """
        raw = BASE_ATTACK_SPEED / self.effective_speed
        return max(MIN_ATTACK_INTERVAL, min(MAX_ATTACK_INTERVAL, raw))
```

- [ ] **Step 7: Update the Speed line in `stats_summary` (~line 425)**

Find this line inside `stats_summary` (it is the only line containing `"  Speed  :"`):

```python
            f"  Speed  : {self.effective_speed}  (AGI {self.AGI} - wt penalty {math.floor(total_equipped_weight(self.equipment)/WEIGHT_DIVISOR)})",
```

Replace with:

```python
            f"  Speed  : {self.effective_speed}  →  {self.action_interval:.1f}s/attack  (AGI {self.AGI} - wt penalty {math.floor(total_equipped_weight(self.equipment)/WEIGHT_DIVISOR)})",
```

- [ ] **Step 8: Run speed tests — expect all to pass**

```
pytest tests/test_combat_speed.py -v
```

Expected: All 7 tests `PASS`.

---

### Task 4: Remove Tick Multipliers from the Combat Loop

**Files:**
- Modify: `server/engine/combat.py` (`_combatant_loop`, ~lines 420 and 443)

There are **two** `* COMBAT_TICK_INTERVAL` multiplications inside `_combatant_loop` that must both be removed. The `Combatant.cooldown` field is documented as seconds — it is initialised from `c.action_interval` (now already seconds), so multiplying again was always wrong.

- [ ] **Step 9: Remove the stagger multiplier (~line 420)**

Inside `_combatant_loop`, find:

```python
        # Stagger first action by the pre-set initial cooldown
        initial_delay = actor.cooldown * COMBAT_TICK_INTERVAL
```

Replace with:

```python
        # Stagger first action by the pre-set initial cooldown (already in seconds)
        initial_delay = actor.cooldown
```

- [ ] **Step 10: Remove the recurring-interval multiplier (~line 443)**

Still inside `_combatant_loop`, find:

```python
                # Sleep until next action, honouring any speed-up bonus
                interval = actor.character.action_interval * COMBAT_TICK_INTERVAL
```

Replace with:

```python
                # Sleep until next action, honouring any speed-up bonus
                interval = actor.character.action_interval
```

`COMBAT_TICK_INTERVAL` remains imported in `combat.py` — it is still used in `_resolve_skill` for the `cooldown_reduce_allies` (battle_cry) effect.

- [ ] **Step 11: Run the full test suite**

```
pytest tests/ -v
```

Expected: All tests pass with no regressions.

- [ ] **Step 12: Commit**

```
git add server/config.py server/engine/character.py server/engine/combat.py tests/test_combat_speed.py
git commit -m "feat: real-time per-character attack intervals driven by AGI (seconds-based)"
```

---

## Speed Reference Table

| Character | AGI | Gear weight | effective_speed | Interval |
|-----------|-----|-------------|----------------|----------|
| Thief (starter) | 16 | 0 lb | 16 | **3.0 s** |
| Mage (starter) | 12 | 3 lb robe | 12 | **4.0 s** |
| Warrior (starter) | 12 | 12 lb | 11 | **4.4 s** |
| Warrior (heavy kit) | 12 | 40 lb | 8 | **6.0 s** |
| Very slow combatant | 3 | 0 lb | 3 | 8.0 s *(clamped)* |

## Decisions

- `BASE_ATTACK_SPEED = 48.0` is a single constant in config — tuning it is a one-line change.
- `BASE_COOLDOWN_TICKS` is kept in `config.py` (and still imported by `combat.py`) to avoid touching unrelated imports. It can be cleaned up in a future refactor.
- `COMBAT_TICK_INTERVAL` continues to drive battle_cry's cooldown reduction in `_resolve_skill → cooldown_reduce_allies`.
- The `COMBAT_MIN_SLEEP = 0.3` floor remains — it prevents any combatant from acting more often than every 300 ms regardless of extreme speed values or bonuses.
