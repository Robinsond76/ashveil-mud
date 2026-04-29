"""
Phase 2 — Survival Stats: recovery tests (Phase E).
Tests for REST restoring stamina, SIT passive recovery, STAND stopping it.
"""
import pytest
import asyncio

from server.engine.domain.character import Character
from server.engine.game import GameSession, State
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

sent_messages: list[str] = []


async def capture_send(text: str) -> None:
    sent_messages.append(text)


def make_campfire_session():
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    session = GameSession(send_fn=capture_send, world=world, class_defs={}, clock=None)
    player = Character(name="Hero", class_type="warrior")
    player.hp = 1
    player.mp = 1
    player.stamina = 30.0
    player.hunger = 40.0
    player.thirst = 40.0
    session.player = player
    session.state = State.CAMPFIRE
    return session


# ── Phase E: REST restores stamina ───────────────────────────────────────────

def test_rest_restores_player_stamina_to_max():
    sent_messages.clear()
    s = make_campfire_session()
    s.player.stamina = 30.0
    asyncio.get_event_loop().run_until_complete(s._handle_campfire("REST"))
    assert s.player.stamina == s.player.max_stamina


def test_rest_restores_npc_stamina_to_max():
    from server.engine.domain.npc import NPC
    sent_messages.clear()
    s = make_campfire_session()
    npc = NPC(name="Ally", class_type="warrior")
    npc.hp = 1
    npc.stamina = 10.0
    s.party = [npc]
    asyncio.get_event_loop().run_until_complete(s._handle_campfire("REST"))
    assert npc.stamina == npc.max_stamina


def test_rest_also_restores_hp_mp():
    sent_messages.clear()
    s = make_campfire_session()
    s.player.hp = 1
    s.player.mp = 1
    asyncio.get_event_loop().run_until_complete(s._handle_campfire("REST"))
    assert s.player.hp == s.player.max_hp
    assert s.player.mp == s.player.max_mp


# ── Phase E: SIT flag and passive stamina recovery ───────────────────────────

def test_sit_command_sets_sitting_flag():
    sent_messages.clear()
    s = make_campfire_session()
    s.state = State.NAVIGATION
    asyncio.get_event_loop().run_until_complete(s.handle_input("SIT"))
    assert s._sitting is True


def test_stand_command_clears_sitting_flag():
    sent_messages.clear()
    s = make_campfire_session()
    s.state = State.NAVIGATION
    s._sitting = True
    asyncio.get_event_loop().run_until_complete(s.handle_input("STAND"))
    assert s._sitting is False


def test_sitting_tick_recovers_stamina():
    """_sitting_stamina_tick() should add +1 stamina to each party member."""
    s = make_campfire_session()
    s.state = State.NAVIGATION
    s._sitting = True
    s.player.stamina = 50.0
    s._sitting_stamina_tick()
    assert s.player.stamina == 51.0


def test_sitting_tick_caps_at_max_stamina():
    s = make_campfire_session()
    s.state = State.NAVIGATION
    s._sitting = True
    s.player.stamina = 100.0
    s._sitting_stamina_tick()
    assert s.player.stamina == 100.0


def test_sitting_tick_affects_npc_too():
    from server.engine.domain.npc import NPC
    s = make_campfire_session()
    s.state = State.NAVIGATION
    s._sitting = True
    npc = NPC.__new__(NPC)
    npc.name = "Ally"
    npc.stamina = 80.0; npc.max_stamina = 100.0
    npc.hp = 30; npc.max_hp = 30
    s.party = [npc]
    s._sitting_stamina_tick()
    assert npc.stamina == 81.0


def test_sitting_tick_does_not_run_when_not_sitting():
    s = make_campfire_session()
    s.state = State.NAVIGATION
    s._sitting = False
    s.player.stamina = 50.0
    s._sitting_stamina_tick()
    assert s.player.stamina == 50.0
