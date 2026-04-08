"""
Phase 7 — Wizard & Spell Overhaul tests.

Phase A: Glass cannon constraints (spell_power_modifier, mage melee guard, weight cap)
Phase B: Staff & spellbook items + spell_power_modifier additions
Phase C: Spell data in mage_skills.json
Phase D: Skill dataclass new fields
Phase E: Cast time — _resolve_aoe_targets
Phase F: Concentration interruption
Phase G: AoE grid targeting coverage
Phase H: Zero mana → DODGE
"""
import asyncio
import random
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from server.engine.character import Character
from server.engine.items import get_item

DATA_DIR = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "server", "data"
)


def _load_skills_once():
    from server.engine.skills import _SKILL_REGISTRY
    if not _SKILL_REGISTRY:
        from server.engine.skills import load_skills
        load_skills(DATA_DIR)


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
        mage = make_mage()
        mage.equipment["weapon"] = "oak_staff"
        results = {mage.roll_damage() for _ in range(50)}
        # Should hit multiple values (normal range), not always 1
        assert len(results) > 1

    def test_mage_bare_handed_deals_1_damage(self):
        mage = make_mage()
        for _ in range(20):
            assert mage.roll_damage() == 1

    def test_warrior_with_sword_uses_normal_range(self):
        warrior = make_warrior()
        warrior.equipment["weapon"] = "iron_sword"
        results = {warrior.roll_damage() for _ in range(30)}
        assert len(results) > 1


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


# ═══════════════════════════════════════════════════════════════════════════════
# Phase B — Staff & Spellbook Items
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseB_StaffItems:
    def test_apprentice_staff_exists(self):
        item = get_item("apprentice_staff")
        assert item is not None

    def test_apprentice_staff_weapon_type_is_staff(self):
        item = get_item("apprentice_staff")
        assert item.weapon_type == "staff"

    def test_apprentice_staff_has_spell_power_bonus(self):
        item = get_item("apprentice_staff")
        assert item.spell_power_bonus >= 1

    def test_oaken_staff_exists(self):
        item = get_item("oaken_staff")
        assert item is not None

    def test_arcane_staff_has_spell_power_bonus(self):
        item = get_item("arcane_staff")
        # Updated arcane_staff should have spell_power_bonus
        assert item is not None
        assert item.spell_power_bonus >= 1


class TestPhaseB_SpellbookItems:
    def test_basic_spellbook_exists(self):
        item = get_item("basic_spellbook")
        assert item is not None

    def test_basic_spellbook_effect_type_is_spellbook(self):
        item = get_item("basic_spellbook")
        assert item.effect_type == "spellbook"

    def test_basic_spellbook_grants_spells(self):
        item = get_item("basic_spellbook")
        assert len(item.grants_spells) > 0

    def test_basic_spellbook_has_spell_power_bonus(self):
        item = get_item("basic_spellbook")
        assert item.spell_power_bonus >= 1

    def test_advanced_spellbook_exists(self):
        item = get_item("advanced_spellbook")
        assert item is not None


