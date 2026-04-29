"""
Tests for improvement-03: data model cleanup.
"""
import pytest


# ── Task 1: Combatant Protocol ────────────────────────────────────────────────

def test_character_satisfies_combatant_protocol(load_game_data):
    """Character should satisfy the Combatant protocol."""
    from server.engine.protocols import Combatant
    from server.engine.domain.character import Character
    c = Character(name="test", class_type="warrior")
    assert isinstance(c, Combatant)
    assert hasattr(c, "name")
    assert hasattr(c, "hp")
    assert hasattr(c, "max_hp")
    assert hasattr(c, "mp")
    assert hasattr(c, "max_mp")
    assert hasattr(c, "equipment")
    assert hasattr(c, "inventory")


def test_npc_satisfies_combatant_protocol(load_game_data):
    """NPC should satisfy the Combatant protocol."""
    from server.engine.protocols import Combatant
    from server.engine.domain.npc import NPC
    npc = NPC(name="Goblin", class_type="warrior")
    assert isinstance(npc, Combatant)


# ── Task 2: Grid row/col defaults ─────────────────────────────────────────────

def test_character_grid_defaults_to_minus_one(load_game_data):
    """grid_row and grid_col should default to -1 (auto-assign)."""
    from server.engine.domain.character import Character
    c = Character(name="test", class_type="warrior")
    assert c.grid_row == -1
    assert c.grid_col == -1


# ── Task 3: Owner field ───────────────────────────────────────────────────────

def test_character_has_owner_field(load_game_data):
    """Character should have an owner field defaulting to empty string."""
    from server.engine.domain.character import Character
    c = Character(name="Hero", class_type="warrior")
    assert hasattr(c, "owner")
    assert c.owner == ""


def test_owner_persists_in_to_dict(load_game_data):
    """Owner field should appear in Character.to_dict() output."""
    from server.engine.domain.character import Character
    c = Character(name="Hero", class_type="warrior")
    c.owner = "player1"
    d = c.to_dict()
    assert d["owner"] == "player1"


def test_owner_restored_from_dict(load_game_data):
    """Owner field should be restored by Character.from_dict()."""
    from server.engine.domain.character import Character
    c = Character(name="Hero", class_type="warrior")
    c.owner = "player1"
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.owner == "player1"


def test_owner_defaults_empty_string_when_missing_from_save(load_game_data):
    """Old saves without 'owner' key should default to empty string."""
    from server.engine.domain.character import Character
    c = Character(name="Hero", class_type="warrior")
    d = c.to_dict()
    del d["owner"]
    c2 = Character.from_dict(d)
    assert c2.owner == ""


# ── Task 4: ItemEffect hierarchy ─────────────────────────────────────────────

def test_heal_effect_has_amount():
    from server.engine.item_effects import HealEffect
    e = HealEffect(amount=50)
    assert e.amount == 50


def test_restore_mp_effect_has_amount():
    from server.engine.item_effects import RestoreMPEffect
    e = RestoreMPEffect(amount=30)
    assert e.amount == 30


def test_status_remove_effect_has_status_id():
    from server.engine.item_effects import StatusRemoveEffect
    e = StatusRemoveEffect(status_id="poison")
    assert e.status_id == "poison"


def test_buff_effect_has_fields():
    from server.engine.item_effects import BuffEffect
    e = BuffEffect(buff_id="satiated", duration_minutes=30)
    assert e.buff_id == "satiated"
    assert e.duration_minutes == 30


def test_parse_item_effect_heal(load_game_data):
    from server.engine.item_effects import parse_item_effect, HealEffect
    from server.engine.domain.items import get_item
    # health_potion should parse to HealEffect
    item = get_item("health_potion")
    assert item is not None
    result = parse_item_effect(item.effect_type, item.effect_params)
    assert isinstance(result, HealEffect)
    assert result.amount > 0


def test_parse_item_effect_restore_mp(load_game_data):
    from server.engine.item_effects import parse_item_effect, RestoreMPEffect
    from server.engine.domain.items import get_item
    item = get_item("mana_potion")
    if item is None:
        pytest.skip("mana_potion not in data")
    result = parse_item_effect(item.effect_type, item.effect_params)
    assert isinstance(result, RestoreMPEffect)


def test_parse_item_effect_unknown_returns_none():
    from server.engine.item_effects import parse_item_effect
    result = parse_item_effect("light_source", {})
    assert result is None
