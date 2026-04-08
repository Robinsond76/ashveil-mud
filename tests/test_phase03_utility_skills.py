"""
Phase 3 — Utility Skills & Mana Rework: utility skills & USE command tests.
Tests (in order of plan phases):
  Phase C — Skill dataclass new fields and filter helpers
  Phase D — USE command behaviour
  Phase E — SKILLS UTILITY / SKILLS COMBAT / SKILLS filtering
"""
import asyncio
import pytest

from server.engine.character import Character
from server.engine.game import GameSession, State
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

DATA_DIR = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "server", "data"
)


def _load_skills_once():
    from server.engine.skills import _SKILL_REGISTRY
    if not _SKILL_REGISTRY:
        from server.engine.skills import load_skills
        load_skills(DATA_DIR)


def run(session, cmd):
    session._collected.clear()

    async def _send(text: str) -> None:
        session._collected.append(text)

    session._send_raw = _send
    asyncio.get_event_loop().run_until_complete(session.handle_input(cmd))
    return "".join(session._collected)


# ── Phase C: Skill dataclass new fields ──────────────────────────────────────

def test_skill_dataclass_has_use_context_field():
    """Skill dataclass must have use_context field defaulting to 'combat'."""
    from server.engine.skills import Skill
    s = Skill(
        id="test", name="Test", description="", class_type="warrior",
        mp_cost=0, cooldown_ticks=3, effect_type="damage"
    )
    assert s.use_context == "combat"


def test_skill_dataclass_has_stamina_cost_field():
    """Skill dataclass must have stamina_cost field defaulting to 0."""
    from server.engine.skills import Skill
    s = Skill(
        id="test", name="Test", description="", class_type="warrior",
        mp_cost=0, cooldown_ticks=3, effect_type="damage"
    )
    assert s.stamina_cost == 0


def test_skill_dataclass_has_required_items_field():
    """Skill dataclass must have required_items field defaulting to []."""
    from server.engine.skills import Skill
    s = Skill(
        id="test", name="Test", description="", class_type="warrior",
        mp_cost=0, cooldown_ticks=3, effect_type="damage"
    )
    assert s.required_items == []


def test_skill_dataclass_has_consumes_item_field():
    """Skill dataclass must have consumes_item field defaulting to False."""
    from server.engine.skills import Skill
    s = Skill(
        id="test", name="Test", description="", class_type="warrior",
        mp_cost=0, cooldown_ticks=3, effect_type="damage"
    )
    assert s.consumes_item is False


def test_get_utility_skills_returns_only_utility_skills():
    """get_utility_skills() returns only skills with use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_utility_skills
    utility = get_utility_skills("thief")
    assert all(s.use_context == "utility" for s in utility)
    assert len(utility) > 0


def test_get_combat_skills_returns_only_combat_skills():
    """get_combat_skills() returns only skills with use_context == 'combat'."""
    _load_skills_once()
    from server.engine.skills import get_combat_skills
    combat = get_combat_skills("thief")
    assert all(s.use_context == "combat" for s in combat)
    assert len(combat) > 0


def test_lockpick_skill_is_utility():
    """The lockpick skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("lockpick")
    assert skill is not None
    assert skill.use_context == "utility"


def test_detect_traps_skill_is_utility():
    """The detect_traps skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("detect_traps")
    assert skill is not None
    assert skill.use_context == "utility"


def test_arcane_light_skill_is_utility():
    """The arcane_light skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("arcane_light")
    assert skill is not None
    assert skill.use_context == "utility"


def test_identify_skill_is_utility():
    """The identify skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("identify")
    assert skill is not None
    assert skill.use_context == "utility"


def test_bless_camp_skill_is_utility():
    """The bless_camp skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("bless_camp")
    assert skill is not None
    assert skill.use_context == "utility"


def test_purify_food_skill_is_utility():
    """The purify_food skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("purify_food")
    assert skill is not None
    assert skill.use_context == "utility"


def test_fortify_skill_is_utility():
    """The fortify skill must have use_context == 'utility'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("fortify")
    assert skill is not None
    assert skill.use_context == "utility"


def test_existing_combat_skills_default_to_combat_context():
    """combat skills like backstab must default to use_context == 'combat'."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("backstab")
    assert skill is not None
    assert skill.use_context == "combat"


# ── Phase D: USE command — state guard ───────────────────────────────────────

def test_use_skill_blocked_in_combat_state(make_nav_session):
    """USE <skill> must be rejected when not in NAVIGATION state."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"lockpick": 1}
    s.player.inventory = ["lockpick"]
    s.state = State.COMBAT
    output = run(s, "USE lockpick")
    assert "cannot" in output.lower() and "utility skills" in output.lower()


def test_use_skill_blocked_in_campfire_state(make_nav_session):
    """USE <skill> must be rejected in CAMPFIRE state."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"lockpick": 1}
    s.player.inventory = ["lockpick"]
    s.state = State.CAMPFIRE
    output = run(s, "USE lockpick")
    assert "navigation" in output.lower()


# ── Phase D: USE command — skill validation ───────────────────────────────────

def test_use_unknown_skill_shows_error(make_nav_session):
    """USE with unknown skill ID shows error."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    output = run(s, "USE nonexistent_skill")
    assert "unknown skill" in output.lower()


def test_use_unlearned_skill_shows_error(make_nav_session):
    """USE with skill not unlocked by player shows error."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {}
    output = run(s, "USE lockpick")
    assert "haven't unlocked" in output.lower()


def test_use_combat_skill_with_use_command_shows_error(make_nav_session):
    """USE on a combat skill shows error (USE is only for utility skills)."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"backstab": 1}
    output = run(s, "USE backstab")
    assert "combat skill" in output.lower()


