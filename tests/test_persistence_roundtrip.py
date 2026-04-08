"""
Persistence roundtrip tests: full save/load cycle with complex character data.
Covers T13 (no persistence roundtrip test): save_player/load_player never
actually called in tests; to_dict/from_dict tested trivially.
"""
import pytest

from server.engine.character import Character
from server.engine.persistence import save_player, load_player


def test_character_roundtrip_preserves_basic_fields(load_game_data):
    """Save and load a character — basic fields survive the roundtrip."""
    c = Character(name="RoundtripHeroBasic", class_type="mage")
    c.level = 3
    c.xp = 1500
    c.gold = 120
    c.hp = 18
    c.max_hp = 30
    c.mp = 35
    c.max_mp = 60

    save_data = {
        "character": c.to_dict(),
        "party": [],
        "current_room_id": "town_square",
        "last_campfire_room_id": "inn",
    }

    save_player("RoundtripHeroBasic", save_data)
    loaded = load_player("RoundtripHeroBasic")

    assert loaded is not None
    lc = Character.from_dict(loaded["character"])

    assert lc.name == "RoundtripHeroBasic"
    assert lc.class_type == "mage"
    assert lc.level == 3
    assert lc.xp == 1500
    assert lc.gold == 120
    assert lc.hp == 18
    assert lc.max_hp == 30
    assert lc.mp == 35
    assert lc.max_mp == 60


def test_character_roundtrip_preserves_stats(load_game_data):
    """All six base stats survive the roundtrip."""
    c = Character(name="RoundtripHeroStats", class_type="mage")
    c.STR = 8
    c.DEX = 12
    c.INT = 18
    c.WIS = 14
    c.CON = 10
    c.AGI = 11

    save_player("RoundtripHeroStats", {"character": c.to_dict(), "party": [],
                                        "current_room_id": "town_square",
                                        "last_campfire_room_id": "test_campfire"})
    loaded = load_player("RoundtripHeroStats")
    lc = Character.from_dict(loaded["character"])

    assert lc.STR == 8
    assert lc.DEX == 12
    assert lc.INT == 18
    assert lc.WIS == 14
    assert lc.CON == 10
    assert lc.AGI == 11


def test_character_roundtrip_preserves_survival_stats(load_game_data):
    """Survival stats (hunger, thirst, stamina) survive with float precision."""
    c = Character(name="RoundtripHeroSurvival", class_type="warrior")
    c.hunger = 72.5
    c.thirst = 88.0
    c.stamina = 45.25

    save_player("RoundtripHeroSurvival", {"character": c.to_dict(), "party": [],
                                           "current_room_id": "town_square",
                                           "last_campfire_room_id": "test_campfire"})
    loaded = load_player("RoundtripHeroSurvival")
    lc = Character.from_dict(loaded["character"])

    assert lc.hunger == pytest.approx(72.5)
    assert lc.thirst == pytest.approx(88.0)
    assert lc.stamina == pytest.approx(45.25)


def test_character_roundtrip_preserves_equipment_and_inventory(load_game_data):
    """Equipment slots and inventory items survive the roundtrip."""
    c = Character(name="RoundtripHeroGear", class_type="mage")
    c.equipment["weapon"] = "oaken_staff"
    c.inventory = ["health_potion", "mana_potion", "torch"]

    save_player("RoundtripHeroGear", {"character": c.to_dict(), "party": [],
                                       "current_room_id": "town_square",
                                       "last_campfire_room_id": "test_campfire"})
    loaded = load_player("RoundtripHeroGear")
    lc = Character.from_dict(loaded["character"])

    assert lc.equipment["weapon"] == "oaken_staff"
    assert "health_potion" in lc.inventory
    assert "mana_potion" in lc.inventory
    assert "torch" in lc.inventory
    assert len(lc.inventory) == 3


def test_character_roundtrip_preserves_skills_and_modifiers(load_game_data):
    """Unlocked skills, modifiers, and active buffs survive the roundtrip."""
    c = Character(name="RoundtripHeroSkills", class_type="mage")
    c.modifiers = {"fire_intensity": 2, "staff_prof": 1}
    c.unlocked_skills = {"fireball": 1, "frost_bolt": 1}
    c.active_buffs = {"ration_satiated": 500}

    save_player("RoundtripHeroSkills", {"character": c.to_dict(), "party": [],
                                         "current_room_id": "town_square",
                                         "last_campfire_room_id": "test_campfire"})
    loaded = load_player("RoundtripHeroSkills")
    lc = Character.from_dict(loaded["character"])

    assert lc.modifiers["fire_intensity"] == 2
    assert lc.modifiers["staff_prof"] == 1
    assert lc.unlocked_skills["fireball"] == 1
    assert lc.unlocked_skills["frost_bolt"] == 1
    assert lc.active_buffs["ration_satiated"] == 500


def test_character_roundtrip_preserves_room_metadata(load_game_data):
    """current_room_id and last_campfire_room_id survive the roundtrip."""
    c = Character(name="RoundtripHeroRoom", class_type="warrior")

    save_player("RoundtripHeroRoom", {"character": c.to_dict(), "party": [],
                                       "current_room_id": "dungeon_entry",
                                       "last_campfire_room_id": "forest_camp"})
    loaded = load_player("RoundtripHeroRoom")

    assert loaded["current_room_id"] == "dungeon_entry"
    assert loaded["last_campfire_room_id"] == "forest_camp"


def test_load_nonexistent_player_returns_none(load_game_data):
    """Loading a player that has never been saved returns None."""
    result = load_player("NoSuchPlayer_XYZ_99999")
    assert result is None


def test_save_overwrites_previous_save(load_game_data):
    """Saving the same player twice uses the latest data (upsert)."""
    c = Character(name="RoundtripHeroOverwrite", class_type="warrior")
    c.gold = 50

    save_player("RoundtripHeroOverwrite", {"character": c.to_dict(), "party": [],
                                            "current_room_id": "town_square",
                                            "last_campfire_room_id": "test_campfire"})

    c.gold = 999
    save_player("RoundtripHeroOverwrite", {"character": c.to_dict(), "party": [],
                                            "current_room_id": "dungeon_entry",
                                            "last_campfire_room_id": "test_campfire"})

    loaded = load_player("RoundtripHeroOverwrite")
    lc = Character.from_dict(loaded["character"])

    assert lc.gold == 999
    assert loaded["current_room_id"] == "dungeon_entry"
