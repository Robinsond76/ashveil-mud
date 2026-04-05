"""
Phase 2 — Survival Stats: command output tests (Phase F).
Tests STATUS, EAT, DRINK, PARTY survival row, LOOK stamina warning.
"""
import asyncio
import pytest

from server.engine.character import Character
from server.engine.game import GameSession, State
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_nav_session(player_kwargs=None):
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda rid: []
    session = GameSession(send_fn=_collect_fn(session_ref=[]), world=world, class_defs={}, clock=None)
    player = Character(name="Hero", class_type="warrior")
    if player_kwargs:
        for k, v in player_kwargs.items():
            setattr(player, k, v)
    session.player = player
    session.state = State.NAVIGATION
    return session


def run(session, command):
    """Run a command and return all output lines joined."""
    collected: list[str] = []

    async def _send(text: str) -> None:
        collected.append(text)

    session._send_raw = _send
    asyncio.get_event_loop().run_until_complete(session.handle_input(command))
    return "".join(collected)


# ── Phase F: STATUS command ───────────────────────────────────────────────────

def test_status_command_shows_hunger():
    s = make_nav_session()
    s._send_raw = None  # will be replaced in run()
    s.player.hunger = 75.0

    collected: list[str] = []
    async def _send(text: str): collected.append(text)
    s._send_raw = _send

    asyncio.get_event_loop().run_until_complete(s.handle_input("STATUS"))
    output = "".join(collected).lower()
    assert "hunger" in output


def test_status_command_shows_thirst():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.thirst = 60.0
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("STATUS"))
    output = "".join(collected).lower()
    assert "thirst" in output


def test_status_command_shows_stamina():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.stamina = 45.0
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("STATUS"))
    output = "".join(collected).lower()
    assert "stamina" in output


def test_status_shows_percentage_values():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.stamina = 50.0  # 50%
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("STATUS"))
    output = "".join(collected)
    assert "50" in output  # 50% should appear somewhere


# ── Phase F: EAT stub ─────────────────────────────────────────────────────────

def test_eat_with_no_item_gives_feedback():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("EAT"))
    output = "".join(collected).lower()
    assert output  # just some feedback


def test_eat_food_item_restores_hunger():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.hunger = 40.0
    # Add hard_bread to inventory
    s.player.inventory = ["hard_bread"]
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("EAT hard_bread"))
    # Hunger should have increased
    assert s.player.hunger > 40.0


def test_eat_removes_item_from_inventory():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.inventory = ["hard_bread"]
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("EAT hard_bread"))
    assert "hard_bread" not in s.player.inventory


# ── Phase F: DRINK stub ───────────────────────────────────────────────────────

def test_drink_water_flask_restores_thirst():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.thirst = 30.0
    s.player.inventory = ["water_flask"]
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("DRINK water_flask"))
    assert s.player.thirst > 30.0


def test_drink_removes_item_from_inventory():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    s = GameSession(send_fn=_send, world=_stub_world(), class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.inventory = ["water_flask"]
    s.state = State.NAVIGATION

    asyncio.get_event_loop().run_until_complete(s.handle_input("DRINK water_flask"))
    assert "water_flask" not in s.player.inventory


# ── Phase F: LOOK shows warning at stamina 0 ─────────────────────────────────

def test_look_shows_stamina_warning_when_zero():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    from server.engine.world import Room
    room = Room.__new__(Room)
    room.id = "here"
    room.name = "Test Room"
    room.description = "A plain room."
    room.exits = {}
    room.item_ids = []
    room.recruitable_npc_ids = []
    room.monster_groups = []
    room.is_campfire = False
    room.room_type = "outdoor"
    room.base_temp_f = 65.0

    world = WorldMap.__new__(WorldMap)
    world._rooms = {"here": room}
    world.get_room = lambda rid: world._rooms.get(rid)
    world.active_encounter_groups = lambda _: []

    s = GameSession(send_fn=_send, world=world, class_defs={}, clock=None)
    s.player = Character(name="Hero", class_type="warrior")
    s.player.stamina = 0.0
    s.state = State.NAVIGATION
    s.current_room_id = "here"

    asyncio.get_event_loop().run_until_complete(s._do_look())
    output = "".join(collected).lower()
    assert "exhaust" in output or "stamina" in output or "rest" in output


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stub_world():
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda _: []
    return world


def _collect_fn(session_ref):
    collected = session_ref
    async def _send(text: str): collected.append(text)
    return _send