class TestPhaseB_SpellPowerModifierWithGear:
    def test_mage_spell_power_modifier_adds_staff_bonus(self):
        mage = make_mage()
        mage.equipment["weapon"] = "apprentice_staff"
        staff = get_item("apprentice_staff")
        bonus = staff.spell_power_bonus
        assert mage.spell_power_modifier() == pytest.approx(1.0 + bonus / 100)

    def test_mage_spell_power_modifier_adds_spellbook_bonus(self):
        mage = make_mage()
        mage.inventory = ["basic_spellbook"]
        book = get_item("basic_spellbook")
        bonus = book.spell_power_bonus
        assert mage.spell_power_modifier() == pytest.approx(1.0 + bonus / 100)

    def test_mage_spell_power_modifier_combines_armor_staff_spellbook(self):
        mage = make_mage()
        mage.equipment["body"] = "leather_armor"   # 0.9
        mage.equipment["weapon"] = "apprentice_staff"
        mage.inventory = ["basic_spellbook"]
        staff_bonus = get_item("apprentice_staff").spell_power_bonus
        book_bonus = get_item("basic_spellbook").spell_power_bonus
        expected = 0.9 + staff_bonus / 100 + book_bonus / 100
        assert mage.spell_power_modifier() == pytest.approx(expected)

    def test_plate_armor_blocks_cast_regardless_of_staff(self):
        mage = make_mage()
        mage.equipment["body"] = "plate_armor"
        mage.equipment["weapon"] = "apprentice_staff"
        # Plate = 0.0 regardless
        assert mage.spell_power_modifier() == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — Spell Data in mage_skills.json
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseC_SpellData:
    def setup_method(self):
        _load_skills_once()

    def test_arcane_bolt_exists(self):
        from server.engine.skills import get_skill
        s = get_skill("arcane_bolt")
        assert s is not None

    def test_arcane_bolt_is_instant(self):
        from server.engine.skills import get_skill
        s = get_skill("arcane_bolt")
        assert s.cast_time_seconds == 0

    def test_magic_missile_exists(self):
        from server.engine.skills import get_skill
        s = get_skill("magic_missile")
        assert s is not None

    def test_magic_missile_cast_time(self):
        from server.engine.skills import get_skill
        s = get_skill("magic_missile")
        assert s.cast_time_seconds == 3

    def test_fireball_exists(self):
        from server.engine.skills import get_skill
        s = get_skill("fireball")
        assert s is not None

    def test_fireball_cast_time_is_9(self):
        from server.engine.skills import get_skill
        s = get_skill("fireball")
        assert s.cast_time_seconds == 9

    def test_fireball_target_type_is_grid_2x2(self):
        from server.engine.skills import get_skill
        s = get_skill("fireball")
        assert s.target_type == "grid_2x2"

    def test_fireball_damage_type_is_fire(self):
        from server.engine.skills import get_skill
        s = get_skill("fireball")
        assert s.damage_type == "fire"

    def test_fireball_has_4_cast_messages(self):
        from server.engine.skills import get_skill
        s = get_skill("fireball")
        assert len(s.cast_messages) == 4

    def test_chain_lightning_target_type_is_all_enemies(self):
        from server.engine.skills import get_skill
        s = get_skill("chain_lightning")
        assert s.target_type == "all_enemies"

    def test_frost_bolt_target_type_is_single(self):
        from server.engine.skills import get_skill
        s = get_skill("frost_bolt")
        assert s.target_type == "single"

    def test_arcane_shield_target_type_is_self(self):
        from server.engine.skills import get_skill
        s = get_skill("arcane_shield")
        assert s.target_type == "self"

    def test_blink_is_instant_and_self(self):
        from server.engine.skills import get_skill
        s = get_skill("blink")
        assert s is not None
        assert s.cast_time_seconds == 0
        assert s.target_type == "self"

    def test_all_mage_spells_have_cast_time_seconds(self):
        from server.engine.skills import get_skill
        for spell_id in ["arcane_bolt", "magic_missile", "frost_bolt",
                         "fireball", "chain_lightning", "arcane_shield", "blink"]:
            s = get_skill(spell_id)
            assert hasattr(s, "cast_time_seconds"), f"{spell_id} missing cast_time_seconds"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — Skill Dataclass New Fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseD_SkillDataclass:
    def test_skill_has_cast_time_seconds_field(self):
        from server.engine.skills import Skill
        s = Skill(id="t", name="T", description="", class_type="mage",
                  mp_cost=5, cooldown_ticks=3, effect_type="damage")
        assert s.cast_time_seconds == 0

    def test_skill_has_target_type_field(self):
        from server.engine.skills import Skill
        s = Skill(id="t", name="T", description="", class_type="mage",
                  mp_cost=5, cooldown_ticks=3, effect_type="damage")
        assert s.target_type == "single"

    def test_skill_has_damage_type_field(self):
        from server.engine.skills import Skill
        s = Skill(id="t", name="T", description="", class_type="mage",
                  mp_cost=5, cooldown_ticks=3, effect_type="damage")
        assert s.damage_type == "physical"

    def test_skill_has_spell_power_scale_field(self):
        from server.engine.skills import Skill
        s = Skill(id="t", name="T", description="", class_type="mage",
                  mp_cost=5, cooldown_ticks=3, effect_type="damage")
        assert s.spell_power_scale == pytest.approx(1.0)

    def test_skill_has_cast_messages_field(self):
        from server.engine.skills import Skill
        s = Skill(id="t", name="T", description="", class_type="mage",
                  mp_cost=5, cooldown_ticks=3, effect_type="damage")
        assert s.cast_messages == []

    def test_skill_accepts_cast_messages_list(self):
        from server.engine.skills import Skill
        msgs = ["start", "mid", "end", "fire"]
        s = Skill(id="t", name="T", description="", class_type="mage",
                  mp_cost=5, cooldown_ticks=3, effect_type="damage",
                  cast_messages=msgs)
        assert s.cast_messages == msgs


