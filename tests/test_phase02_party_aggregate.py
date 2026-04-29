"""
Phase 2 — Survival Stats: GameSession party aggregate + penalty tests (Phase B).
Tests for _party_survival_aggregate() and _apply_survival_penalties().
"""
import asyncio
import pytest

from server.engine.domain.character import Character
from server.engine.game import GameSession, State
from server.engine.world.map import WorldMap
from server.engine.domain.npc import NPC
from server.engine.systems.survival import party_survival_aggregate, apply_survival_penalties


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _noop(text: str) -> None:
    pass


def make_session():
    """Minimal GameSession with a player but no clock/world needed for aggregate tests."""
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    session = GameSession(send_fn=_noop, world=world, class_defs={}, clock=None)
    player = Character(name="Hero", class_type="warrior")
    session.player = player
    session.state = State.NAVIGATION
    return session


def make_npc(name="Companion", hunger=100.0, thirst=100.0, stamina=100.0):
    npc = NPC.__new__(NPC)
    npc.name = name
    npc.hunger = hunger
    npc.max_hunger = 100.0
    npc.thirst = thirst
    npc.max_thirst = 100.0
    npc.stamina = stamina
    npc.max_stamina = 100.0
    npc.class_type = "warrior"
    npc.hp = 30
    npc.max_hp = 30
    return npc


# ── Phase B: _party_survival_aggregate ───────────────────────────────────────

def test_aggregate_solo_all_full():
    s = make_session()
    g, t, st = party_survival_aggregate(s.player, s.party)
    assert g == 1.0
    assert t == 1.0
    assert st == 1.0


def test_aggregate_solo_half_hunger():
    s = make_session()
    s.player.hunger = 50.0
    g, t, st = party_survival_aggregate(s.player, s.party)
    assert abs(g - 0.5) < 1e-9


def test_aggregate_with_npc_pools_correctly():
    s = make_session()
    s.player.hunger = 35.0   # 35/100
    npc = make_npc(hunger=70.0)  # 70/100
    s.party = [npc]
    # pool: 105/200 = 0.525
    g, t, st = party_survival_aggregate(s.player, s.party)
    assert abs(g - (35 + 70) / (100 + 100)) < 1e-9


def test_aggregate_npc_leaves_recalculates():
    s = make_session()
    s.player.hunger = 50.0
    npc = make_npc(hunger=100.0)
    s.party = [npc]
    # with npc: 150/200 = 0.75
    g1, _, _ = party_survival_aggregate(s.player, s.party)
    assert abs(g1 - 0.75) < 1e-9
    # npc leaves
    s.party = []
    g2, _, _ = party_survival_aggregate(s.player, s.party)
    assert abs(g2 - 0.5) < 1e-9


# ── Phase B: _apply_survival_penalties ───────────────────────────────────────

def test_no_penalties_when_all_full():
    s = make_session()
    mult, blocked = apply_survival_penalties(s.player, s.party)
    assert mult == 1.0
    assert blocked is False


def test_stamina_10_to_30_pct_gives_0_85_multiplier():
    s = make_session()
    s.player.stamina = 20.0   # 20% — in the 10–30% band
    mult, blocked = apply_survival_penalties(s.player, s.party)
    assert abs(mult - 0.85) < 1e-9
    assert blocked is False


def test_stamina_below_10_pct_blocks_movement():
    s = make_session()
    s.player.stamina = 5.0    # 5%
    mult, blocked = apply_survival_penalties(s.player, s.party)
    assert blocked is True


def test_hunger_thirst_20_to_40_gives_0_9_multiplier():
    s = make_session()
    s.player.hunger = 30.0   # 30% — in the 20–40% band
    s.player.thirst = 30.0
    mult, blocked = apply_survival_penalties(s.player, s.party)
    assert abs(mult - 0.9) < 1e-9


def test_hunger_thirst_below_20_gives_0_75_multiplier():
    s = make_session()
    s.player.hunger = 10.0   # 10% — below 20%
    s.player.thirst = 10.0
    mult, blocked = apply_survival_penalties(s.player, s.party)
    assert abs(mult - 0.75) < 1e-9


def test_both_penalties_stack_multiplicatively():
    s = make_session()
    s.player.stamina = 20.0  # 20% → 0.85×
    s.player.hunger  = 30.0  # 30% → 0.90×
    s.player.thirst  = 30.0
    mult, blocked = apply_survival_penalties(s.player, s.party)
    # 0.85 × 0.90 = 0.765
    assert abs(mult - 0.85 * 0.90) < 1e-9
