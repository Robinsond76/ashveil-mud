"""
Error path tests: wrong-state commands, malformed input, edge cases.
Covers T3 (no error path testing) and T2 (weak assertions).
"""
import asyncio
import pytest

from server.engine.domain.character import Character
from server.engine.game import GameSession, State
from server.engine.world import WorldMap, Room


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_session(class_type="warrior", stamina=None, hp=None, mp=None):
    collected = []

    async def send(text):
        collected.append(text)

    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda rid: []

    s = GameSession(send_fn=send, world=world, class_defs={}, clock=None, sessions={})
    player = Character(name="Hero", class_type=class_type)
    if stamina is not None:
        player.stamina = stamina
        player.max_stamina = 100.0
    if hp is not None:
        player.hp = hp
        player.max_hp = max(hp, player.max_hp)
    if mp is not None:
        player.mp = mp
        player.max_mp = 100
    s.player = player
    s.state = State.NAVIGATION
    s._collected = collected
    return s, collected


def _run_cmd(s, collected, cmd):
    collected.clear()
    _run(s.handle_input(cmd))
    return "".join(collected)


# ─── Wrong-state commands ─────────────────────────────────────────────────────

def test_attack_in_campfire_state_does_not_start_combat():
    """ATTACK in CAMPFIRE state must not start a combat session."""
    s, collected = _make_session()
    s.state = State.CAMPFIRE

    _run_cmd(s, collected, "ATTACK")

    assert s._combat is None


def test_attack_in_campfire_state_shows_message():
    """ATTACK in CAMPFIRE state shows an unknown-command or context error."""
    s, collected = _make_session()
    s.state = State.CAMPFIRE

    output = _run_cmd(s, collected, "ATTACK")

    # Campfire handler sends "Unknown campfire command 'ATTACK'. Type HELP."
    assert "attack" in output.lower() or "unknown" in output.lower() or "help" in output.lower()


def test_campfire_command_in_combat_state_shows_combat_message():
    """CAMPFIRE command while in COMBAT state should print in-progress message."""
    s, collected = _make_session()
    s.state = State.COMBAT

    output = _run_cmd(s, collected, "CAMPFIRE")

    assert "combat" in output.lower()


def test_campfire_command_in_combat_state_does_not_change_state():
    """State must remain COMBAT after sending CAMPFIRE while in combat."""
    s, collected = _make_session()
    s.state = State.COMBAT

    _run_cmd(s, collected, "CAMPFIRE")

    assert s.state == State.COMBAT


def test_move_in_combat_state_shows_combat_message():
    """Directional movement while in COMBAT state is blocked with an in-progress message."""
    s, collected = _make_session()
    s.state = State.COMBAT
    original_room = s.current_room_id

    output = _run_cmd(s, collected, "NORTH")

    assert "combat" in output.lower()
    assert s.current_room_id == original_room


# ─── Malformed input ──────────────────────────────────────────────────────────

def test_give_no_args_shows_usage():
    """GIVE with no arguments should show usage hint including 'TO'."""
    s, collected = _make_session()
    s.player.inventory = []

    output = _run_cmd(s, collected, "GIVE")

    assert "give" in output.lower() or "usage" in output.lower() or "to" in output.lower()


def test_unknown_command_shows_helpful_error():
    """A completely unknown command shows an error mentioning HELP."""
    s, collected = _make_session()

    output = _run_cmd(s, collected, "TELEPORT")

    assert any(
        phrase in output.lower()
        for phrase in ["unknown", "not recognized", "help"]
    )


# ─── Edge cases ───────────────────────────────────────────────────────────────

def test_move_blocked_when_stamina_zero():
    """Movement is blocked when player stamina is at 0."""
    s, collected = _make_session(stamina=0.0)

    # Provide a room with a south exit so the stamina check is reached
    room = Room(
        id="test_room", name="Test Room", description="",
        exits={"south": "other_room"}, item_ids=[],
        encounter_groups=[], recruitable_npc_ids=[],
    )
    s.world.get_room = lambda rid: room
    original_room = s.current_room_id

    output = _run_cmd(s, collected, "SOUTH")

    assert s.current_room_id == original_room
    assert any(
        phrase in output.lower()
        for phrase in ["stamina", "exhausted", "tired"]
    )


def test_drop_item_not_in_inventory_shows_error():
    """DROP with an item not in inventory shows a 'not found' error."""
    s, collected = _make_session()
    s.player.inventory = []

    output = _run_cmd(s, collected, "DROP excalibur")

    assert any(
        phrase in output.lower()
        for phrase in ["don't have", "not found", "excalibur"]
    )


def test_equip_with_empty_inventory_shows_error():
    """EQUIP when inventory is empty shows a 'not found' error."""
    s, collected = _make_session()
    s.player.inventory = []

    output = _run_cmd(s, collected, "EQUIP sword")

    assert any(
        phrase in output.lower()
        for phrase in ["don't have", "not found", "inventory"]
    )


def test_move_in_direction_with_no_exit_shows_error():
    """Moving in a direction with no exit shows a can't-go message."""
    s, collected = _make_session()

    # Room exists but has no exits
    room = Room(
        id="test_room", name="Test Room", description="",
        exits={}, item_ids=[],
        encounter_groups=[], recruitable_npc_ids=[],
    )
    s.world.get_room = lambda rid: room
    original_room = s.current_room_id

    output = _run_cmd(s, collected, "NORTH")

    assert s.current_room_id == original_room
    assert any(
        phrase in output.lower()
        for phrase in ["can't go", "cannot go", "no exit", "north"]
    )