# ═══════════════════════════════════════════════════════════════════════════════
# Phase E — AoE Grid Targeting (_resolve_aoe_targets)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseE_AoEGridTargeting:
    def _make_combatant(self, row, col, alive=True, name="Target"):
        from server.engine.combat import Combatant
        char = make_mage(name=name)
        if not alive:
            char.hp = 0
        c = Combatant(character=char, is_player_side=False, row=row, col=col)
        return c

    def test_single_target_by_name(self):
        from server.engine.combat import CombatSession
        c0 = self._make_combatant(0, 0, name="A")
        c1 = self._make_combatant(0, 1, name="B")
        result = CombatSession._resolve_aoe_targets("single", 0, 0, [c0, c1], name="A")
        assert c0 in result
        assert c1 not in result

    def test_grid_1x1_returns_exact_cell(self):
        from server.engine.combat import CombatSession
        c00 = self._make_combatant(0, 0)
        c01 = self._make_combatant(0, 1)
        c10 = self._make_combatant(1, 0)
        result = CombatSession._resolve_aoe_targets("grid_1x1", 0, 0, [c00, c01, c10])
        assert c00 in result
        assert c01 not in result
        assert c10 not in result

    def test_grid_1x2_returns_row_and_two_cols(self):
        from server.engine.combat import CombatSession
        c00 = self._make_combatant(0, 0)
        c01 = self._make_combatant(0, 1)
        c02 = self._make_combatant(0, 2)
        c10 = self._make_combatant(1, 0)
        result = CombatSession._resolve_aoe_targets("grid_1x2", 0, 0, [c00, c01, c02, c10])
        assert c00 in result
        assert c01 in result
        assert c02 not in result
        assert c10 not in result

    def test_grid_2x2_returns_four_cells(self):
        from server.engine.combat import CombatSession
        c00 = self._make_combatant(0, 0)
        c01 = self._make_combatant(0, 1)
        c10 = self._make_combatant(1, 0)
        c11 = self._make_combatant(1, 1)
        c02 = self._make_combatant(0, 2)
        result = CombatSession._resolve_aoe_targets("grid_2x2", 0, 0, [c00, c01, c10, c11, c02])
        assert c00 in result
        assert c01 in result
        assert c10 in result
        assert c11 in result
        assert c02 not in result

    def test_all_enemies_returns_all_alive(self):
        from server.engine.combat import CombatSession
        c0 = self._make_combatant(0, 0, alive=True)
        c1 = self._make_combatant(0, 1, alive=True)
        c2 = self._make_combatant(1, 0, alive=False)
        result = CombatSession._resolve_aoe_targets("all_enemies", 0, 0, [c0, c1, c2])
        assert c0 in result
        assert c1 in result
        assert c2 not in result

    def test_grid_excludes_dead_combatants(self):
        from server.engine.combat import CombatSession
        alive = self._make_combatant(0, 0, alive=True)
        dead = self._make_combatant(0, 0, alive=False, name="Dead")
        result = CombatSession._resolve_aoe_targets("grid_1x1", 0, 0, [alive, dead])
        assert alive in result
        assert dead not in result


# ═══════════════════════════════════════════════════════════════════════════════
# Phase F — Concentration Interruption
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseF_Interruption:
    def _make_combat_session(self):
        from server.engine.combat import CombatSession, Combatant
        mage = make_mage(INT=14)
        mage.mp = 50
        from server.engine.npc import NPC
        npc = NPC(
            name="Goblin", class_type="warrior", level=1,
            hp=30, max_hp=30, mp=0, max_mp=0,
            STR=10, DEX=10, INT=10, WIS=10, CON=10, AGI=10,
            xp_reward=10, gold_range=(0, 5), template_id="goblin",
        )
        session = CombatSession(
            player_party=[mage],
            enemy_party=[npc],
            send=AsyncMock(),
        )
        mage_combatant = session.player_combatants[0]
        return session, mage_combatant, mage

    def test_apply_damage_cancels_channeling_on_failed_save(self):
        session, mage_cbt, mage = self._make_combat_session()
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        mage_cbt._channeling = task
        mage_cbt._channeling_spell_mp = 10
        # Force INT save to fail: INT=14 → modifier = (14-10)//2 = 2; roll 1→3 < 12
        with patch("random.randint", return_value=1):
            log = []
            session._apply_damage(mage_cbt, 5, log)
        task.cancel.assert_called_once()
        assert any("concentration" in line.lower() for line in log)

    def test_apply_damage_keeps_channeling_on_passed_save(self):
        session, mage_cbt, mage = self._make_combat_session()
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        mage_cbt._channeling = task
        mage_cbt._channeling_spell_mp = 10
        # Force INT save to pass: roll 20 → 20+(14-10)//2 = 22 >= 12
        with patch("random.randint", return_value=20):
            log = []
            session._apply_damage(mage_cbt, 5, log)
        task.cancel.assert_not_called()

    def test_apply_damage_with_no_channeling_just_applies_damage(self):
        session, mage_cbt, mage = self._make_combat_session()
        mage_cbt._channeling = None
        hp_before = mage.hp
        log = []
        session._apply_damage(mage_cbt, 5, log)
        assert mage.hp < hp_before

    def test_interrupted_mage_gets_half_mana_refunded(self):
        session, mage_cbt, mage = self._make_combat_session()
        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False
        mage_cbt._channeling = task
        mage_cbt._channeling_spell_mp = 18
        mage.mp = 0  # already deducted
        with patch("random.randint", return_value=1):  # fail save
            log = []
            session._apply_damage(mage_cbt, 1, log)
        assert mage.mp == 9  # half of 18 refunded


