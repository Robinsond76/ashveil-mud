"""
Phase 4 — Food & Consumables: items, EAT/DRINK commands, and BUFFS command.
Tests:
  Phase C — Item registry
    - All 9 Phase-4 food items are loadable from registry
    - Buff items have correct effect_params fields
  Phase D — EAT / DRINK commands
    - EAT restores hunger (buff food item)
    - EAT restores thirst (if item has thirst param)
    - EAT applies buff to all party members
    - EAT removes item from carrying character's inventory
    - EAT with no matching item → error message
    - EAT when item is not food → error message
    - DRINK restores thirst; EAT handles drink items too (waterskin via EAT)
    - Hunger/thirst capped at max
  Phase E — BUFFS command
    - BUFFS shows active buff name and remaining time
    - BUFFS shows "No active buffs." when none
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from server.engine.character import Character
from server.engine.game import GameSession, State
from server.engine.domain.items import get_item
from server.engine.npc import NPC
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_clock(total_minutes: int = 0):
    clock = MagicMock()
    clock.total_minutes = total_minutes
    return clock


def make_nav_session(clock=None):
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda rid: []
    collected: list[str] = []

    async def _send(text: str) -> None:
        collected.append(text)

    session = GameSession(send_fn=_send, world=world, class_defs={}, clock=clock)
    player = Character(name="Hero", class_type="warrior")
    session.player = player
    session.state = State.NAVIGATION
    return session


def run(session, command: str) -> str:
    collected: list[str] = []

    async def _send(text: str) -> None:
        collected.append(text)

    session._send_raw = _send
    asyncio.get_event_loop().run_until_complete(session.handle_input(command))
    return "".join(collected)


# ── Phase C: Item registry ─────────────────────────────────────────────────────

PHASE4_FOOD_ITEMS = [
    "hard_bread",
    "dried_meat",
    "ration_pack",
    "waterskin",
    "hearty_stew",
    "forest_berries",
    "adventure_bread",
    "mountain_tea",
    "warrior_chow",
]


@pytest.mark.parametrize("item_id", PHASE4_FOOD_ITEMS)
def test_phase4_food_item_exists_in_registry(item_id):
    item = get_item(item_id)
    assert item is not None, f"Item '{item_id}' not found in registry"


def test_hearty_stew_is_food_type():
    item = get_item("hearty_stew")
    assert item.effect_type == "food"


def test_hearty_stew_has_correct_hunger():
    item = get_item("hearty_stew")
    assert item.effect_params["hunger"] == 70


def test_hearty_stew_has_correct_thirst():
    item = get_item("hearty_stew")
    assert item.effect_params["thirst"] == 30


def test_hearty_stew_has_fortified_buff():
    item = get_item("hearty_stew")
    assert item.effect_params["buff"] == "fortified"
    assert item.effect_params["buff_duration"] == 120


def test_forest_berries_has_alertness_buff():
    item = get_item("forest_berries")
    assert item.effect_params.get("buff") == "alertness"
    assert item.effect_params.get("buff_duration") == 60


def test_adventure_bread_has_satiated_buff():
    item = get_item("adventure_bread")
    assert item.effect_params.get("buff") == "satiated"
    assert item.effect_params.get("buff_duration") == 180


def test_mountain_tea_has_focused_buff():
    item = get_item("mountain_tea")
    assert item.effect_params.get("buff") == "focused"
    assert item.effect_params.get("buff_duration") == 60


def test_warrior_chow_has_energised_buff():
    item = get_item("warrior_chow")
    assert item.effect_params.get("buff") == "energised"
    assert item.effect_params.get("buff_duration") == 90


def test_hard_bread_has_no_buff():
    item = get_item("hard_bread")
    assert "buff" not in item.effect_params or item.effect_params.get("buff") is None


def test_ration_pack_restores_both_hunger_and_thirst():
    item = get_item("ration_pack")
    assert item.effect_params.get("hunger", 0) > 0
    assert item.effect_params.get("thirst", 0) > 0


def test_waterskin_restores_thirst():
    item = get_item("waterskin")
    assert item.effect_params.get("thirst", 0) > 0


# ── Phase D: EAT command ──────────────────────────────────────────────────────

def test_eat_restores_hunger_on_player():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hard_bread"]
    session.player.hunger = 50.0
    run(session, "EAT hard bread")
    item = get_item("hard_bread")
    expected = 50.0 + item.effect_params["hunger"]
    assert session.player.hunger == pytest.approx(expected)


def test_eat_removes_item_from_inventory():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hard_bread"]
    run(session, "EAT hard bread")
    assert "hard_bread" not in session.player.inventory


def test_eat_caps_hunger_at_max():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hearty_stew"]
    session.player.hunger = 90.0
    session.player.max_hunger = 100.0
    run(session, "EAT hearty stew")
    assert session.player.hunger == pytest.approx(100.0)


def test_eat_restores_thirst_on_buff_food():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hearty_stew"]
    session.player.thirst = 50.0
    run(session, "EAT hearty stew")
    assert session.player.thirst > 50.0


def test_eat_applies_buff_to_player():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hearty_stew"]
    run(session, "EAT hearty stew")
    assert "fortified" in session.player.active_buffs


def test_eat_applies_buff_to_all_party_members():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hearty_stew"]
    npc = NPC(name="Ally", class_type="warrior")
    session.party = [npc]
    run(session, "EAT hearty stew")
    assert "fortified" in session.player.active_buffs
    assert "fortified" in npc.active_buffs


def test_eat_no_buff_food_no_buff_applied():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["hard_bread"]
    run(session, "EAT hard bread")
    assert session.player.active_buffs == {}


def test_eat_item_not_in_inventory():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    output = run(session, "EAT hard bread")
    assert "don't have" in output.lower() or "no" in output.lower()


def test_eat_non_food_item_rejected():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["health_potion"]
    output = run(session, "EAT health potion")
    assert "can't eat" in output.lower() or "not food" in output.lower()


def test_eat_no_args_shows_usage():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    output = run(session, "EAT")
    assert "eat" in output.lower()


def test_eat_finds_item_in_party_member_inventory():
    """EAT searches party member inventories, not just the player's."""
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    npc = NPC(name="Ally", class_type="warrior")
    npc.inventory = ["hard_bread"]
    session.party = [npc]
    output = run(session, "EAT hard bread")
    assert "don't have" not in output.lower()
    assert "hard_bread" not in npc.inventory


