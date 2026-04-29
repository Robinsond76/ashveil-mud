import json
import pytest
from server.engine.world.map import Room, EncounterGroup


def test_recruit_hall_no_hardcoded_npc_descriptions():
    """Ensure test_recruit_hall description doesn't contain hardcoded NPC names."""
    # Load the room data
    with open("server/data/rooms/testing_grounds.json") as f:
        data = json.load(f)
    
    # Find the recruit hall room
    recruit_hall = next(r for r in data if r["id"] == "test_recruit_hall")
    description = recruit_hall["description"]
    
    # These names should NOT be in the description (they come from recruitable_npc_ids dynamically)
    npc_names = ["Gareth", "Lyria", "Sable", "Aldric", "Brom", "Vex", "Mira", "Ophelia"]
    
    for name in npc_names:
        assert name not in description, f"NPC name '{name}' should not be hardcoded in room description"
