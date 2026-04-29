"""
Phase 4 — Food & Consumables: data model tests (Phase A).
Tests:
  - active_buffs field exists and defaults to {}
  - apply_food_buff() sets expiry keyed by buff name
  - apply_food_buff() replaces same-type buff (no stacking)
  - get_active_buffs() returns only unexpired buffs
  - to_dict() / from_dict() round-trip preserves active_buffs
"""
import pytest
from unittest.mock import MagicMock

from server.engine.domain.character import Character


def make_char():
    return Character(name="Tester", class_type="warrior")


def make_clock(total_minutes: int = 100):
    clock = MagicMock()
    clock.total_minutes = total_minutes
    return clock


# ── active_buffs field ────────────────────────────────────────────────────────

def test_character_has_active_buffs_field():
    c = make_char()
    assert hasattr(c, "active_buffs")


def test_active_buffs_defaults_to_empty_dict():
    c = make_char()
    assert c.active_buffs == {}


# ── apply_food_buff ───────────────────────────────────────────────────────────

def test_apply_food_buff_sets_expiry():
    c = make_char()
    clock = make_clock(total_minutes=100)
    c.apply_food_buff("alertness", 60, clock)
    assert "alertness" in c.active_buffs
    assert c.active_buffs["alertness"] == 160  # 100 + 60


def test_apply_food_buff_overwrites_existing_same_type():
    c = make_char()
    clock = make_clock(total_minutes=100)
    c.apply_food_buff("alertness", 60, clock)
    clock.total_minutes = 120
    c.apply_food_buff("alertness", 60, clock)
    # expiry should now be 180, not 160
    assert c.active_buffs["alertness"] == 180


def test_apply_food_buff_different_types_coexist():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("alertness", 60, clock)
    c.apply_food_buff("fortified", 120, clock)
    assert "alertness" in c.active_buffs
    assert "fortified" in c.active_buffs


# ── get_active_buffs ──────────────────────────────────────────────────────────

def test_get_active_buffs_returns_unexpired():
    c = make_char()
    clock = make_clock(total_minutes=100)
    c.apply_food_buff("alertness", 60, clock)  # expires at 160
    # Still at minute 100 — should be active
    result = c.get_active_buffs(clock)
    assert "alertness" in result


def test_get_active_buffs_excludes_expired():
    c = make_char()
    clock = make_clock(total_minutes=100)
    c.apply_food_buff("alertness", 60, clock)  # expires at 160
    clock.total_minutes = 161
    result = c.get_active_buffs(clock)
    assert "alertness" not in result


def test_get_active_buffs_at_exact_expiry_is_expired():
    c = make_char()
    clock = make_clock(total_minutes=100)
    c.apply_food_buff("alertness", 60, clock)  # expires at 160
    clock.total_minutes = 160
    result = c.get_active_buffs(clock)
    assert "alertness" not in result


def test_get_active_buffs_returns_empty_when_no_buffs():
    c = make_char()
    clock = make_clock(total_minutes=100)
    assert c.get_active_buffs(clock) == []


def test_get_active_buffs_returns_multiple_active():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("alertness", 60, clock)
    c.apply_food_buff("fortified", 120, clock)
    result = c.get_active_buffs(clock)
    assert "alertness" in result
    assert "fortified" in result


# ── Serialisation round-trip ──────────────────────────────────────────────────

def test_to_dict_includes_active_buffs():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("satiated", 180, clock)
    d = c.to_dict()
    assert "active_buffs" in d
    assert d["active_buffs"]["satiated"] == 180


def test_from_dict_restores_active_buffs():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("energised", 90, clock)
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.active_buffs == {"energised": 90}


def test_from_dict_defaults_active_buffs_to_empty_when_missing():
    """Old save data without active_buffs should default gracefully."""
    c = make_char()
    d = c.to_dict()
    d.pop("active_buffs", None)
    c2 = Character.from_dict(d)
    assert c2.active_buffs == {}
