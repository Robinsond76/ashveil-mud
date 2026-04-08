"""
Phase 9 — Multiplayer Foundations tests.

Phase A: Session registry — GameSession accepts sessions dict
Phase B: Room occupancy — WorldMap enter/leave/players_in_room
Phase C: Broadcast helper — _broadcast_to_room sends to correct sessions
Phase D: Movement broadcasts — moves update occupancy and broadcast
Phase E: LOOK 'Also here' — other players listed in room description
Phase F: Item broadcasts — TAKE and DROP notify room occupants
Phase G: Chat commands — SAY, EMOTE/ME, SHOUT
"""
import asyncio
import pytest

from server.engine.game import GameSession, State
from server.engine.character import Character
from server.engine.world import WorldMap, Room


# ── Test helpers ──────────────────────────────────────────────────────────────

async def _noop(text):
    pass


def make_world_with_rooms():
    """Two rooms connected north/south."""
    world = WorldMap.__new__(WorldMap)
    world._rooms = {}
    world.room_occupants = {}
    room_a = Room(
        id="room_a",
        name="Room A",
        description="A test room.",
        exits={"north": "room_b"},
        item_ids=["iron_sword"],
        encounter_groups=[],
        recruitable_npc_ids=[],
    )
    room_b = Room(
        id="room_b",
        name="Room B",
        description="Another test room.",
        exits={"south": "room_a"},
        item_ids=[],
        encounter_groups=[],
        recruitable_npc_ids=[],
    )
    world._rooms["room_a"] = room_a
    world._rooms["room_b"] = room_b
    world.get_room = lambda rid: world._rooms.get(rid)
    world.active_encounter_groups = lambda rid: []
    return world


def make_session(name="Hero", room_id="room_a", sessions=None):
    world = make_world_with_rooms()
    if sessions is None:
        sessions = {}
    session = GameSession(
        send_fn=_noop,
        world=world,
        class_defs={},
        clock=None,
        sessions=sessions,
    )
    player = Character(name=name, class_type="warrior")
    session.player = player
    session.state = State.NAVIGATION
    session.current_room_id = room_id
    return session


def collect_output(session):
    """Override send to collect output; return getter."""
    collected = []
    async def _capture(text):
        collected.append(text)
    session._send_raw = _capture
    return collected


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — Session Registry
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseA_SessionRegistry:
    def test_gamesession_accepts_sessions_kwarg(self):
        sessions = {}
        session = make_session(sessions=sessions)
        assert session._sessions is sessions

    def test_gamesession_sessions_defaults_to_empty_dict_if_none(self):
        world = make_world_with_rooms()
        s = GameSession(send_fn=_noop, world=world, class_defs={}, clock=None)
        assert isinstance(s._sessions, dict)

    def test_sessions_can_hold_multiple_sessions(self):
        sessions = {}
        s1 = make_session(name="Aldric", sessions=sessions)
        s2 = make_session(name="Mira", sessions=sessions)
        sessions["Aldric"] = s1
        sessions["Mira"] = s2
        assert len(sessions) == 2
        assert sessions["Aldric"] is s1


