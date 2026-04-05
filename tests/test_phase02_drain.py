"""
Phase 2 — Survival Stats: drain tick + movement stamina drain tests (Phase C).
"""
import pytest

from server.engine.character import Character
from server.engine.game import GameSession, State
from server.engine.world import WorldMap
from server.engine.npc import NPC


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _noop(text: str) -> None:
    pass


def make_session_with_player():
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    session = GameSession(send_fn=_noop, world=world, class_defs={}, clock=None)
    session.player = Character(name="Hero", class_type="warrior")
    session.state = State.NAVIGATION
    return session


# ── Phase C: _drain_survival_tick ─────────────────────────────────────────────

def test_drain_tick_reduces_hunger():
    s = make_session_with_player()
    initial = s.player.hunger
    s._drain_survival_tick("Comfortable")
    assert s.player.hunger < initial


def test_drain_tick_reduces_thirst_comfortable():
    s = make_session_with_player()
    initial = s.player.thirst
    s._drain_survival_tick("Comfortable")
    assert s.player.thirst < initial


def test_drain_tick_hot_drains_thirst_faster_than_comfortable():
    s = make_session_with_player()
    s2 = make_session_with_player()
    s._drain_survival_tick("Hot")
    s2._drain_survival_tick("Comfortable")
    # Hot should drain more thirst
    assert s.player.thirst < s2.player.thirst


def test_drain_tick_scorching_drains_thirst_2x():
    s = make_session_with_player()
    s_base = make_session_with_player()
    s._drain_survival_tick("Scorching")
    s_base._drain_survival_tick("Comfortable")
    base_drain = 100.0 - s_base.player.thirst
    scorch_drain = 100.0 - s.player.thirst
    assert abs(scorch_drain - base_drain * 2.0) < 1e-6


def test_drain_tick_does_not_drain_below_zero():
    s = make_session_with_player()
    s.player.hunger = 0.0
    s.player.thirst = 0.0
    s._drain_survival_tick("Scorching")
    assert s.player.hunger >= 0.0
    assert s.player.thirst >= 0.0


def test_drain_tick_affects_all_party_members():
    s = make_session_with_player()
    npc = NPC.__new__(NPC)
    npc.name = "Ally"
    npc.hunger  = 100.0; npc.max_hunger  = 100.0
    npc.thirst  = 100.0; npc.max_thirst  = 100.0
    npc.stamina = 100.0; npc.max_stamina = 100.0
    npc.class_type = "warrior"
    npc.hp = 30; npc.max_hp = 30
    s.party = [npc]
    s._drain_survival_tick("Comfortable")
    assert npc.hunger < 100.0
    assert npc.thirst < 100.0


# ── Phase C: stamina drain from movement ─────────────────────────────────────

def test_move_drains_party_stamina():
    """After a successful move, all party members lose 2 stamina."""
    import asyncio
    from unittest.mock import MagicMock, AsyncMock

    # Build a minimal world with one room that has an exit
    from server.engine.world import Room
    room = Room.__new__(Room)
    room.id = "start"
    room.name = "Start Room"
    room.description = ""
    room.exits = {"north": "end"}
    room.item_ids = []
    room.recruitable_npc_ids = []
    room.monster_groups = []
    room.is_campfire = False
    room.room_type = "outdoor"
    room.base_temp_f = 65.0

    dest = Room.__new__(Room)
    dest.id = "end"
    dest.name = "End Room"
    dest.description = ""
    dest.exits = {}
    dest.item_ids = []
    dest.recruitable_npc_ids = []
    dest.monster_groups = []
    dest.is_campfire = False
    dest.room_type = "outdoor"
    dest.base_temp_f = 65.0

    world = WorldMap.__new__(WorldMap)
    world._rooms = {"start": room, "end": dest}
    world.get_room = lambda rid: world._rooms.get(rid)
    world.active_encounter_groups = lambda _: []

    sent = []
    async def send_fn(text):
        sent.append(text)

    session = GameSession(send_fn=send_fn, world=world, class_defs={}, clock=None)
    session.player = Character(name="Hero", class_type="warrior")
    session.state = State.NAVIGATION
    session.current_room_id = "start"

    initial_stamina = session.player.stamina
    asyncio.get_event_loop().run_until_complete(session._do_move("north"))
    assert session.player.stamina == initial_stamina - 2.0


def test_move_blocked_when_stamina_zero():
    """At stamina=0, movement should be refused."""
    import asyncio
    from server.engine.world import Room

    room = Room.__new__(Room)
    room.id = "start"
    room.name = "Start Room"
    room.description = ""
    room.exits = {"north": "end"}
    room.item_ids = []
    room.recruitable_npc_ids = []
    room.monster_groups = []
    room.is_campfire = False
    room.room_type = "outdoor"
    room.base_temp_f = 65.0

    world = WorldMap.__new__(WorldMap)
    world._rooms = {"start": room}
    world.get_room = lambda rid: world._rooms.get(rid)
    world.active_encounter_groups = lambda _: []

    sent = []
    async def send_fn(text):
        sent.append(text)

    session = GameSession(send_fn=send_fn, world=world, class_defs={}, clock=None)
    session.player = Character(name="Hero", class_type="warrior")
    session.player.stamina = 0.0
    session.state = State.NAVIGATION
    session.current_room_id = "start"

    asyncio.get_event_loop().run_until_complete(session._do_move("north"))
    # Player should still be in start room
    assert session.current_room_id == "start"
    # Should have gotten a warning
    assert any("stamina" in m.lower() or "exhausted" in m.lower() or "rest" in m.lower()
               for m in sent)
