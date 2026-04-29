"""
Tests for the typed Action dataclass hierarchy (improvement-02).
"""
import pytest

from server.engine.actions import Attack, Defend, Flee, UseSkill, UseItem, CombatResult


# ── Action type tests ─────────────────────────────────────────────────────────

def test_attack_action_has_target():
    a = Attack(target=None)
    assert a.target is None


def test_attack_action_stores_target():
    sentinel = object()
    a = Attack(target=sentinel)
    assert a.target is sentinel


def test_use_skill_action_has_skill_id():
    a = UseSkill(skill_id="fireball", target=None)
    assert a.skill_id == "fireball"


def test_use_item_action_has_item_id():
    a = UseItem(item_id="health_potion", target=None)
    assert a.item_id == "health_potion"


def test_defend_action():
    a = Defend()
    assert isinstance(a, Defend)


def test_flee_action():
    a = Flee()
    assert isinstance(a, Flee)


# ── CombatResult tests ────────────────────────────────────────────────────────

def test_combat_result_victory():
    r = CombatResult(state="victory", summary=["You win!"], rewards={"xp": 100, "gold": 50, "loot": []})
    assert r.state == "victory"
    assert r.rewards["xp"] == 100


def test_combat_result_defeat():
    r = CombatResult(state="defeat", summary=["You lost."])
    assert r.state == "defeat"
    assert r.rewards == {}


# ── Strategy integration tests ────────────────────────────────────────────────

def test_evaluate_strategy_returns_attack_action(load_game_data):
    """Default strategy with no rules returns Attack action."""
    from server.engine.domain.character import Character
    from server.engine.strategy import evaluate_strategy

    c = Character(name="test", class_type="warrior")
    c.strategies = []
    action, target = evaluate_strategy(c, [], [])
    assert isinstance(action, Attack)


def test_evaluate_strategy_returns_defend_action(load_game_data):
    """Strategy rule with DEFEND returns Defend action."""
    from server.engine.domain.character import Character
    from server.engine.strategy import evaluate_strategy

    c = Character(name="test", class_type="warrior")
    c.strategies = [
        {"priority": 1, "condition": "ALWAYS", "action": "DEFEND", "target": "SELF"}
    ]
    action, target = evaluate_strategy(c, [c], [])
    assert isinstance(action, Defend)


def test_evaluate_strategy_returns_flee_action(load_game_data):
    """Strategy rule with FLEE returns Flee action."""
    from server.engine.domain.character import Character
    from server.engine.strategy import evaluate_strategy

    c = Character(name="test", class_type="warrior")
    c.strategies = [
        {"priority": 1, "condition": "ALWAYS", "action": "FLEE", "target": "SELF"}
    ]
    action, target = evaluate_strategy(c, [c], [])
    assert isinstance(action, Flee)


def test_evaluate_strategy_returns_use_skill_action(load_game_data):
    """Strategy rule with USE_SKILL returns UseSkill action."""
    from server.engine.domain.character import Character
    from server.engine.strategy import evaluate_strategy

    c = Character(name="test", class_type="mage")
    c.hp = 100
    c.max_hp = 100
    c.mp = 50
    c.strategies = [
        {"priority": 1, "condition": "ALWAYS", "action": "USE_SKILL fireball", "target": "NEAREST_ENEMY"}
    ]
    enemy = Character(name="enemy", class_type="warrior")
    action, target = evaluate_strategy(c, [c], [enemy])
    assert isinstance(action, UseSkill)
    assert action.skill_id == "fireball"


def test_evaluate_strategy_returns_use_item_action(load_game_data):
    """Strategy rule with USE_ITEM returns UseItem action."""
    from server.engine.domain.character import Character
    from server.engine.strategy import evaluate_strategy

    c = Character(name="test", class_type="warrior")
    c.strategies = [
        {"priority": 1, "condition": "ALWAYS", "action": "USE_ITEM health_potion", "target": "SELF"}
    ]
    action, target = evaluate_strategy(c, [c], [])
    assert isinstance(action, UseItem)
    assert action.item_id == "health_potion"


# ── Grid validation tests ─────────────────────────────────────────────────────

def test_assign_positions_rejects_party_over_six(load_game_data):
    """Parties larger than 6 should raise ValueError, not silently drop members."""
    from server.engine.domain.character import Character
    from server.engine.combat import CombatSession, Combatant

    oversized = [
        Combatant(character=Character(name=f"c{i}", class_type="warrior"), is_player_side=True)
        for i in range(7)
    ]
    with pytest.raises(ValueError, match="exceeds.*grid"):
        CombatSession._assign_positions(oversized)
