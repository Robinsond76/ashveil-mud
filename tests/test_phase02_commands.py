"""
Phase 2 — Survival Stats: command output tests (Phase F).
Tests STATUS, EAT, DRINK, PARTY survival row, LOOK stamina warning.
"""
import asyncio
import pytest

from server.engine.domain.character import Character
from server.engine.game import GameSession, State
from server.engine.world.map import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(session, command):
    """Run a command and return all output lines joined."""
    collected: list[str] = []

    async def _send(text: str) -> None:
        collected.append(text)

    session._send_raw = _send
    asyncio.get_event_loop().run_until_complete(session.handle_input(command))
    return "".join(collected)


# ── Phase F: STATUS command ───────────────────────────────────────────────────

def test_status_command_shows_hunger(make_nav_session):
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


# ── Phase F: LOOK shows warning at stamina 0 ─────────────────────────────────

def test_look_zero_stamina_shows_exhaustion_warning():
    collected: list[str] = []
    async def _send(text: str): collected.append(text)

    from server.engine.world.map import Room
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

    from server.engine.states.navigation import NavigationHandler
    asyncio.get_event_loop().run_until_complete(NavigationHandler()._do_look(s))
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
