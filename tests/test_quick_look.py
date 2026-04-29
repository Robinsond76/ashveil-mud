"""Tests for Quick Look feature with LOOKMODE and BATTLELOOK toggles."""

import pytest

from server.engine.domain.character import Character
from server.engine.world import Room, EncounterGroup


class TestCharacterPreferences:
    """Test Character preference fields."""

    def test_character_has_look_mode_default_full(self):
        """Character defaults to FULL look mode."""
        char = Character(name="test", class_type="warrior")
        assert char.look_mode == "FULL"

    def test_character_has_battle_look_default_true(self):
        """Character defaults to battle_look True."""
        char = Character(name="test", class_type="warrior")
        assert char.battle_look is True

    def test_character_preferences_persist_in_dict(self):
        """Preferences are saved in to_dict output."""
        char = Character(name="test", class_type="warrior")
        char.look_mode = "QUICK"
        char.battle_look = False

        data = char.to_dict()
        assert data["look_mode"] == "QUICK"
        assert data["battle_look"] is False

    def test_character_preferences_load_from_dict(self):
        """Preferences are loaded from dict correctly."""
        char = Character.from_dict({
            "name": "test",
            "class_type": "warrior",
            "look_mode": "QUICK",
            "battle_look": False,
        })
        assert char.look_mode == "QUICK"
        assert char.battle_look is False

    def test_character_preferences_backward_compatible(self):
        """Old saves without preferences default correctly."""
        char = Character.from_dict({
            "name": "test",
            "class_type": "warrior",
        })
        assert char.look_mode == "FULL"
        assert char.battle_look is True


class TestRoomRenderQuick:
    """Test Room.render_quick method."""

    def _make_room(self, **overrides):
        """Helper to create a room with defaults."""
        defaults = dict(
            id="test_room",
            name="Test Room",
            description="A test room.",
            exits={"north": "room2", "east": "room3"},
            item_ids=[],
            encounter_groups=[],
            recruitable_npc_ids=[],
        )
        defaults.update(overrides)
        return Room(**defaults)

    def test_render_quick_shows_room_name(self):
        """Quick look shows room name."""
        room = self._make_room()
        output = room.render_quick({}, [], [], [])
        assert "TEST ROOM" in output
        assert "[Exits:" in output

    def test_render_quick_shows_exits(self):
        """Quick look shows available exits."""
        room = self._make_room(exits={"north": "room2", "east": "room3"})
        output = room.render_quick({}, [], [], [])
        assert "EAST" in output
        assert "NORTH" in output

    def test_render_quick_shows_items_in_green(self):
        """Items are shown in green color code."""
        room = self._make_room(item_ids=["sword", "potion"])
        item_names = {"sword": "Iron Sword", "potion": "Health Potion"}
        output = room.render_quick(item_names, [], [], [])
        assert "Items:" in output
        assert "\x1b[32mIron Sword\x1b[0m" in output
        assert "\x1b[32mHealth Potion\x1b[0m" in output

    def test_render_quick_shows_hostiles_in_red(self):
        """Hostiles are shown in red color code."""
        room = self._make_room()
        encounter_summary = ["wolves", "bandits"]
        output = room.render_quick({}, [], encounter_summary, [])
        assert "Hostiles:" in output
        assert "\x1b[31m" in output

    def test_render_quick_shows_npcs_in_yellow(self):
        """NPCs are shown in yellow color code."""
        room = self._make_room()
        npc_flavors = ["Gareth the Blacksmith works at his forge."]
        output = room.render_quick({}, npc_flavors, [], [])
        assert "\x1b[33m" in output

    def test_render_quick_shows_players_in_blue(self):
        """Other players are shown in blue color code."""
        room = self._make_room()
        other_players = ["Alice", "Bob"]
        output = room.render_quick({}, [], [], other_players)
        assert "Also here:" in output
        assert "\x1b[34mAlice\x1b[0m" in output
        assert "\x1b[34mBob\x1b[0m" in output

    def test_render_quick_shows_nothing_note_when_empty(self):
        """Shows 'nothing of note' when room is empty and has no interesting content."""
        room = self._make_room(
            exits={"east": "room2"},
            item_ids=[],
            encounter_groups=[],
            recruitable_npc_ids=[],
        )
        output = room.render_quick({}, [], [], [])
        assert "(nothing of note)" in output

    def test_render_quick_nothing_note_with_exits_only(self):
        """Room with just exits but nothing else shows nothing of note."""
        room = self._make_room(exits={"north": "room2"})
        output = room.render_quick({}, [], [], [])
        assert "(nothing of note)" in output

    def test_render_quick_no_nothing_note_with_items(self):
        """Room with items doesn't show 'nothing of note'."""
        room = self._make_room(item_ids=["sword"])
        item_names = {"sword": "Iron Sword"}
        output = room.render_quick(item_names, [], [], [])
        assert "(nothing of note)" not in output

    def test_render_quick_no_exits(self):
        """Room with no exits shows 'none' for exits."""
        room = self._make_room(exits={})
        output = room.render_quick({}, [], [], [])
        assert "none" in output


