"""
Phase 7 — Glass Cannon Mechanic tests.

Phase A: Glass cannon constraints (spell_power_modifier, mage melee guard, weight cap)
"""
import pytest

from server.engine.domain.character import Character


def make_mage(name="Mage", INT=12):
    c = Character(name=name, class_type="mage", INT=INT)
    c.max_hp = 30
    c.hp = 30
    c.max_mp = 50
    c.mp = 50
    return c


def make_warrior(name="Warrior"):
    return Character(name=name, class_type="warrior")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — Glass Cannon Constraints
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseA_SpellPowerModifier:
    def test_mage_no_armor_returns_1(self):
        mage = make_mage()
        assert mage.spell_power_modifier() == pytest.approx(1.0)

    def test_mage_cloth_robe_returns_1(self):
        mage = make_mage()
        mage.equipment["body"] = "cloth_robe"
        assert mage.spell_power_modifier() == pytest.approx(1.0)

    def test_mage_leather_armor_returns_0_9(self):
        mage = make_mage()
        mage.equipment["body"] = "leather_armor"
        assert mage.spell_power_modifier() == pytest.approx(0.9)

    def test_mage_chainmail_returns_0_7(self):
        mage = make_mage()
        mage.equipment["body"] = "chainmail"
        assert mage.spell_power_modifier() == pytest.approx(0.7)

    def test_mage_plate_armor_returns_0(self):
        mage = make_mage()
        mage.equipment["body"] = "plate_armor"
        assert mage.spell_power_modifier() == pytest.approx(0.0)

    def test_non_mage_returns_1_regardless_of_armor(self):
        warrior = make_warrior()
        warrior.equipment["body"] = "plate_armor"
        assert warrior.spell_power_modifier() == pytest.approx(1.0)


class TestPhaseA_MeleeDamageGuard:
    def test_mage_with_non_staff_weapon_deals_1_damage(self):
        mage = make_mage()
        mage.equipment["weapon"] = "iron_sword"
        for _ in range(20):
            assert mage.roll_damage() == 1

    def test_mage_with_staff_uses_normal_range(self):
        import random
        mage = make_mage()
        mage.equipment["weapon"] = "oak_staff"
        random.seed(42)
        results = [mage.roll_damage() for _ in range(20)]
        # Oak staff: damage_min=3, damage_max=7. Mage guard (returns 1) must NOT apply.
        assert min(results) >= 3, "Mage with staff should use weapon damage range, not mage guard"
        assert max(results) <= 7, "Damage should not exceed weapon maximum"

    def test_mage_bare_handed_deals_1_damage(self):
        mage = make_mage()
        for _ in range(20):
            assert mage.roll_damage() == 1

    def test_warrior_with_sword_uses_normal_range(self):
        import random
        warrior = make_warrior()
        warrior.equipment["weapon"] = "iron_sword"
        random.seed(42)
        results = [warrior.roll_damage() for _ in range(20)]
        # Iron sword: damage_min=7, damage_max=13.
        assert min(results) >= 7, "Warrior with iron_sword should deal at least 7 damage"
        assert max(results) <= 13, "Warrior with iron_sword should deal at most 13 damage"


class TestPhaseA_MageWeightCap:
    def test_mage_cap_is_int_times_1_5(self):
        mage = make_mage(INT=10)
        assert mage.carry_weight_cap == int(10 * 1.5)

    def test_mage_cap_scales_with_int(self):
        mage = make_mage(INT=16)
        assert mage.carry_weight_cap == int(16 * 1.5)

    def test_warrior_cap_uses_default_formula(self):
        warrior = make_warrior()
        # Warriors use the base 20 (or whatever STR-based formula)
        assert warrior.carry_weight_cap == 20  # base value per existing logic
