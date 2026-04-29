"""
Improvement 04 — Async Safety Tests

Tests for:
  - Concurrent room enter/leave safety (asyncio.Lock on room_occupants)
  - WorldClock periodic respawn ticking
  - Light source persistence through Character serialization
"""
import asyncio
import pytest
import pytest_asyncio


# ── Task 1: Concurrent room occupants ────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_room_enter_does_not_corrupt(load_game_data):
    """Two players entering the same room concurrently should both appear."""
    from server.engine.world import WorldMap
    world = WorldMap()
    world.room_occupants["town_square"] = []

    async def enter(name):
        await world.enter_room(name, "town_square")

    await asyncio.gather(enter("Alice"), enter("Bob"))
    occupants = await world.players_in_room("town_square")
    assert "Alice" in occupants
    assert "Bob" in occupants
    assert len(occupants) == 2


@pytest.mark.asyncio
async def test_concurrent_leave_does_not_corrupt(load_game_data):
    """Two players leaving the same room concurrently should both be removed."""
    from server.engine.world import WorldMap
    world = WorldMap()
    world.room_occupants["town_square"] = ["Alice", "Bob"]

    async def leave(name):
        await world.leave_room(name, "town_square")

    await asyncio.gather(leave("Alice"), leave("Bob"))
    occupants = await world.players_in_room("town_square")
    assert len(occupants) == 0


# ── Task 2: WorldClock ticks respawns ────────────────────────────────────────

def test_world_clock_ticks_respawns(load_game_data):
    """WorldClock should call world.tick_respawns() on each game-minute tick."""
    from server.engine.world import WorldMap, Room, EncounterGroup
    from server.engine.world_clock import WorldClock

    world = WorldMap()
    # Add a room with a defeated encounter group
    room = Room(
        id="test_room",
        name="Test Room",
        description="A test room.",
        exits={},
        item_ids=[],
        encounter_groups=[
            EncounterGroup(
                group="test_group",
                members=[],
                respawn_ticks=3,
                label="Test Group",
                defeated=True,
                respawn_countdown=2,
            )
        ],
        recruitable_npc_ids=[],
    )
    world._rooms["test_room"] = room

    clock = WorldClock(world=world)

    # Simulate one respawn tick via _advance_one_minute
    clock._advance_one_minute()
    assert room.encounter_groups[0].respawn_countdown == 1

    clock._advance_one_minute()
    assert room.encounter_groups[0].respawn_countdown == 0
    assert room.encounter_groups[0].defeated is False  # respawned


def test_world_clock_without_world_still_works(load_game_data):
    """WorldClock without a world parameter should not error."""
    from server.engine.world_clock import WorldClock
    clock = WorldClock()
    # Should not raise even though no world is attached
    clock._advance_one_minute()


# ── Task 3: Light source persistence ─────────────────────────────────────────

def test_lit_sources_defaults_empty(load_game_data):
    """lit_sources should default to empty dict on a new Character."""
    from server.engine.domain.character import Character
    c = Character(name="test", class_type="warrior")
    assert c.lit_sources == {}


def test_lit_sources_persist_in_to_dict(load_game_data):
    """lit_sources should be included in Character.to_dict()."""
    from server.engine.domain.character import Character
    c = Character(name="test", class_type="warrior")
    c.lit_sources = {"torch_1": 500}
    d = c.to_dict()
    assert d["lit_sources"] == {"torch_1": 500}


def test_lit_sources_restored_from_dict(load_game_data):
    """lit_sources should be restored from Character.from_dict()."""
    from server.engine.domain.character import Character
    c = Character(name="test", class_type="warrior")
    c.lit_sources = {"torch_1": 500}
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.lit_sources == {"torch_1": 500}


def test_lit_sources_defaults_empty_in_from_dict(load_game_data):
    """from_dict without lit_sources key should default to empty dict."""
    from server.engine.domain.character import Character
    c = Character(name="test", class_type="warrior")
    d = c.to_dict()
    del d["lit_sources"]
    c2 = Character.from_dict(d)
    assert c2.lit_sources == {}
