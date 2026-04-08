"""
Phase 2 — Survival Stats: Character-level tests (Phase A).
"""
import pytest
from server.engine.character import Character


def make_char(name="Tester", class_type="warrior"):
    return Character(name=name, class_type=class_type)


# ── Phase A: Default field values ────────────────────────────────────────────

def test_character_initializes_with_survival_defaults():
    """All survival stats should initialize to their max values."""
    c = make_char()
    assert c.hunger == 100.0
    assert c.max_hunger == 100.0
    assert c.thirst == 100.0
    assert c.max_thirst == 100.0
    assert c.stamina == 100.0
    assert c.max_stamina == 100.0


# ── Phase A: hunger_drain_rate ────────────────────────────────────────────────

def test_hunger_drain_rate_returns_float():
    c = make_char()
    assert isinstance(c.hunger_drain_rate(), float)


def test_hunger_drain_rate_positive():
    c = make_char()
    assert c.hunger_drain_rate() > 0


# ── Phase A: thirst_drain_rate uses temperature multipliers ──────────────────

def test_thirst_drain_rate_base_for_cold_temps():
    c = make_char()
    for label in ("Freezing", "Bitter Cold", "Cold", "Cool", "Comfortable"):
        rate = c.thirst_drain_rate(label)
        # Base rate * 1.0x — just check it equals the cold-baseline
        assert rate == c.thirst_drain_rate("Comfortable"), (
            f"label '{label}' should give the same rate as 'Comfortable'"
        )


def test_thirst_drain_rate_hot_is_1_5x():
    c = make_char()
    base = c.thirst_drain_rate("Comfortable")
    hot  = c.thirst_drain_rate("Hot")
    assert abs(hot - base * 1.5) < 1e-9


def test_thirst_drain_rate_scorching_is_2x():
    c = make_char()
    base = c.thirst_drain_rate("Comfortable")
    scorch = c.thirst_drain_rate("Scorching")
    assert abs(scorch - base * 2.0) < 1e-9


# ── Phase A: serialisation round-trip ────────────────────────────────────────

def test_survival_stats_round_trip():
    c = make_char()
    c.hunger  = 42.5
    c.thirst  = 30.0
    c.stamina = 75.0
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.hunger  == 42.5
    assert c2.thirst  == 30.0
    assert c2.stamina == 75.0


def test_survival_max_fields_round_trip():
    c = make_char()
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.max_hunger  == 100.0
    assert c2.max_thirst  == 100.0
    assert c2.max_stamina == 100.0
