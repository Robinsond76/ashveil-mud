"""
Phase 3 — Utility Skills & Mana Rework: mana rework tests (Phase A).
Tests:
  - REST (campfire) fully restores MP for player and party NPCs
  - No passive MP regeneration occurs during out-of-combat world-clock ticks
"""
import asyncio
import pytest

from server.engine.character import Character
from server.engine.game import GameSession, State
from server.engine.npc import NPC
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_campfire_session():
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    collected: list[str] = []

    async def _send(text: str) -> None:
        collected.append(text)

    session = GameSession(send_fn=_send, world=world, class_defs={}, clock=None)
    player = Character(name="Gandalf", class_type="mage")
    player.hp = 1
    player.mp = 0
    player.max_mp = 40
    player.stamina = 10.0
    session.player = player
    session.state = State.CAMPFIRE
    return session


# ── Phase A: REST restores MP ─────────────────────────────────────────────────

def test_rest_restores_player_mp_to_max():
    """REST at campfire must fully restore player MP."""
    s = make_campfire_session()
    s.player.mp = 0
    s.player.max_mp = 40
    asyncio.get_event_loop().run_until_complete(s._handle_campfire("REST"))
    assert s.player.mp == 40


def test_rest_restores_npc_party_mp_to_max():
    """REST at campfire must fully restore all party NPC MP."""
    s = make_campfire_session()
    npc = NPC(name="Ariel", class_type="cleric")
    npc.mp = 0
    npc.max_mp = 30
    s.party = [npc]
    asyncio.get_event_loop().run_until_complete(s._handle_campfire("REST"))
    assert npc.mp == 30


def test_rest_restores_multiple_party_npcs_mp():
    """REST restores MP for every NPC in the party."""
    s = make_campfire_session()
    npcs = []
    for i in range(3):
        n = NPC(name=f"NPC{i}", class_type="warrior")
        n.mp = 0
        n.max_mp = 20
        npcs.append(n)
    s.party = npcs
    asyncio.get_event_loop().run_until_complete(s._handle_campfire("REST"))
    for n in npcs:
        assert n.mp == 20


# ── Phase A: No passive MP regen out of combat ────────────────────────────────

def test_slow_mp_regen_during_sitting_tick():
    """MP increases slowly during the passive sitting stamina tick."""
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None

    async def _send(text: str) -> None:
        pass

    session = GameSession(send_fn=_send, world=world, class_defs={}, clock=None)
    player = Character(name="Mage", class_type="mage")
    player.mp = 5
    player.max_mp = 40
    session.player = player
    session._sitting = True
    session.state = State.NAVIGATION

    # Call the tick directly
    session._sitting_stamina_tick()
    assert player.mp == 5.3  # MP recovers at 0.3 per tick while sitting


def test_no_passive_mp_regen_on_drain_tick():
    """MP must NOT increase during the survival drain tick."""
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None

    async def _send(text: str) -> None:
        pass

    session = GameSession(send_fn=_send, world=world, class_defs={}, clock=None)
    player = Character(name="Mage", class_type="mage")
    player.mp = 5
    player.max_mp = 40
    session.player = player
    session.state = State.NAVIGATION

    session._drain_survival_tick("Comfortable")
    assert player.mp == 5  # unchanged
