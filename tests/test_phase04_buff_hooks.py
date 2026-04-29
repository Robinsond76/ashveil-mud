"""
Phase 4 — Food & Consumables: buff hook tests (Phase B).
Tests:
  - alertness → dodge_bonus() +15%
  - satiated  → hunger_drain_rate() 0.6x
  - quenched  → thirst_drain_rate() 0.6x
  - energised → _sitting_stamina_tick() +1.5/min
  - fortified → _do_move() stamina drain 0.7x
  - focused   → spell intensity scale +0.1
  - _drain_survival_tick honours satiated/quenched via clock
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from server.engine.domain.character import Character
from server.engine.game import GameSession, State
from server.engine.world.map import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_char(name="Tester", class_type="warrior"):
    return Character(name=name, class_type=class_type)


def make_clock(total_minutes: int = 0):
    clock = MagicMock()
    clock.total_minutes = total_minutes
    return clock


# ── alertness → dodge_bonus ───────────────────────────────────────────────────

def test_alertness_increases_dodge_bonus():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("alertness", 60, clock)
    bonus = c.dodge_bonus(clock)
    assert bonus == pytest.approx(0.15)


def test_dodge_bonus_without_alertness_unaffected():
    c = make_char()
    clock = make_clock(total_minutes=0)
    assert c.dodge_bonus(clock) == pytest.approx(0.0)


def test_dodge_bonus_alertness_stacks_with_modifier():
    c = make_char()
    c.modifiers["dodge_mastery"] = 1  # +0.05 from modifier
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("alertness", 60, clock)
    bonus = c.dodge_bonus(clock)
    from server.config import MODIFIER_BONUS_PER_LEVEL
    expected = 1 * MODIFIER_BONUS_PER_LEVEL + 0.15
    assert bonus == pytest.approx(expected)


def test_alertness_no_dodge_bonus_when_expired():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("alertness", 60, clock)
    clock.total_minutes = 200
    assert c.dodge_bonus(clock) == pytest.approx(0.0)


# ── satiated → hunger_drain_rate ─────────────────────────────────────────────

def test_satiated_reduces_hunger_drain():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("satiated", 180, clock)
    rate = c.hunger_drain_rate(clock)
    assert rate == pytest.approx(0.1 * 0.6)


def test_hunger_drain_rate_without_satiated():
    c = make_char()
    clock = make_clock(total_minutes=0)
    assert c.hunger_drain_rate(clock) == pytest.approx(0.1)


def test_hunger_drain_rate_no_clock_uses_base():
    c = make_char()
    assert c.hunger_drain_rate() == pytest.approx(0.1)


# ── quenched → thirst_drain_rate ─────────────────────────────────────────────

def test_quenched_reduces_thirst_drain():
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("quenched", 120, clock)
    rate = c.thirst_drain_rate("Comfortable", clock)
    assert rate == pytest.approx(0.15 * 0.6)


def test_thirst_drain_rate_without_quenched():
    c = make_char()
    clock = make_clock(total_minutes=0)
    assert c.thirst_drain_rate("Comfortable", clock) == pytest.approx(0.15)


def test_thirst_drain_rate_quenched_plus_hot():
    """Quenched and hot temp: 0.15 * 1.5 * 0.6"""
    c = make_char()
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("quenched", 120, clock)
    rate = c.thirst_drain_rate("Hot", clock)
    assert rate == pytest.approx(0.15 * 1.5 * 0.6)


# ── energised → _sitting_stamina_tick ────────────────────────────────────────

def test_energised_increases_sit_recovery(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.stamina = 50.0
    session.player.apply_food_buff("energised", 90, clock)
    session._sitting = True
    session._sitting_stamina_tick()
    assert session.player.stamina == pytest.approx(51.5)


def test_energised_expired_gives_normal_recovery(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.stamina = 50.0
    session.player.apply_food_buff("energised", 90, clock)
    clock.total_minutes = 200  # expired
    session._sitting = True
    session._sitting_stamina_tick()
    assert session.player.stamina == pytest.approx(51.0)


def test_no_energised_normal_sit_recovery(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.stamina = 50.0
    session._sitting = True
    session._sitting_stamina_tick()
    assert session.player.stamina == pytest.approx(51.0)


# ── fortified → _do_move stamina drain ───────────────────────────────────────

def test_fortified_reduces_move_stamina_drain(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.stamina = 100.0
    session.player.apply_food_buff("fortified", 120, clock)

    # Mock a navigable room to move into
    from server.engine.world.map import Room
    dest_room = Room(id="r2", name="Dest", description="", exits={}, item_ids=[], encounter_groups=[], recruitable_npc_ids=[])
    source_room = Room(id="r1", name="Src", description="", exits={"north": "r2"}, item_ids=[], encounter_groups=[], recruitable_npc_ids=[])
    session.world.get_room = lambda rid: dest_room if rid == "r2" else source_room
    session.world.active_encounter_groups = lambda rid: []
    session.current_room_id = "r1"

    asyncio.get_event_loop().run_until_complete(session._do_move("north"))
    # Normal drain = 2.0, fortified = 2.0 * 0.7 = 1.4
    assert session.player.stamina == pytest.approx(98.6)


def test_no_fortified_normal_move_drain(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.stamina = 100.0

    from server.engine.world.map import Room
    dest_room = Room(id="r2", name="Dest", description="", exits={}, item_ids=[], encounter_groups=[], recruitable_npc_ids=[])
    source_room = Room(id="r1", name="Src", description="", exits={"north": "r2"}, item_ids=[], encounter_groups=[], recruitable_npc_ids=[])
    session.world.get_room = lambda rid: dest_room if rid == "r2" else source_room
    session.world.active_encounter_groups = lambda rid: []
    session.current_room_id = "r1"

    asyncio.get_event_loop().run_until_complete(session._do_move("north"))
    assert session.player.stamina == pytest.approx(98.0)


# ── _drain_survival_tick passes clock to drain rates ─────────────────────────

def test_drain_survival_tick_honours_satiated_buff(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.hunger = 100.0
    session.player.apply_food_buff("satiated", 180, clock)
    session._drain_survival_tick("Comfortable")
    # satiated rate = 0.1 * 0.6 = 0.06
    assert session.player.hunger == pytest.approx(100.0 - 0.06)


def test_drain_survival_tick_honours_quenched_buff(make_nav_session):
    clock = make_clock(total_minutes=0)
    session = make_nav_session(clock=clock)
    session.player.thirst = 100.0
    session.player.apply_food_buff("quenched", 120, clock)
    session._drain_survival_tick("Comfortable")
    # quenched rate = 0.15 * 0.6 = 0.09
    assert session.player.thirst == pytest.approx(100.0 - 0.09)


# ── focused → spell intensity in combat ──────────────────────────────────────

def test_focused_adds_to_spell_intensity_bonus():
    """Character with focused buff gets +0.1 added to spell_intensity_bonus."""
    c = Character(name="Mage", class_type="mage")
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("focused", 60, clock)
    # spell_intensity_bonus with focused buff active
    bonus = c.spell_intensity_bonus("fire", clock)
    assert bonus == pytest.approx(0.1)


def test_focused_stacks_with_fire_intensity_modifier():
    c = Character(name="Mage", class_type="mage")
    c.modifiers["fire_intensity"] = 2  # 2 levels
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("focused", 60, clock)
    from server.config import MODIFIER_BONUS_PER_LEVEL
    base_bonus = 2 * MODIFIER_BONUS_PER_LEVEL
    bonus = c.spell_intensity_bonus("fire", clock)
    assert bonus == pytest.approx(base_bonus + 0.1)


def test_focused_no_bonus_when_expired():
    c = Character(name="Mage", class_type="mage")
    clock = make_clock(total_minutes=0)
    c.apply_food_buff("focused", 60, clock)
    clock.total_minutes = 200
    bonus = c.spell_intensity_bonus("fire", clock)
    assert bonus == pytest.approx(0.0)


def test_no_focused_spell_intensity_unchanged():
    c = Character(name="Mage", class_type="mage")
    clock = make_clock(total_minutes=0)
    assert c.spell_intensity_bonus("fire", clock) == pytest.approx(0.0)