# ── Phase D: DRINK command ────────────────────────────────────────────────────

def test_drink_restores_thirst():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["waterskin"]
    session.player.thirst = 20.0
    run(session, "DRINK waterskin")
    item = get_item("waterskin")
    expected = 20.0 + item.effect_params["thirst"]
    assert session.player.thirst == pytest.approx(expected)


def test_drink_mountain_tea_applies_focused_buff():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.inventory = ["mountain_tea"]
    run(session, "DRINK mountain tea")
    assert "focused" in session.player.active_buffs


def test_drink_item_not_in_inventory():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    output = run(session, "DRINK waterskin")
    assert "don't have" in output.lower() or "no" in output.lower()


# ── Phase E: BUFFS command ────────────────────────────────────────────────────

def test_buffs_command_shows_active_buff():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.apply_food_buff("fortified", 120, clock)
    output = run(session, "BUFFS")
    assert "fortified" in output.lower()


def test_buffs_command_shows_remaining_time():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.apply_food_buff("fortified", 120, clock)
    clock.total_minutes = 20  # 100 minutes remaining
    output = run(session, "BUFFS")
    assert "100" in output


def test_buffs_command_shows_no_buffs_when_empty():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    output = run(session, "BUFFS")
    assert "no active buffs" in output.lower()


def test_buffs_excludes_expired_buff():
    clock = make_clock(0)
    session = make_nav_session(clock=clock)
    session.player.apply_food_buff("alertness", 60, clock)
    clock.total_minutes = 200
    output = run(session, "BUFFS")
    assert "no active buffs" in output.lower()