class TestLookModeCommand:
    """Test LOOKMODE command handler."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock GameSession for testing commands."""
        from unittest.mock import AsyncMock, MagicMock

        session = MagicMock()
        session.player = Character(name="test", class_type="warrior")
        session.output = []

        async def mock_send(text):
            session.output.append(text)

        session.send = AsyncMock(side_effect=mock_send)
        session._send = AsyncMock(side_effect=mock_send)
        return session

    @pytest.mark.asyncio
    async def test_lookmode_shows_current_mode(self, mock_session):
        """LOOKMODE without args shows current mode."""
        from server.engine.states.navigation import NavigationHandler
        mock_session.player.look_mode = "FULL"
        handler = NavigationHandler()

        await handler._do_lookmode(mock_session, "")

        output = "".join([str(call) for call in mock_session.send.call_args_list])
        assert "Current look mode: FULL" in output

    @pytest.mark.asyncio
    async def test_lookmode_sets_full(self, mock_session):
        """LOOKMODE FULL sets mode to FULL."""
        from server.engine.states.navigation import NavigationHandler
        mock_session.player.look_mode = "QUICK"
        handler = NavigationHandler()

        await handler._do_lookmode(mock_session, "FULL")

        assert mock_session.player.look_mode == "FULL"

    @pytest.mark.asyncio
    async def test_lookmode_sets_quick(self, mock_session):
        """LOOKMODE QUICK sets mode to QUICK."""
        from server.engine.states.navigation import NavigationHandler
        mock_session.player.look_mode = "FULL"
        handler = NavigationHandler()

        await handler._do_lookmode(mock_session, "QUICK")

        assert mock_session.player.look_mode == "QUICK"

    @pytest.mark.asyncio
    async def test_lookmode_invalid_shows_usage(self, mock_session):
        """Invalid LOOKMODE argument shows usage."""
        from server.engine.states.navigation import NavigationHandler
        handler = NavigationHandler()

        await handler._do_lookmode(mock_session, "INVALID")

        output = "".join([str(call) for call in mock_session.send.call_args_list])
        assert "Usage" in output


class TestBattleLookCommand:
    """Test BATTLELOOK command handler."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock GameSession for testing commands."""
        from unittest.mock import AsyncMock, MagicMock

        session = MagicMock()
        session.player = Character(name="test", class_type="warrior")
        session.output = []

        async def mock_send(text):
            session.output.append(text)

        session.send = AsyncMock(side_effect=mock_send)
        session._send = AsyncMock(side_effect=mock_send)
        return session

    @pytest.mark.asyncio
    async def test_battlelook_shows_current_status_on(self, mock_session):
        """BATTLELOOK without args shows ON when enabled."""
        from server.engine.states.navigation import NavigationHandler
        mock_session.player.battle_look = True
        handler = NavigationHandler()

        await handler._do_battlelook(mock_session, "")

        output = "".join([str(call) for call in mock_session.send.call_args_list])
        assert "Battle look is ON" in output

    @pytest.mark.asyncio
    async def test_battlelook_sets_on(self, mock_session):
        """BATTLELOOK ON enables battle look."""
        from server.engine.states.navigation import NavigationHandler
        mock_session.player.battle_look = False
        handler = NavigationHandler()

        await handler._do_battlelook(mock_session, "ON")

        assert mock_session.player.battle_look is True

    @pytest.mark.asyncio
    async def test_battlelook_sets_off(self, mock_session):
        """BATTLELOOK OFF disables battle look."""
        from server.engine.states.navigation import NavigationHandler
        mock_session.player.battle_look = True
        handler = NavigationHandler()

        await handler._do_battlelook(mock_session, "OFF")

        assert mock_session.player.battle_look is False

    @pytest.mark.asyncio
    async def test_battlelook_invalid_shows_usage(self, mock_session):
        """Invalid BATTLELOOK argument shows usage."""
        from server.engine.states.navigation import NavigationHandler
        handler = NavigationHandler()

        await handler._do_battlelook(mock_session, "INVALID")

        output = "".join([str(call) for call in mock_session.send.call_args_list])
        assert "Usage" in output