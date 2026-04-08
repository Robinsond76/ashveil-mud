"""
Phase 6 — Horses & Mounts tests.

Phase A: horse item in misc.json
Phase B: GameSession mount state + helpers
Phase C: movement hook (auto-detach / auto-remount on room type change)
Phase D: combat auto-dismount / auto-remount
Phase E: RIDE, DISMOUNT, HORSES commands
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from server.engine.character import Character
from server.engine.items import get_item


# ── helpers ──────────────────────────────────────────────────────────────────

def make_char(name="Hero", cls="warrior", agi=10):
    return Character(name=name, class_type=cls, AGI=agi)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_session(world=None, send_fn=None, player=None, party=None):
    from server.engine.game import GameSession

    if send_fn is None:
        send_fn = AsyncMock()
    if world is None:
        world = MagicMock()
        world.get_room.return_value = None

    gs = GameSession(send_fn=send_fn, world=world, class_defs={})
    if player is not None:
        gs.player = player
    else:
        gs.player = make_char()
    if party is not None:
        gs.party = party
    return gs


def make_world_with_rooms(src_type="outdoor", dst_type="indoor"):
    """Return (world, src_room, dst_room) with basic mock setup."""
    world = MagicMock()
    src_room = MagicMock()
    src_room.id = "src_room"
    src_room.exits = {"north": "dst_room"}
    src_room.room_type = src_type
    src_room.item_ids = []
    src_room.recruitable_npc_ids = []
    src_room.base_temp_f = 70
    src_room.render = MagicMock(return_value="room desc\n")

    dst_room = MagicMock()
    dst_room.id = "dst_room"
    dst_room.room_type = dst_type
    dst_room.item_ids = []
    dst_room.recruitable_npc_ids = []
    dst_room.exits = {}
    dst_room.base_temp_f = 70
    dst_room.render = MagicMock(return_value="room desc\n")

    def get_room(rid):
        if rid == "src_room":
            return src_room
        if rid == "dst_room":
            return dst_room
        return None

    world.get_room.side_effect = get_room
    world.active_encounter_groups.return_value = []
    return world, src_room, dst_room


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — Horse item definition
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseA_HorseItem:
    def test_horse_item_exists(self):
        horse = get_item("horse")
        assert horse is not None

    def test_horse_item_name(self):
        horse = get_item("horse")
        assert horse.name == "Horse"

    def test_horse_type_is_mount(self):
        horse = get_item("horse")
        assert horse.type == "mount"

    def test_horse_effect_type_is_mount(self):
        horse = get_item("horse")
        assert horse.effect_type == "mount"

    def test_horse_stamina_reduction_is_sixty_percent(self):
        horse = get_item("horse")
        assert horse.effect_params.get("stamina_reduction") == 0.60

    def test_horse_outdoor_only_is_true(self):
        horse = get_item("horse")
        assert horse.effect_params.get("outdoor_only") is True

    def test_horse_weight_is_zero(self):
        horse = get_item("horse")
        assert horse.weight == 0

    def test_horse_value_is_200(self):
        horse = get_item("horse")
        assert horse.value == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Phase B — GameSession mount state + helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseB_MountState:
    def test_mounted_defaults_false(self):
        gs = make_session()
        assert gs._mounted is False

    def test_horses_outside_defaults_false(self):
        gs = make_session()
        assert gs._horses_outside is False

    def test_was_mounted_defaults_false(self):
        gs = make_session()
        assert gs._was_mounted is False


class TestPhaseB_HorseCount:
    def test_horse_count_zero_when_no_horses(self):
        gs = make_session()
        gs.player.inventory = []
        assert gs._horse_count() == 0

    def test_horse_count_one_when_player_has_horse(self):
        gs = make_session()
        gs.player.inventory = ["horse"]
        assert gs._horse_count() == 1

    def test_horse_count_two_when_player_has_two_horses(self):
        gs = make_session()
        gs.player.inventory = ["horse", "horse"]
        assert gs._horse_count() == 2

    def test_horse_count_includes_npc_inventory(self):
        gs = make_session()
        gs.player.inventory = ["horse"]
        npc = make_char("Gareth")
        npc.inventory = ["horse"]
        gs.party = [npc]
        assert gs._horse_count() == 2

    def test_horse_count_ignores_non_mount_items(self):
        gs = make_session()
        gs.player.inventory = ["torch", "lockpick", "horse"]
        assert gs._horse_count() == 1


class TestPhaseB_StaminaMultiplier:
    def test_multiplier_is_one_when_not_mounted(self):
        gs = make_session()
        gs._mounted = False
        gs.player.inventory = ["horse"]
        assert gs._stamina_multiplier() == 1.0

    def test_multiplier_is_full_reduction_when_one_horse_one_member(self):
        gs = make_session()
        gs._mounted = True
        gs.player.inventory = ["horse"]
        # ratio = min(1.0, 1/1) = 1.0 → multiplier = 1.0 - 0.60*1.0 = 0.40
        assert abs(gs._stamina_multiplier() - 0.40) < 1e-9

    def test_multiplier_scales_by_ratio(self):
        gs = make_session()
        gs._mounted = True
        gs.player.inventory = ["horse"]
        # party = player + 3 npcs = 4 members, 1 horse → ratio = 0.25
        for i in range(3):
            npc = make_char(f"NPC{i}")
            npc.inventory = []
            gs.party.append(npc)
        # ratio = min(1.0, 1/4) = 0.25 → multiplier = 1.0 - 0.60*0.25 = 0.85
        assert abs(gs._stamina_multiplier() - 0.85) < 1e-9

    def test_multiplier_caps_at_max_reduction_when_more_horses_than_members(self):
        gs = make_session()
        gs._mounted = True
        gs.player.inventory = ["horse", "horse", "horse"]
        # 3 horses, 1 member → ratio = min(1.0, 3/1) = 1.0 → multiplier = 0.40
        assert abs(gs._stamina_multiplier() - 0.40) < 1e-9

    def test_multiplier_zero_horses_gives_one(self):
        gs = make_session()
        gs._mounted = True
        gs.player.inventory = []
        # No horses, mounted (shouldn't happen logically but defensively: ratio=0 → mult=1.0)
        assert abs(gs._stamina_multiplier() - 1.0) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — Movement hook
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseC_MoveHook_Detach:
    def test_mounted_becomes_false_entering_indoor(self):
        world, _, _ = make_world_with_rooms("outdoor", "indoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        assert gs._mounted is False

    def test_horses_outside_becomes_true_entering_indoor(self):
        world, _, _ = make_world_with_rooms("outdoor", "indoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        assert gs._horses_outside is True

    def test_detach_message_printed_entering_indoor(self):
        world, src_room, _ = make_world_with_rooms("outdoor", "indoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs._mounted = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert "horses wait outside" in all_output.lower()

    def test_mounted_becomes_false_entering_underground(self):
        world, _, _ = make_world_with_rooms("outdoor", "underground")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        assert gs._mounted is False
        assert gs._horses_outside is True

    def test_no_detach_when_not_mounted(self):
        world, _, _ = make_world_with_rooms("outdoor", "indoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = False
        gs._horses_outside = False

        run(gs._do_move("north"))

        assert gs._mounted is False
        assert gs._horses_outside is False

    def test_no_detach_message_when_not_mounted(self):
        world, _, _ = make_world_with_rooms("outdoor", "indoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs._mounted = False

        run(gs._do_move("north"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert "horses wait outside" not in all_output.lower()


class TestPhaseC_MoveHook_Remount:
    def test_horses_outside_becomes_false_returning_to_outdoor(self):
        world, _, _ = make_world_with_rooms("indoor", "outdoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = False
        gs._horses_outside = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        assert gs._horses_outside is False

    def test_mounted_becomes_true_returning_to_outdoor(self):
        world, _, _ = make_world_with_rooms("indoor", "outdoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = False
        gs._horses_outside = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        assert gs._mounted is True

    def test_remount_message_printed(self):
        world, _, _ = make_world_with_rooms("indoor", "outdoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs._mounted = False
        gs._horses_outside = True
        gs.player.inventory = ["horse"]

        run(gs._do_move("north"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert "fall back into step" in all_output.lower()

    def test_no_remount_when_horses_not_outside(self):
        world, _, _ = make_world_with_rooms("indoor", "outdoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = False
        gs._horses_outside = False

        run(gs._do_move("north"))

        assert gs._mounted is False


class TestPhaseC_StaminaDrain:
    def test_stamina_drain_reduced_when_mounted(self):
        world, _, _ = make_world_with_rooms("outdoor", "outdoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = True
        gs.player.inventory = ["horse"]
        gs.player.stamina = 100.0

        run(gs._do_move("north"))

        # 1 horse, 1 party member → ratio=1.0 → multiplier=0.40 → drain = 2*0.40 = 0.80
        assert abs(gs.player.stamina - 99.20) < 0.01

    def test_stamina_drain_full_when_not_mounted(self):
        world, _, _ = make_world_with_rooms("outdoor", "outdoor")
        gs = make_session(world=world)
        gs.current_room_id = "src_room"
        gs._mounted = False
        gs.player.inventory = ["horse"]
        gs.player.stamina = 100.0

        run(gs._do_move("north"))

        assert abs(gs.player.stamina - 98.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — Combat auto-dismount / auto-remount
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseD_CombatDismount:
    def test_mounted_becomes_false_when_combat_starts(self):
        world = MagicMock()
        room = MagicMock()
        room.id = "outdoor_room"
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._mounted = True
        gs._was_mounted = False
        gs.current_room_id = "outdoor_room"

        from unittest.mock import patch
        with patch("server.engine.game.CombatSession") as MockCombat:
            mock_cs = MagicMock()
            from server.engine.actions import CombatResult as _CR
            mock_cs.run_and_get_result = AsyncMock(return_value=_CR(state='defeat', summary=[]))
            mock_cs.collect_rewards = MagicMock()
            MockCombat.return_value = mock_cs

            encounter_group = MagicMock()
            encounter_group.members = ["goblin"]

            with patch("server.engine.npc.spawn_npc") as mock_spawn:
                mock_npc = MagicMock()
                mock_spawn.return_value = mock_npc

                run(gs._start_combat(encounter_group))

        assert gs._mounted is False

    def test_was_mounted_set_true_when_combat_starts_mounted(self):
        world = MagicMock()
        room = MagicMock()
        room.id = "outdoor_room"
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._mounted = True
        gs._was_mounted = False
        gs.current_room_id = "outdoor_room"

        from unittest.mock import patch
        with patch("server.engine.game.CombatSession") as MockCombat:
            mock_cs = MagicMock()
            from server.engine.actions import CombatResult as _CR
            mock_cs.run_and_get_result = AsyncMock(return_value=_CR(state='defeat', summary=[]))
            mock_cs.collect_rewards = MagicMock()
            MockCombat.return_value = mock_cs

            encounter_group = MagicMock()
            encounter_group.members = ["goblin"]

            with patch("server.engine.npc.spawn_npc") as mock_spawn:
                mock_npc = MagicMock()
                mock_spawn.return_value = mock_npc

                run(gs._start_combat(encounter_group))

        assert gs._was_mounted is True

    def test_dismount_message_printed_when_combat_starts_mounted(self):
        world = MagicMock()
        room = MagicMock()
        room.id = "outdoor_room"
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs._mounted = True
        gs.current_room_id = "outdoor_room"

        from unittest.mock import patch
        with patch("server.engine.game.CombatSession") as MockCombat:
            mock_cs = MagicMock()
            from server.engine.actions import CombatResult as _CR
            mock_cs.run_and_get_result = AsyncMock(return_value=_CR(state='defeat', summary=[]))
            mock_cs.collect_rewards = MagicMock()
            MockCombat.return_value = mock_cs

            encounter_group = MagicMock()
            encounter_group.members = ["goblin"]

            with patch("server.engine.npc.spawn_npc") as mock_spawn:
                mock_npc = MagicMock()
                mock_spawn.return_value = mock_npc

                run(gs._start_combat(encounter_group))

        all_output = "".join(str(c.args[0]) for c in send_fn.call_args_list)
        assert "dismounts" in all_output.lower()

    def test_was_mounted_not_set_when_combat_starts_dismounted(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._mounted = False
        gs._was_mounted = False

        from unittest.mock import patch
        with patch("server.engine.game.CombatSession") as MockCombat:
            mock_cs = MagicMock()
            from server.engine.actions import CombatResult as _CR
            mock_cs.run_and_get_result = AsyncMock(return_value=_CR(state='defeat', summary=[]))
            mock_cs.collect_rewards = MagicMock()
            MockCombat.return_value = mock_cs

            encounter_group = MagicMock()
            encounter_group.members = ["goblin"]

            with patch("server.engine.game.spawn_npc") as mock_spawn:
                mock_npc = MagicMock()
                mock_spawn.return_value = mock_npc

                run(gs._start_combat(encounter_group))

        assert gs._was_mounted is False


class TestPhaseD_CombatRemount:
    def test_remounts_after_victory_in_outdoor_room(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._was_mounted = True
        gs._mounted = False
        gs.current_room_id = "outdoor_room"

        run(gs._end_combat_victory())

        assert gs._mounted is True
        assert gs._was_mounted is False

    def test_remount_message_printed_after_victory_in_outdoor(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        room.render.return_value = "room desc\n"
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs._was_mounted = True
        gs._mounted = False
        gs.current_room_id = "outdoor_room"

        run(gs._end_combat_victory())

        all_output = "".join(str(c.args[0]) for c in send_fn.call_args_list)
        assert "remounts" in all_output.lower()

    def test_no_remount_after_victory_in_indoor_room(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "indoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._was_mounted = True
        gs._mounted = False
        gs.current_room_id = "indoor_room"

        run(gs._end_combat_victory())

        assert gs._mounted is False
        assert gs._was_mounted is False

    def test_no_remount_after_victory_in_underground_room(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "underground"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._was_mounted = True
        gs._mounted = False
        gs.current_room_id = "dungeon_room"

        run(gs._end_combat_victory())

        assert gs._mounted is False
        assert gs._was_mounted is False

    def test_was_mounted_cleared_even_when_not_remounting(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "indoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        gs = make_session(world=world)
        gs._was_mounted = True
        gs._mounted = False

        run(gs._end_combat_victory())

        assert gs._was_mounted is False


# ═══════════════════════════════════════════════════════════════════════════════
# Phase E — RIDE, DISMOUNT, HORSES commands
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseE_RideCommand:
    def _make_outdoor_session(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        room.render = MagicMock(return_value="room desc\n")
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=AsyncMock(), world=world, class_defs={})
        gs.player = make_char()
        gs.state = State.NAVIGATION
        gs.current_room_id = "outdoor_room"
        return gs

    def _make_indoor_session(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "indoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=AsyncMock(), world=world, class_defs={})
        gs.player = make_char()
        gs.state = State.NAVIGATION
        gs.current_room_id = "indoor_room"
        return gs

    def test_ride_sets_mounted_true(self):
        gs = self._make_outdoor_session()
        gs.player.inventory = ["horse"]

        run(gs.handle_input("RIDE"))

        assert gs._mounted is True

    def test_ride_sends_confirmation_message(self):
        send_fn = AsyncMock()
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=send_fn, world=world, class_defs={})
        gs.player = make_char()
        gs.player.inventory = ["horse"]
        gs.state = State.NAVIGATION
        gs.current_room_id = "outdoor_room"

        run(gs.handle_input("RIDE"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert "mounts up" in all_output.lower()

    def test_ride_errors_when_no_horses(self):
        send_fn = AsyncMock()
        gs = self._make_outdoor_session()
        gs._send_raw = send_fn
        gs.player.inventory = []

        run(gs.handle_input("RIDE"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert gs._mounted is False
        assert "no horse" in all_output.lower() or "don't have" in all_output.lower()

    def test_ride_errors_when_not_outdoors(self):
        send_fn = AsyncMock()
        gs = self._make_indoor_session()
        gs._send_raw = send_fn
        gs.player.inventory = ["horse"]

        run(gs.handle_input("RIDE"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert gs._mounted is False
        assert "outdoor" in all_output.lower() or "outside" in all_output.lower()


class TestPhaseE_DismountCommand:
    def test_dismount_sets_mounted_false(self):
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=AsyncMock(), world=world, class_defs={})
        gs.player = make_char()
        gs.state = State.NAVIGATION
        gs._mounted = True

        run(gs.handle_input("DISMOUNT"))

        assert gs._mounted is False

    def test_dismount_sends_confirmation_message(self):
        send_fn = AsyncMock()
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=send_fn, world=world, class_defs={})
        gs.player = make_char()
        gs.state = State.NAVIGATION
        gs._mounted = True

        run(gs.handle_input("DISMOUNT"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert "dismount" in all_output.lower()


class TestPhaseE_HorsesCommand:
    def test_horses_command_shows_horse_count(self):
        send_fn = AsyncMock()
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=send_fn, world=world, class_defs={})
        gs.player = make_char()
        gs.player.inventory = ["horse", "horse"]
        gs.state = State.NAVIGATION

        run(gs.handle_input("HORSES"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        assert "2" in all_output

    def test_horses_command_shows_party_size(self):
        send_fn = AsyncMock()
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=send_fn, world=world, class_defs={})
        gs.player = make_char()
        gs.player.inventory = ["horse"]
        npc = make_char("Gareth")
        npc.inventory = []
        gs.party = [npc]
        gs.state = State.NAVIGATION

        run(gs.handle_input("HORSES"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        # party size = 2 (player + 1 npc)
        assert "2" in all_output

    def test_horses_command_shows_drain_reduction(self):
        send_fn = AsyncMock()
        world = MagicMock()
        room = MagicMock()
        room.room_type = "outdoor"
        room.item_ids = []
        room.recruitable_npc_ids = []
        room.base_temp_f = 70
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []

        from server.engine.game import GameSession, State
        gs = GameSession(send_fn=send_fn, world=world, class_defs={})
        gs.player = make_char()
        gs.player.inventory = ["horse"]
        gs.state = State.NAVIGATION
        gs._mounted = True

        run(gs.handle_input("HORSES"))

        all_output = "".join(c.args[0] for c in send_fn.call_args_list)
        # 1 horse, 1 member → 60% reduction
        assert "60" in all_output or "-60" in all_output
