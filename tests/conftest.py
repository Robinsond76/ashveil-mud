"""
Shared test fixtures — load game data (items, NPCs, world) once per session.
"""
import os
import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "server", "data")


@pytest.fixture(scope="session", autouse=True)
def load_game_data():
    """Load items and NPC templates into their registries once per test session."""
    from server.engine.domain.items import load_items
    from server.engine.domain.npc import load_npcs
    from server.engine.persistence import init_db

    load_items(DATA_DIR)
    load_npcs(DATA_DIR)
    init_db()


@pytest.fixture
def make_nav_session():
    """Factory fixture to create a GameSession in NAVIGATION state.

    Usage:
        session = make_nav_session()
        session = make_nav_session(class_type="mage", mp=50, stamina=80)
        session = make_nav_session(clock=mock_clock)
    """
    def _factory(
        class_type="warrior",
        hp=None,
        mp=None,
        stamina=None,
        hunger=None,
        thirst=None,
        clock=None,
        player_kwargs=None,
    ):
        from server.engine.game import GameSession, State
        from server.engine.world.map import WorldMap
        from server.engine.domain.character import Character

        world = WorldMap.__new__(WorldMap)
        world._rooms = {}
        world.get_room = lambda rid: None
        world.active_encounter_groups = lambda rid: []

        collected = []

        async def _send(text):
            collected.append(text)

        session = GameSession(send_fn=_send, world=world, class_defs={}, clock=clock)
        player = Character(name="Hero", class_type=class_type)

        if mp is not None:
            player.mp = mp
            player.max_mp = 100
        if stamina is not None:
            player.stamina = stamina
            player.max_stamina = 100.0
        if hp is not None:
            player.hp = hp
            player.max_hp = max(hp, player.max_hp)
        if hunger is not None:
            player.hunger = hunger
        if thirst is not None:
            player.thirst = thirst
        if player_kwargs:
            for k, v in player_kwargs.items():
                setattr(player, k, v)

        session.player = player
        session.state = State.NAVIGATION
        session._collected = collected

        return session

    return _factory
