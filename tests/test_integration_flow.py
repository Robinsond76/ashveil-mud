"""
Full game flow integration test: CONNECT → CREATE → NAVIGATE → LOOK → STATUS → SAVE.
Covers T12 (no integration test) and exercises the complete character creation wizard.
"""
import asyncio
import json
import os
import pytest

from server.engine.game import GameSession, State
from server.engine.world import WorldMap

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "server", "data")

# Use unique alphabetic names (2-20 letters, no digits)
_HERO_NAME = "IntegHeroAlpha"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_world():
    world = WorldMap()
    world.load(DATA_DIR)
    return world


def _load_class_defs():
    with open(os.path.join(DATA_DIR, "classes", "classes.json")) as f:
        return json.load(f)


# ─── Full flow test ───────────────────────────────────────────────────────────

def test_full_creation_flow_reaches_navigation(load_game_data):
    """CONNECT → name → class → suggest stats → done → done → State.NAVIGATION."""
    collected = []

    async def send(text):
        collected.append(text)

    session = GameSession(
        send_fn=send,
        world=_make_world(),
        class_defs=_load_class_defs(),
        clock=None,
        sessions={},
    )

    # Step 1: start (CONNECT state, prompt for name)
    _run(session.start())
    assert session.state == State.CONNECT
    assert any("name" in t.lower() for t in collected)

    # Step 2: enter name → goes to CREATION
    collected.clear()
    _run(session.handle_input(_HERO_NAME))
    assert session.state == State.CREATION

    # Step 3: choose class
    collected.clear()
    _run(session.handle_input("warrior"))
    assert session.state == State.CREATION

    # Step 4: apply suggested stats
    collected.clear()
    _run(session.handle_input("SUGGEST"))

    # Step 5: confirm stats → enters STRATEGY editor
    collected.clear()
    _run(session.handle_input("DONE"))
    assert session.state == State.STRATEGY

    # Step 6: exit strategy wizard → enters world (NAVIGATION)
    collected.clear()
    _run(session.handle_input("DONE"))
    assert session.state == State.NAVIGATION


def test_full_flow_player_is_warrior(load_game_data):
    """After creation, player character is a warrior."""
    collected = []

    async def send(text):
        collected.append(text)

    session = GameSession(
        send_fn=send,
        world=_make_world(),
        class_defs=_load_class_defs(),
        clock=None,
        sessions={},
    )

    _run(session.start())
    _run(session.handle_input("IntegHeroBeta"))
    _run(session.handle_input("warrior"))
    _run(session.handle_input("SUGGEST"))
    _run(session.handle_input("DONE"))
    _run(session.handle_input("DONE"))

    assert session.player is not None
    assert session.player.class_type == "warrior"
    assert session.player.name == "IntegHeroBeta"


def test_full_flow_look_shows_room_description(load_game_data):
    """After creation, LOOK shows room description (town_square)."""
    collected = []

    async def send(text):
        collected.append(text)

    session = GameSession(
        send_fn=send,
        world=_make_world(),
        class_defs=_load_class_defs(),
        clock=None,
        sessions={},
    )

    _run(session.start())
    _run(session.handle_input("IntegHeroGamma"))
    _run(session.handle_input("warrior"))
    _run(session.handle_input("SUGGEST"))
    _run(session.handle_input("DONE"))
    _run(session.handle_input("DONE"))

    # LOOK
    collected.clear()
    _run(session.handle_input("LOOK"))
    output = "".join(collected)
    assert any(
        phrase in output.lower()
        for phrase in ["town", "square", "tavern", "exits"]
    )


def test_full_flow_status_shows_survival_stats(load_game_data):
    """After creation, STATUS shows hunger/thirst/stamina."""
    collected = []

    async def send(text):
        collected.append(text)

    session = GameSession(
        send_fn=send,
        world=_make_world(),
        class_defs=_load_class_defs(),
        clock=None,
        sessions={},
    )

    _run(session.start())
    _run(session.handle_input("IntegHeroDelta"))
    _run(session.handle_input("warrior"))
    _run(session.handle_input("SUGGEST"))
    _run(session.handle_input("DONE"))
    _run(session.handle_input("DONE"))

    # STATUS
    collected.clear()
    _run(session.handle_input("STATUS"))
    output = "".join(collected)
    assert any(
        phrase in output.lower()
        for phrase in ["hunger", "thirst", "stamina"]
    )


def test_full_flow_save_persists_player(load_game_data):
    """After creation, SAVE saves the player to the database."""
    from server.engine.persistence import load_player

    collected = []

    async def send(text):
        collected.append(text)

    session = GameSession(
        send_fn=send,
        world=_make_world(),
        class_defs=_load_class_defs(),
        clock=None,
        sessions={},
    )

    save_name = "IntegHeroEpsilon"

    _run(session.start())
    _run(session.handle_input(save_name))
    _run(session.handle_input("warrior"))
    _run(session.handle_input("SUGGEST"))
    _run(session.handle_input("DONE"))
    _run(session.handle_input("DONE"))

    # SAVE
    collected.clear()
    _run(session.handle_input("SAVE"))
    output = "".join(collected)
    assert "saved" in output.lower()

    # Verify the save was written
    save_data = load_player(save_name)
    assert save_data is not None
    assert save_data["character"]["name"] == save_name
    assert save_data["character"]["class_type"] == "warrior"


def test_invalid_class_shows_error_and_stays_in_creation(load_game_data):
    """Entering an unknown class during creation shows an error."""
    collected = []

    async def send(text):
        collected.append(text)

    session = GameSession(
        send_fn=send,
        world=_make_world(),
        class_defs=_load_class_defs(),
        clock=None,
        sessions={},
    )

    _run(session.start())
    _run(session.handle_input("IntegHeroZeta"))

    # Try an invalid class
    collected.clear()
    _run(session.handle_input("PALADIN"))
    output = "".join(collected)

    # Should stay in CREATION and show error
    assert session.state == State.CREATION
    assert any(
        phrase in output.lower()
        for phrase in ["unknown", "choose", "warrior", "mage"]
    )