# ═══════════════════════════════════════════════════════════════════════════════
# Phase B — Room Occupancy
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseB_RoomOccupancy:
    async def test_players_in_room_empty_initially(self):
        world = make_world_with_rooms()
        assert await world.players_in_room("room_a") == []

    async def test_enter_room_adds_player(self):
        world = make_world_with_rooms()
        await world.enter_room("Aldric", "room_a")
        assert "Aldric" in await world.players_in_room("room_a")

    async def test_enter_room_multiple_players(self):
        world = make_world_with_rooms()
        await world.enter_room("Aldric", "room_a")
        await world.enter_room("Mira", "room_a")
        occupants = await world.players_in_room("room_a")
        assert "Aldric" in occupants
        assert "Mira" in occupants

    async def test_leave_room_removes_player(self):
        world = make_world_with_rooms()
        await world.enter_room("Aldric", "room_a")
        await world.leave_room("Aldric", "room_a")
        assert "Aldric" not in await world.players_in_room("room_a")

    async def test_leave_room_nonexistent_player_is_safe(self):
        world = make_world_with_rooms()
        await world.leave_room("Ghost", "room_a")  # Should not raise

    async def test_leave_room_unknown_room_is_safe(self):
        world = make_world_with_rooms()
        await world.leave_room("Aldric", "void_room")  # Should not raise

    async def test_players_in_room_returns_copy(self):
        world = make_world_with_rooms()
        await world.enter_room("Aldric", "room_a")
        result = await world.players_in_room("room_a")
        result.append("Injected")
        assert "Injected" not in await world.players_in_room("room_a")

    async def test_enter_same_player_twice_appears_once(self):
        world = make_world_with_rooms()
        await world.enter_room("Aldric", "room_a")
        await world.enter_room("Aldric", "room_a")
        assert (await world.players_in_room("room_a")).count("Aldric") == 1

    async def test_players_in_different_rooms_isolated(self):
        world = make_world_with_rooms()
        await world.enter_room("Aldric", "room_a")
        await world.enter_room("Mira", "room_b")
        assert "Mira" not in await world.players_in_room("room_a")
        assert "Aldric" not in await world.players_in_room("room_b")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — Broadcast Helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseC_BroadcastHelper:
    def test_broadcast_sends_to_other_session_in_same_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_a", sessions=sessions)
        # Override s2's world to be the same as s1's so rooms match
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s2)
        run(s1._broadcast_to_room("Hello room!"))
        assert any("Hello room!" in m for m in received)

    def test_broadcast_exclude_self_true_skips_sender(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        sessions["Aldric"] = s1

        received = collect_output(s1)
        run(s1._broadcast_to_room("Test", exclude_self=True))
        assert not any("Test" in m for m in received)

    def test_broadcast_exclude_self_false_includes_sender(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        sessions["Aldric"] = s1

        received = collect_output(s1)
        run(s1._broadcast_to_room("Echo!", exclude_self=False))
        assert any("Echo!" in m for m in received)

    def test_broadcast_does_not_reach_different_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_b", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s2)
        run(s1._broadcast_to_room("Only for room_a"))
        assert not any("Only for room_a" in m for m in received)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — Movement Broadcasts
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseD_MovementBroadcasts:
    def _setup_two_players(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_a", sessions=sessions)
        s2.world = s1.world
        run(s1.world.enter_room("Aldric", "room_a"))
        run(s1.world.enter_room("Mira", "room_a"))
        sessions["Aldric"] = s1
        sessions["Mira"] = s2
        return s1, s2, sessions

    def test_move_updates_room_occupancy_leave(self):
        s1, s2, sessions = self._setup_two_players()
        s1.player.stamina = 100.0
        run(s1._do_move("north"))
        assert "Aldric" not in run(s1.world.players_in_room("room_a"))

    def test_move_updates_room_occupancy_enter(self):
        s1, s2, sessions = self._setup_two_players()
        s1.player.stamina = 100.0
        run(s1._do_move("north"))
        assert "Aldric" in run(s1.world.players_in_room("room_b"))

    def test_move_broadcasts_leaves_to_old_room(self):
        s1, s2, sessions = self._setup_two_players()
        s1.player.stamina = 100.0

        received_s2 = collect_output(s2)
        run(s1._do_move("north"))
        output = " ".join(received_s2)
        assert "Aldric" in output
        assert "north" in output.lower() or "heads" in output.lower()

    def test_move_broadcasts_arrives_to_new_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_b", sessions=sessions)
        s2.world = s1.world
        run(s1.world.enter_room("Aldric", "room_a"))
        run(s1.world.enter_room("Mira", "room_b"))
        sessions["Aldric"] = s1
        sessions["Mira"] = s2
        s1.player.stamina = 100.0

        received_s2 = collect_output(s2)
        run(s1._do_move("north"))
        output = " ".join(received_s2)
        assert "Aldric" in output
        assert "arrives" in output.lower() or "south" in output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase E — LOOK 'Also here'
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseE_LookAlsoHere:
    def test_look_shows_other_players_in_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_a", sessions=sessions)
        s2.world = s1.world
        run(s1.world.enter_room("Aldric", "room_a"))
        run(s1.world.enter_room("Mira", "room_a"))
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s1)
        run(s1._do_look())
        output = " ".join(received)
        assert "Mira" in output
        assert "Also here" in output

    def test_look_does_not_show_self_in_also_here(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        sessions["Aldric"] = s1
        run(s1.world.enter_room("Aldric", "room_a"))

        received = collect_output(s1)
        run(s1._do_look())
        # Should not show "Also here: Aldric"
        output = " ".join(received)
        if "Also here" in output:
            assert "Aldric" not in output.split("Also here")[1].split("\n")[0]

    def test_look_no_also_here_when_alone(self):
        s1 = make_session(name="Aldric", room_id="room_a")

        received = collect_output(s1)
        run(s1._do_look())
        output = " ".join(received)
        assert "Also here" not in output


# ═══════════════════════════════════════════════════════════════════════════════
# Phase F — Item Broadcasts
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseF_ItemBroadcasts:
    def test_take_broadcasts_to_room_occupants(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_a", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s2)
        run(s1.handle_input("TAKE iron sword"))
        output = " ".join(received)
        assert "Aldric" in output
        assert "picks up" in output.lower() or "pick" in output.lower()

    def test_drop_broadcasts_to_room_occupants(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_a", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2
        # Give s1 an item to drop
        s1.player.inventory.append("iron_sword")
        s1.world.get_room("room_a").item_ids.clear()

        received = collect_output(s2)
        run(s1.handle_input("DROP iron sword"))
        output = " ".join(received)
        assert "Aldric" in output
        assert "drops" in output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase G — Chat Commands
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseG_ChatCommands:
    def _two_players_same_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_a", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2
        return s1, s2

    # ── SAY ───────────────────────────────────────────────────────────────────

    def test_say_sender_sees_you_say(self):
        s1, s2 = self._two_players_same_room()
        received = collect_output(s1)
        run(s1.handle_input("SAY Hello traveler!"))
        output = " ".join(received)
        assert "You say" in output
        assert "Hello traveler!" in output

    def test_say_broadcasts_to_room_with_name(self):
        s1, s2 = self._two_players_same_room()
        received = collect_output(s2)
        run(s1.handle_input("SAY Hello traveler!"))
        output = " ".join(received)
        assert "Aldric" in output
        assert "Hello traveler!" in output

    def test_say_does_not_reach_other_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_b", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s2)
        run(s1.handle_input("SAY Secret message"))
        output = " ".join(received)
        assert "Secret message" not in output

    def test_say_requires_message_text(self):
        s1, _ = self._two_players_same_room()
        received = collect_output(s1)
        run(s1.handle_input("SAY"))
        output = " ".join(received)
        assert output  # some feedback returned

    # ── EMOTE / ME ────────────────────────────────────────────────────────────

    def test_emote_sender_sees_own_emote(self):
        s1, s2 = self._two_players_same_room()
        received = collect_output(s1)
        run(s1.handle_input("EMOTE waves cheerfully."))
        output = " ".join(received)
        assert "Aldric" in output
        assert "waves cheerfully" in output

    def test_emote_broadcasts_to_room(self):
        s1, s2 = self._two_players_same_room()
        received = collect_output(s2)
        run(s1.handle_input("EMOTE waves cheerfully."))
        output = " ".join(received)
        assert "Aldric" in output
        assert "waves cheerfully" in output

    def test_me_alias_works_like_emote(self):
        s1, s2 = self._two_players_same_room()
        received = collect_output(s2)
        run(s1.handle_input("ME bows deeply."))
        output = " ".join(received)
        assert "Aldric" in output
        assert "bows deeply" in output

    # ── SHOUT ────────────────────────────────────────────────────────────────

    def test_shout_reaches_different_room(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_b", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s2)
        run(s1.handle_input("SHOUT Is anyone at the inn?"))
        output = " ".join(received)
        assert "Aldric" in output
        assert "Is anyone at the inn?" in output

    def test_shout_sender_sees_confirmation(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        sessions["Aldric"] = s1
        received = collect_output(s1)
        run(s1.handle_input("SHOUT Testing!"))
        output = " ".join(received)
        assert "Testing!" in output

    def test_ooc_alias_works_like_shout(self):
        sessions = {}
        s1 = make_session(name="Aldric", room_id="room_a", sessions=sessions)
        s2 = make_session(name="Mira", room_id="room_b", sessions=sessions)
        s2.world = s1.world
        sessions["Aldric"] = s1
        sessions["Mira"] = s2

        received = collect_output(s2)
        run(s1.handle_input("OOC Global message"))
        output = " ".join(received)
        assert "Aldric" in output
        assert "Global message" in output


# ═══════════════════════════════════════════════════════════════════════════════
# Phase H — Help Entries
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseH_HelpEntries:
    def test_help_has_say_topic(self):
        from server.engine.game import _HELP_TOPICS
        assert "SAY" in _HELP_TOPICS

    def test_help_has_emote_topic(self):
        from server.engine.game import _HELP_TOPICS
        assert "EMOTE" in _HELP_TOPICS

    def test_help_has_shout_topic(self):
        from server.engine.game import _HELP_TOPICS
        assert "SHOUT" in _HELP_TOPICS

    def test_help_has_me_topic(self):
        from server.engine.game import _HELP_TOPICS
        assert "ME" in _HELP_TOPICS

    def test_help_has_players_topic(self):
        from server.engine.game import _HELP_TOPICS
        assert "PLAYERS" in _HELP_TOPICS

    def test_help_say_returns_text(self):
        from server.engine.game import _HELP_TOPICS
        assert _HELP_TOPICS["SAY"]

    def test_help_emote_returns_text(self):
        from server.engine.game import _HELP_TOPICS
        assert _HELP_TOPICS["EMOTE"]
