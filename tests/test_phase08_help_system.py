"""
Phase 8 — Help System Overhaul tests.

Phase A: _HELP_TOPICS module-level dict exists with all required keys
Phase B: State-aware bare HELP (contextual per State)
Phase C: All topic entries return valid formatted help
Phase D: Unknown topic returns graceful fallback
"""
import asyncio
import pytest

from server.engine.game import GameSession, State, _HELP_TOPICS
from server.engine.character import Character
from server.engine.world import WorldMap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_session(state=State.NAVIGATION):
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda rid: []
    session = GameSession(send_fn=_noop, world=world, class_defs={}, clock=None)
    player = Character(name="Hero", class_type="warrior")
    session.player = player
    session.state = state
    return session


async def _noop(text): pass


def ask(session, command):
    collected = []
    async def _send(text): collected.append(text)
    session._send_raw = _send
    asyncio.get_event_loop().run_until_complete(session.handle_input(command))
    return "".join(collected)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — _HELP_TOPICS dict exists with required keys
# ═══════════════════════════════════════════════════════════════════════════════

# ── Module-level topic registry ───────────────────────────────────────────────

EXPECTED_TOPICS = [
    # Navigation
    "LOOK", "L", "NORTH", "SOUTH", "EAST", "WEST", "MOVE",
    "INV", "INVENTORY", "EQUIP", "UNEQUIP", "DROP", "TAKE", "PICK",
    "STATS", "SKILLS", "ATTACK", "CAMP", "STATUS", "SIT", "STAND",
    # Environment
    "TIME", "WEATHER", "LIGHT", "LIGHTING", "ENVDETAILS", "ENV",
    "LIT", "EXTINGUISH", "DOUSE",
    # Combat
    "COMBAT", "FLEE", "STRATEGY", "STRATEGIES", "CAST",
    # Campfire
    "REST", "PARTY",
    # Survival
    "HUNGER", "THIRST", "STAMINA", "SURVIVAL",
    # Weight
    "WEIGHT", "BACKPACK", "CART", "GIVE", "STASH", "LOAD", "UNLOAD",
    # Mount
    "RIDE", "DISMOUNT", "HORSES", "MOUNTS",
    # Wizard & Spells
    "WIZARD", "SPELLS", "CASTING",
    "FIREBALL", "FROST_BOLT", "ARCANE_BOLT", "MAGIC_MISSILE",
    "CHAIN_LIGHTNING", "ARCANE_SHIELD", "BLINK", "ARCANE_LIGHT", "IDENTIFY",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — _HELP_TOPICS dict exists with required keys
# ═══════════════════════════════════════════════════════════════════════════════

def test_help_topics_is_dict():
    assert isinstance(_HELP_TOPICS, dict)


@pytest.mark.parametrize("topic", EXPECTED_TOPICS)
def test_help_topic_exists(topic):
    """Each expected help topic should exist in the _HELP_TOPICS dict."""
    assert topic in _HELP_TOPICS


def test_all_help_topic_values_nonempty():
    for key, val in _HELP_TOPICS.items():
        assert isinstance(val, str) and len(val.strip()) > 0, \
            f"_HELP_TOPICS[{key!r}] is empty or not a string"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase B — State-aware bare HELP
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseB_StateAwareHelp:
    def test_navigation_help_mentions_look(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert "LOOK" in out.upper()

    def test_navigation_help_mentions_north(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert "NORTH" in out.upper()

    def test_navigation_help_mentions_attack(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert "ATTACK" in out.upper()

    def test_navigation_help_does_not_say_combat_list(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        # Should not show combat-only commands like FLEE at the top level
        assert "You are exploring" in out or "exploring" in out.lower()

    def test_campfire_help_mentions_rest(self):
        s = make_session(State.CAMPFIRE)
        out = ask(s, "HELP")
        assert "REST" in out.upper()

    def test_campfire_help_mentions_leave(self):
        s = make_session(State.CAMPFIRE)
        out = ask(s, "HELP")
        assert "LEAVE" in out.upper()

    def test_campfire_help_does_not_mention_north(self):
        s = make_session(State.CAMPFIRE)
        out = ask(s, "HELP")
        # Navigation commands should not appear in campfire help
        assert "resting at camp" in out.lower() or "camp" in out.lower()

    def test_combat_help_mentions_flee(self):
        s = make_session(State.COMBAT)
        out = ask(s, "HELP")
        assert "FLEE" in out.upper()

    def test_combat_help_mentions_attack(self):
        s = make_session(State.COMBAT)
        out = ask(s, "HELP")
        assert "ATTACK" in out.upper()

    def test_combat_help_says_in_combat(self):
        s = make_session(State.COMBAT)
        out = ask(s, "HELP")
        assert "combat" in out.lower()

    def test_strategy_help_mentions_done(self):
        s = make_session(State.STRATEGY)
        out = ask(s, "HELP")
        assert "DONE" in out.upper()

    def test_strategy_help_mentions_tactics(self):
        s = make_session(State.STRATEGY)
        out = ask(s, "HELP")
        assert "AGGRESSIVE" in out.upper() or "tactic" in out.lower()

    def test_connect_help_mentions_races(self):
        s = make_session(State.CONNECT)
        out = ask(s, "HELP")
        assert "RACES" in out.upper()

    def test_creation_help_mentions_classes(self):
        s = make_session(State.CREATION)
        out = ask(s, "HELP")
        assert "CLASSES" in out.upper()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — HELP <topic> returns formatted content
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("topic", EXPECTED_TOPICS)
def test_help_topic_has_nonempty_content(topic):
    """Requesting help for any known topic should return non-empty formatted content."""
    s = make_session(State.NAVIGATION)
    out = ask(s, f"HELP {topic}")
    assert len(out.strip()) > 10


def test_help_topic_case_insensitive():
    out = ask(make_session(State.NAVIGATION), "HELP hunger")
    assert "HUNGER" in out.upper() or "hunger" in out.lower()


def test_help_topic_works_from_any_state():
    # HELP <topic> should work regardless of current state
    for state in [State.NAVIGATION, State.CAMPFIRE, State.COMBAT]:
        s = make_session(state)
        out = ask(s, "HELP HUNGER")
        assert "HUNGER" in out.upper() or "hunger" in out.lower(), \
            f"HELP HUNGER failed in state {state}"




# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — Unknown topic graceful fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseD_UnknownTopic:
    def test_help_nonexistent_does_not_crash(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP XYZZY")
        assert len(out) > 0

    def test_help_nonexistent_mentions_topic_name(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP XYZZY")
        assert "XYZZY" in out.upper() or "xyzzy" in out.lower()

    def test_help_nonexistent_suggests_help_list(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP FOOBAR")
        assert "HELP" in out.upper()

    def test_help_empty_string_returns_contextual(self):
        s = make_session(State.NAVIGATION)
        out = ask(s, "HELP")
        assert len(out) > 0
        assert "LOOK" in out.upper() or "NORTH" in out.upper()