# ── Phase D: USE command — MP/stamina cost ────────────────────────────────────

def test_use_detect_traps_deducts_mp(make_nav_session):
    """USE detect_traps must deduct the skill's MP cost from the player."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("detect_traps")
    assert skill is not None

    s = make_nav_session(class_type="thief", mp=50)
    s.player.unlocked_skills = {"detect_traps": 1}
    run(s, "USE detect_traps")
    assert s.player.mp == 50 - skill.mp_cost


def test_use_detect_traps_blocked_without_enough_mp(make_nav_session):
    """USE detect_traps must be blocked if MP is insufficient."""
    _load_skills_once()
    s = make_nav_session(class_type="thief", mp=0)
    s.player.unlocked_skills = {"detect_traps": 1}
    output = run(s, "USE detect_traps")
    assert "not enough mana" in output.lower()


def test_use_lockpick_deducts_stamina(make_nav_session):
    """USE lockpick must deduct the skill's stamina_cost from the player."""
    _load_skills_once()
    from server.engine.skills import get_skill
    skill = get_skill("lockpick")
    assert skill is not None

    s = make_nav_session(class_type="thief", stamina=100.0)
    s.player.unlocked_skills = {"lockpick": 1}
    s.player.inventory = ["lockpick"]
    run(s, "USE lockpick")
    assert s.player.stamina == 100.0 - skill.stamina_cost


def test_use_lockpick_blocked_without_enough_stamina(make_nav_session):
    """USE lockpick must be blocked if stamina is insufficient."""
    _load_skills_once()
    s = make_nav_session(class_type="thief", stamina=0.0)
    s.player.unlocked_skills = {"lockpick": 1}
    s.player.inventory = ["lockpick"]
    output = run(s, "USE lockpick")
    assert "not enough stamina" in output.lower()


# ── Phase D: USE command — item requirements ─────────────────────────────────

def test_use_lockpick_blocked_without_lockpick_item(make_nav_session):
    """USE lockpick must be blocked if no lockpick item in party inventory."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"lockpick": 1}
    s.player.inventory = []   # no lockpick item
    output = run(s, "USE lockpick")
    assert "you need" in output.lower() and "lockpick" in output.lower()


def test_use_lockpick_succeeds_when_npc_party_member_has_lockpick(make_nav_session):
    """USE lockpick succeeds if a party NPC has a lockpick item."""
    _load_skills_once()
    from server.engine.npc import NPC
    s = make_nav_session(class_type="thief", stamina=100.0)
    s.player.unlocked_skills = {"lockpick": 1}
    s.player.inventory = []

    npc = NPC(name="Rogue", class_type="thief")
    npc.inventory = ["lockpick"]
    s.party = [npc]

    output = run(s, "USE lockpick")
    # should not show missing-item error
    assert "you need a lockpick" not in output.lower()


# ── Phase D: USE command — utility effects ───────────────────────────────────

def test_use_fortify_applies_party_damage_reduction(make_nav_session):
    """USE fortify must apply a fortify flag on the session until next combat."""
    _load_skills_once()
    s = make_nav_session(class_type="warrior", stamina=100.0)
    s.player.unlocked_skills = {"fortify": 1}
    run(s, "USE fortify")
    assert getattr(s, "_fortify_active", False) is True


def test_use_bless_camp_sets_bless_flag(make_nav_session):
    """USE bless_camp must set a flag reducing hunger drain for next rest."""
    _load_skills_once()
    s = make_nav_session(class_type="cleric", mp=50)
    s.player.unlocked_skills = {"bless_camp": 1}
    run(s, "USE bless_camp")
    assert getattr(s, "_bless_camp_active", False) is True


def test_use_arcane_light_sets_temporary_light_override(make_nav_session):
    """USE arcane_light must set a temporary light override on the session."""
    _load_skills_once()
    s = make_nav_session(class_type="mage", mp=50)
    s.player.unlocked_skills = {"arcane_light": 1}
    run(s, "USE arcane_light")
    assert getattr(s, "_arcane_light_until", None) is not None


# ── Phase E: SKILLS command filtering ────────────────────────────────────────

def test_skills_utility_shows_only_utility_skills(make_nav_session):
    """SKILLS UTILITY must list only utility skills."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"lockpick": 1, "detect_traps": 1, "backstab": 1}
    s.state = State.NAVIGATION
    output = run(s, "SKILLS UTILITY")
    assert "lockpick" in output.lower()
    assert "detect traps" in output.lower()
    assert "backstab" not in output.lower()


def test_skills_combat_shows_only_combat_skills(make_nav_session):
    """SKILLS COMBAT must list only combat skills."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"lockpick": 1, "detect_traps": 1, "backstab": 1}
    s.state = State.NAVIGATION
    output = run(s, "SKILLS COMBAT")
    assert "backstab" in output.lower()
    # utility skills should not appear
    assert "lockpick" not in output.lower()


def test_skills_bare_shows_both_sections(make_nav_session):
    """SKILLS (bare) must show both COMBAT and UTILITY sections."""
    _load_skills_once()
    s = make_nav_session(class_type="thief")
    s.player.unlocked_skills = {"lockpick": 1, "backstab": 1}
    s.state = State.NAVIGATION
    output = run(s, "SKILLS")
    assert "combat" in output.lower()
    assert "utility" in output.lower()
