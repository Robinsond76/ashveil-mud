"""
Tests for real-time per-character attack speed intervals.
"""
import pytest
from server.engine.character import Character


def _bare(class_type, AGI):
    """Character with no gear or carried items (clean speed calculation)."""
    c = Character(name="T", class_type=class_type, AGI=AGI)
    c.inventory = []
    c.equipment = {}
    return c


class TestActionIntervalSeconds:
    def test_thief_agility_16_attacks_every_3s(self, load_game_data):
        # 48.0 / 16 = 3.0
        char = _bare("thief", AGI=16)
        assert char.action_interval == pytest.approx(3.0)

    def test_warrior_agility_12_attacks_every_4s(self, load_game_data):
        # 48.0 / 12 = 4.0
        char = _bare("warrior", AGI=12)
        assert char.action_interval == pytest.approx(4.0)

    def test_mage_agility_12_attacks_every_4s(self, load_game_data):
        char = _bare("mage", AGI=12)
        assert char.action_interval == pytest.approx(4.0)

    def test_max_clamp_applies_for_very_low_speed(self, load_game_data):
        # AGI=3 (minimum stat), no gear → effective_speed=3 → 48/3=16.0 → clamped to MAX
        from server.config import MAX_ATTACK_INTERVAL
        char = _bare("warrior", AGI=3)
        assert char.action_interval == pytest.approx(MAX_ATTACK_INTERVAL)

    def test_min_clamp_applies(self, load_game_data):
        # If effective_speed is huge, interval must floor at MIN_ATTACK_INTERVAL
        from server.config import MIN_ATTACK_INTERVAL
        char = _bare("thief", AGI=18)
        # AGI=18 → 48/18 ≈ 2.67 > MIN (2.0) — patch speed to force the floor
        char.__class__ = type(
            "UltraFastChar",
            (Character,),
            {"effective_speed": property(lambda self: 100)},
        )
        # 48/100 = 0.48, clamped up to MIN_ATTACK_INTERVAL
        assert char.action_interval == pytest.approx(MIN_ATTACK_INTERVAL)

    def test_weight_penalty_slows_interval(self, load_game_data):
        # Warrior AGI=12, effective_speed=12; add weight so penalty=2 → speed=10 → 4.8s
        char = _bare("warrior", AGI=12)
        # Monkey-patch effective_speed (weight calculation tested separately)
        char.__class__ = type(
            "HeavyWarrior",
            (Character,),
            {"effective_speed": property(lambda self: 10)},
        )
        assert char.action_interval == pytest.approx(4.8)


class TestStatsDisplay:
    def test_stats_summary_shows_attack_interval(self, load_game_data):
        char = _bare("thief", AGI=16)
        summary = char.stats_summary()
        assert "3.0s/attack" in summary