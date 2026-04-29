"""
Tests for caster spell preference: starter skills, basic-spell cascade, cleric smite default.
"""
import pytest
from unittest.mock import AsyncMock

from server.engine.domain.character import Character
from server.engine.domain.npc import NPC

DATA_DIR = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "server", "data"
)


def _load_skills():
    from server.engine.domain.skills import _SKILL_REGISTRY
    if not _SKILL_REGISTRY:
        from server.engine.domain.skills import load_skills
        load_skills(DATA_DIR)


def _make_enemy(name="Goblin"):
    npc = NPC(
        name=name, class_type="warrior", level=1,
        hp=50, max_hp=50, mp=0, max_mp=0,
        STR=10, DEX=10, INT=10, WIS=10, CON=10, AGI=10,
        xp_reward=10, gold_range=(0, 5), template_id="goblin",
    )
    npc.status_effects = {}
    return npc


def _make_session(caster, enemy):
    from server.engine.combat.session import CombatSession
    return CombatSession(
        player_party=[caster],
        enemy_party=[enemy],
        send=AsyncMock(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Starter skills auto-unlock at character creation
# ─────────────────────────────────────────────────────────────────────────────

class TestStarterSkills:
    def test_new_mage_has_arcane_bolt_unlocked(self, load_game_data):
        """A freshly created mage must have arcane_bolt unlocked without spending skill points."""
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        mage_def = class_defs["mage"]
        assert "starter_skills" in mage_def, "mage must have starter_skills field"
        assert "arcane_bolt" in mage_def["starter_skills"]

    def test_new_cleric_has_heal_and_smite_unlocked(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        cleric_def = class_defs["cleric"]
        assert "starter_skills" in cleric_def
        assert "heal" in cleric_def["starter_skills"]
        assert "smite" in cleric_def["starter_skills"]

    def test_arcane_bolt_is_in_mage_skill_tree(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        tree_ids = [node["id"] for node in class_defs["mage"]["skill_tree"]]
        assert "arcane_bolt" in tree_ids

    def test_arcane_bolt_is_free_in_mage_skill_tree(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        node = next(n for n in class_defs["mage"]["skill_tree"] if n["id"] == "arcane_bolt")
        assert node["unlock_cost"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Basic spell cascade in _resolve_skill
# ─────────────────────────────────────────────────────────────────────────────

class TestMageCascade:
    def test_mage_uses_arcane_bolt_when_fireball_mp_insufficient(self, load_game_data):
        """Mage with MP < fireball cost but MP >= arcane_bolt cost casts arcane_bolt."""
        _load_skills()
        mage = Character(name="Lyria", class_type="mage", INT=14)
        mage.mp = 10        # fireball costs 18; arcane_bolt costs 5
        mage.max_mp = 60
        mage.unlocked_skills = {"fireball": 1, "arcane_bolt": 1}
        mage.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(mage, enemy)
        actor = session.player_combatants[0]
        allies = [mage]
        enemies = [enemy]

        log = []
        session._resolve_skill(actor, "fireball", enemy, allies, enemies, log)

        # MP should have dropped by arcane_bolt cost (5), not fireball cost (18)
        assert mage.mp == 5  # 10 - 5
        # Log should mention the downgrade
        full_log = " ".join(log).lower()
        assert "low on mp" in full_log or "arcane bolt" in full_log

    def test_mage_goes_melee_when_no_mp_for_arcane_bolt(self, load_game_data):
        """Mage with MP < arcane_bolt cost falls to melee (no infinite cascade)."""
        _load_skills()
        mage = Character(name="Lyria", class_type="mage", INT=14)
        mage.mp = 3         # arcane_bolt costs 5 — can't afford it
        mage.max_mp = 60
        mage.unlocked_skills = {"fireball": 1, "arcane_bolt": 1}
        mage.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(mage, enemy)
        actor = session.player_combatants[0]
        allies = [mage]
        enemies = [enemy]

        log = []
        session._resolve_skill(actor, "fireball", enemy, allies, enemies, log)

        # MP unchanged (no spell cast)
        assert mage.mp == 3
        # Log should mention attacking instead
        full_log = " ".join(log).lower()
        assert "attacking instead" in full_log or "insufficient" in full_log

    def test_cascade_does_not_loop_when_basic_spell_is_requested_spell(self, load_game_data):
        """If the strategy directly requests arcane_bolt and MP is too low → melee, not infinite loop."""
        _load_skills()
        mage = Character(name="Lyria", class_type="mage", INT=14)
        mage.mp = 2         # arcane_bolt costs 5
        mage.max_mp = 60
        mage.unlocked_skills = {"arcane_bolt": 1}
        mage.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(mage, enemy)
        actor = session.player_combatants[0]
        allies = [mage]
        enemies = [enemy]

        log = []
        # Should not raise RecursionError
        session._resolve_skill(actor, "arcane_bolt", enemy, allies, enemies, log)
        assert mage.mp == 2  # unchanged


# ─────────────────────────────────────────────────────────────────────────────
# Cleric smite as default attack
# ─────────────────────────────────────────────────────────────────────────────

class TestClericSmiteDefault:
    def test_cleric_default_strategy_last_rule_is_smite(self, load_game_data):
        import json, os
        classes_path = os.path.join(DATA_DIR, "classes", "classes.json")
        with open(classes_path) as f:
            class_defs = json.load(f)

        last_strategy = class_defs["cleric"]["default_strategies"][-1]
        assert "smite" in last_strategy["action"].lower()

    def test_cleric_casts_smite_when_mp_available(self, load_game_data):
        """Cleric with smite unlocked and sufficient MP casts smite, not melee."""
        _load_skills()
        cleric = Character(name="Aldric", class_type="cleric", WIS=14)
        cleric.mp = 40       # smite costs 10
        cleric.max_mp = 45
        cleric.unlocked_skills = {"heal": 1, "smite": 1}
        cleric.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(cleric, enemy)
        actor = session.player_combatants[0]
        allies = [cleric]
        enemies = [enemy]

        hp_before = enemy.hp
        log = []
        session._resolve_skill(actor, "smite", enemy, allies, enemies, log)

        assert cleric.mp == 30  # 40 - 10
        assert enemy.hp < hp_before  # enemy took damage
        full_log = " ".join(log).lower()
        assert "smite" in full_log

    def test_cleric_falls_to_melee_when_mp_depleted(self, load_game_data):
        """Cleric with MP < smite cost falls to melee."""
        _load_skills()
        cleric = Character(name="Aldric", class_type="cleric", WIS=14)
        cleric.mp = 5        # smite costs 10
        cleric.max_mp = 45
        cleric.unlocked_skills = {"heal": 1, "smite": 1}
        cleric.status_effects = {}

        enemy = _make_enemy()
        session = _make_session(cleric, enemy)
        actor = session.player_combatants[0]
        allies = [cleric]
        enemies = [enemy]

        log = []
        session._resolve_skill(actor, "smite", enemy, allies, enemies, log)

        assert cleric.mp == 5   # unchanged — no spell cast
        full_log = " ".join(log).lower()
        assert "attacking instead" in full_log or "insufficient" in full_log