# ═══════════════════════════════════════════════════════════════════════════════
# Phase G — AoE Grid Targeting (extended)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseG_AoEExtended:
    def _combatant(self, row, col, name="T"):
        from server.engine.combat import Combatant
        c = Character(name=name, class_type="warrior")
        c.hp = 30
        return Combatant(character=c, is_player_side=False, row=row, col=col)

    def test_grid_2x2_at_edge_clips_to_grid(self):
        from server.engine.combat import CombatSession
        # Row 1, col 2 → grid_2x2 would want rows [1,2] cols [2,3]
        # Only row 1 exists (BACK_ROW=1), col 3 doesn't exist
        c12 = self._combatant(1, 2, "C12")
        c22 = self._combatant(2, 2, "C22")  # row 2 doesn't exist in grid but included
        result = CombatSession._resolve_aoe_targets("grid_2x2", 1, 2, [c12, c22])
        assert c12 in result

    def test_all_enemies_returns_empty_if_all_dead(self):
        from server.engine.combat import CombatSession
        dead = self._combatant(0, 0)
        dead.character.hp = 0
        result = CombatSession._resolve_aoe_targets("all_enemies", 0, 0, [dead])
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# Phase H — Zero Mana State
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseH_ZeroMana:
    def _make_session_with_mage_strategy(self):
        from server.engine.combat import CombatSession, Combatant
        from server.engine.npc import NPC
        _load_skills_once()

        mage = make_mage(INT=10)
        mage.mp = 0
        mage.max_mp = 50
        mage.unlocked_skills = {"fireball": 1}

        npc = NPC(
            name="Goblin", class_type="warrior", level=1,
            hp=30, max_hp=30, mp=0, max_mp=0,
            STR=10, DEX=10, INT=10, WIS=10, CON=10, AGI=10,
            xp_reward=10, gold_range=(0, 5), template_id="goblin",
        )
        npc.status_effects = {}

        session = CombatSession(
            player_party=[mage],
            enemy_party=[npc],
            send=AsyncMock(),
        )
        mage_combatant = session.player_combatants[0]
        return session, mage_combatant, mage, npc

    def test_zero_mp_mage_action_is_dodge(self):
        session, mage_cbt, mage, npc = self._make_session_with_mage_strategy()
        mage.strategies = [{"action": "USE_SKILL fireball", "condition": "always"}]
        log = []
        session._do_action_mage_zero_mp(mage_cbt, log)
        # Should set defending/dodge status or log dodge message
        assert any("dodge" in line.lower() or "brace" in line.lower() or "nothing" in line.lower()
                   for line in log)

    def test_zero_mp_message_shown_first_occurrence(self):
        session, mage_cbt, mage, npc = self._make_session_with_mage_strategy()
        mage._zero_mp_message_shown = False
        log = []
        session._do_action_mage_zero_mp(mage_cbt, log)
        assert any("arcane" in line.lower() or "nothing" in line.lower()
                   for line in log)

    def test_zero_mp_message_not_repeated(self):
        session, mage_cbt, mage, npc = self._make_session_with_mage_strategy()
        mage._zero_mp_message_shown = True
        log = []
        session._do_action_mage_zero_mp(mage_cbt, log)
        # Second call should not include the "reaches for arcane" message
        arcane_msgs = [l for l in log if "arcane" in l.lower()]
        assert len(arcane_msgs) == 0
