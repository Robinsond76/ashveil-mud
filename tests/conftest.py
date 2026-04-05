"""
Shared test fixtures — load game data (items, NPCs, world) once per session.
"""
import os
import pytest

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "server", "data")


@pytest.fixture(scope="session", autouse=True)
def load_game_data():
    """Load items and NPC templates into their registries once per test session."""
    from server.engine.items import load_items
    from server.engine.npc import load_npcs
    from server.engine.persistence import init_db

    load_items(DATA_DIR)
    load_npcs(DATA_DIR)
    init_db()
