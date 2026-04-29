"""
Tests for chat commands: SAY, EMOTE (ME), SHOUT (OOC).
Covers T10 (untested commands): SAY, EMOTE, SHOUT have zero test coverage.
"""
import asyncio
import pytest

from server.engine.domain.character import Character
from server.engine.game import GameSession, State
from server.engine.world.map import WorldMap


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_world():
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.get_room = lambda rid: None
    world.active_encounter_groups = lambda rid: []
    return world


def _make_multiplayer_sessions():
    """Create two GameSessions sharing a sessions dict placed in the same room."""
    sessions = {}
    collected1 = []
    collected2 = []

    async def send1(text):
        collected1.append(text)

    async def send2(text):
        collected2.append(text)

    s1 = GameSession(send_fn=send1, world=_make_world(), class_defs={}, clock=None, sessions=sessions)
    s1.player = Character(name="Alice", class_type="warrior")
    s1.state = State.NAVIGATION
    s1.current_room_id = "town_square"
    s1._collected = collected1

    s2 = GameSession(send_fn=send2, world=_make_world(), class_defs={}, clock=None, sessions=sessions)
    s2.player = Character(name="Bob", class_type="mage")
    s2.state = State.NAVIGATION
    s2.current_room_id = "town_square"
    s2._collected = collected2

    sessions["Alice"] = s1
    sessions["Bob"] = s2

    return s1, s2, collected1, collected2


def _make_session_in_room(collected, sessions, room_id, name, class_type="warrior"):
    """Create a GameSession collecting output into the provided list."""
    async def send(text):
        collected.append(text)

    s = GameSession(send_fn=send, world=_make_world(), class_defs={}, clock=None, sessions=sessions)
    s.player = Character(name=name, class_type=class_type)
    s.state = State.NAVIGATION
    s.current_room_id = room_id
    return s


# ─── SAY ─────────────────────────────────────────────────────────────────────

def test_say_confirmation_shown_to_speaker():
    """SAY shows 'You say' confirmation to the speaker."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("SAY Hello everyone!"))
    output = "".join(c1)
    assert "you say" in output.lower()


def test_say_broadcasts_message_to_same_room():
    """SAY broadcasts the message to other players in the same room."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("SAY Hello everyone!"))
    output2 = "".join(c2)
    assert "Alice" in output2
    assert "Hello everyone!" in output2


def test_say_empty_message_shows_usage():
    """SAY with no text shows usage hint."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("SAY"))
    output = "".join(c1)
    assert "say" in output.lower()


def test_say_does_not_send_to_different_room():
    """SAY does not reach a player in a different room."""
    sessions = {}
    c1 = []
    c2 = []

    s1 = _make_session_in_room(c1, sessions, "town_square", "Alice")
    s2 = _make_session_in_room(c2, sessions, "forest_path", "Bob")
    sessions["Alice"] = s1
    sessions["Bob"] = s2

    _run(s1.handle_input("SAY Can you hear me?"))
    output2 = "".join(c2)
    assert "Can you hear me?" not in output2


# ─── EMOTE / ME ──────────────────────────────────────────────────────────────

def test_emote_broadcasts_action_to_room():
    """EMOTE broadcasts '* Alice <action>' to all players in the room."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("EMOTE waves hello"))
    output2 = "".join(c2)
    assert "Alice" in output2
    assert "waves hello" in output2


def test_emote_also_shown_to_speaker():
    """EMOTE (with exclude_self=False) is shown to the emoting player too."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("EMOTE bows deeply"))
    output1 = "".join(c1)
    assert "Alice" in output1
    assert "bows deeply" in output1


def test_me_alias_works_like_emote():
    """ME is an alias for EMOTE."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("ME nods thoughtfully"))
    output2 = "".join(c2)
    assert "Alice" in output2
    assert "nods thoughtfully" in output2


def test_emote_empty_message_shows_usage():
    """EMOTE with no text shows usage hint."""
    s1, s2, c1, c2 = _make_multiplayer_sessions()
    _run(s1.handle_input("EMOTE"))
    output = "".join(c1)
    assert "emote" in output.lower()


# ─── SHOUT / OOC ─────────────────────────────────────────────────────────────

def test_shout_broadcasts_to_all_sessions_across_rooms():
    """SHOUT reaches players in different rooms."""
    sessions = {}
    c1 = []
    c2 = []

    s1 = _make_session_in_room(c1, sessions, "town_square", "Alice")
    s2 = _make_session_in_room(c2, sessions, "forest_path", "Bob")
    sessions["Alice"] = s1
    sessions["Bob"] = s2

    _run(s1.handle_input("SHOUT Anyone out there?"))
    output2 = "".join(c2)
    assert "Alice" in output2
    assert "Anyone out there?" in output2


def test_shout_confirmation_shown_to_speaker():
    """SHOUT shows 'You shout' or similar confirmation to the shouter."""
    sessions = {}
    c1 = []
    s1 = _make_session_in_room(c1, sessions, "town_square", "Alice")
    sessions["Alice"] = s1

    _run(s1.handle_input("SHOUT Hello world!"))
    output = "".join(c1)
    assert "shout" in output.lower()


def test_shout_does_not_duplicate_to_shouter_via_session_loop():
    """Shouter should not receive an extra copy from the sessions loop."""
    sessions = {}
    c1 = []
    s1 = _make_session_in_room(c1, sessions, "town_square", "Alice")
    sessions["Alice"] = s1

    _run(s1.handle_input("SHOUT echo test"))
    # Count lines containing the message — should be exactly 1 (the confirmation)
    lines_with_msg = [t for t in c1 if "echo test" in t]
    assert len(lines_with_msg) == 1


def test_ooc_alias_works_like_shout():
    """OOC is an alias for SHOUT."""
    sessions = {}
    c1 = []
    c2 = []

    s1 = _make_session_in_room(c1, sessions, "town_square", "Alice")
    s2 = _make_session_in_room(c2, sessions, "forest_path", "Bob")
    sessions["Alice"] = s1
    sessions["Bob"] = s2

    _run(s1.handle_input("OOC testing 123"))
    output2 = "".join(c2)
    assert "testing 123" in output2


def test_shout_empty_message_shows_usage():
    """SHOUT with no text shows usage hint."""
    sessions = {}
    c1 = []
    s1 = _make_session_in_room(c1, sessions, "town_square", "Alice")
    sessions["Alice"] = s1

    _run(s1.handle_input("SHOUT"))
    output = "".join(c1)
    assert "shout" in output.lower()
