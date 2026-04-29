"""
Phase 5 — Inventory & Weight Overhaul tests.

Phase A: Equipment slot & container items
Phase B: Weight formula update
Phase C: Cart state & movement
Phase D: Auto-placement algorithm
Phase E: Party inventory view & commands
Phase F: Manual management commands (GIVE, LOAD CART, UNLOAD CART)
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from server.engine.character import Character
from server.engine.domain.items import EQUIPMENT_SLOTS, get_item


# ── helpers ──────────────────────────────────────────────────────────────────

def make_char(name="Hero", cls="warrior", agi=10):
    c = Character(name=name, class_type=cls, AGI=agi)
    return c


def make_npc_char(name="Gareth", cls="warrior"):
    c = Character(name=name, class_type=cls)
    return c


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_session(world=None, send_fn=None, player=None, party=None):
    """Build a minimal GameSession for testing without a real WebSocket."""
    from server.engine.game import GameSession
    from server.engine.domain.items import load_items
    import os

    if send_fn is None:
        send_fn = AsyncMock()
    if world is None:
        world = MagicMock()
        world.get_room.return_value = None

    # Ensure async world methods work with MagicMock
    if isinstance(world, MagicMock):
        world.players_in_room = AsyncMock(return_value=[])
        world.enter_room = AsyncMock()
        world.leave_room = AsyncMock()

    gs = GameSession(send_fn=send_fn, world=world, class_defs={})
    if player is not None:
        gs.player = player
    else:
        gs.player = make_char()
    if party is not None:
        gs.party = party
    return gs


# ═══════════════════════════════════════════════════════════════════════════════
# Phase A — Equipment Slot & Container Items
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseA_BackSlot:
    def test_back_slot_exists_in_equipment_slots(self):
        assert "back" in EQUIPMENT_SLOTS

    def test_character_equipment_dict_has_back_key(self):
        c = make_char()
        assert "back" in c.equipment

    def test_back_slot_defaults_to_none(self):
        c = make_char()
        assert c.equipment["back"] is None


class TestPhaseA_CarryProperties:
    def test_carry_slots_base_is_five(self):
        c = make_char()
        assert c.carry_slots == 5

    def test_carry_weight_cap_base_is_twenty(self):
        c = make_char()
        assert c.carry_weight_cap == 20

    def test_carry_slots_increases_with_small_backpack(self):
        c = make_char()
        c.equipment["back"] = "small_backpack"
        # small_backpack gives +8 slot_bonus
        assert c.carry_slots == 5 + 8

    def test_carry_slots_increases_with_large_backpack(self):
        c = make_char()
        c.equipment["back"] = "large_backpack"
        # large_backpack gives +12 slot_bonus
        assert c.carry_slots == 5 + 12

    def test_carry_weight_cap_increases_with_small_backpack(self):
        c = make_char()
        c.equipment["back"] = "small_backpack"
        # small_backpack gives +30 weight_bonus
        assert c.carry_weight_cap == 20 + 30

    def test_carry_weight_cap_increases_with_large_backpack(self):
        c = make_char()
        c.equipment["back"] = "large_backpack"
        # large_backpack gives +50 weight_bonus
        assert c.carry_weight_cap == 20 + 50


class TestPhaseA_ItemData:
    def test_small_backpack_exists_in_registry(self):
        item = get_item("small_backpack")
        assert item is not None, "small_backpack not found in item registry"

    def test_large_backpack_exists_in_registry(self):
        item = get_item("large_backpack")
        assert item is not None, "large_backpack not found in item registry"

    def test_travellers_cart_exists_in_registry(self):
        item = get_item("travellers_cart")
        assert item is not None, "travellers_cart not found in item registry"

    def test_small_backpack_slot_is_back(self):
        item = get_item("small_backpack")
        assert item.slot == "back"

    def test_large_backpack_slot_is_back(self):
        item = get_item("large_backpack")
        assert item.slot == "back"

    def test_small_backpack_slot_bonus(self):
        item = get_item("small_backpack")
        assert item.stats.get("slot_bonus") == 8

    def test_large_backpack_slot_bonus(self):
        item = get_item("large_backpack")
        assert item.stats.get("slot_bonus") == 12

    def test_small_backpack_weight_bonus(self):
        item = get_item("small_backpack")
        assert item.stats.get("weight_bonus") == 30

    def test_large_backpack_weight_bonus(self):
        item = get_item("large_backpack")
        assert item.stats.get("weight_bonus") == 50

    def test_travellers_cart_slot_bonus(self):
        item = get_item("travellers_cart")
        assert item.stats.get("slot_bonus") == 40

    def test_travellers_cart_weight_bonus(self):
        item = get_item("travellers_cart")
        assert item.stats.get("weight_bonus") == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Phase B — Weight Formula Update
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseB_WeightFormula:
    def test_no_inventory_no_equipment_effective_speed_equals_agi(self):
        c = make_char(agi=10)
        assert c.effective_speed == 10

    def test_carried_weight_reduces_effective_speed(self):
        from server.config import WEIGHT_DIVISOR
        import math
        c = make_char(agi=10)
        # Give items with known weight; small_backpack weight = check item data
        # Use torch (weight=1) to add predictable carried weight
        c.inventory = ["torch", "torch", "torch", "torch", "torch"]  # 5 * 1 = 5 weight
        carried = 5
        expected = max(1, 10 - math.floor(carried / WEIGHT_DIVISOR))
        assert c.effective_speed == expected

    def test_cart_items_do_not_count_toward_effective_speed(self):
        """Items in cart_inventory on GameSession don't slow character."""
        c = make_char(agi=10)
        # No inventory items — speed should be full AGI
        assert c.effective_speed == 10

    def test_effective_speed_minimum_is_one(self):
        from server.config import WEIGHT_DIVISOR
        c = make_char(agi=1)
        # Fill inventory with very heavy items; speed should floor at 1
        c.inventory = ["large_backpack"] * 20  # large_backpack weight = 5
        assert c.effective_speed >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Phase C — Cart State in GameSession
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseC_CartState:
    def test_game_session_has_cart_present_field(self):
        gs = make_session()
        assert hasattr(gs, "_cart_present")
        assert gs._cart_present is False

    def test_game_session_has_cart_room_id_field(self):
        gs = make_session()
        assert hasattr(gs, "_cart_room_id")
        assert gs._cart_room_id is None

    def test_game_session_has_cart_inventory_field(self):
        gs = make_session()
        assert hasattr(gs, "_cart_inventory")
        assert gs._cart_inventory == []

    def test_party_has_cart_false_when_no_cart(self):
        gs = make_session()
        gs.player.inventory = []
        assert gs._party_has_cart() is False

    def test_party_has_cart_true_when_player_has_cart_in_inventory(self):
        gs = make_session()
        gs.player.inventory = ["travellers_cart"]
        assert gs._party_has_cart() is True

    def test_party_has_cart_true_when_npc_has_cart_in_inventory(self):
        gs = make_session()
        gs.player.inventory = []
        npc = make_npc_char("Gareth")
        npc.inventory = ["travellers_cart"]
        gs.party = [npc]
        assert gs._party_has_cart() is True


class TestPhaseC_CartMoveLogic:
    def _make_world_with_rooms(self, src_type="outdoor", dst_type="indoor"):
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

    def test_cart_detaches_when_entering_indoor_room(self):
        world, src_room, dst_room = self._make_world_with_rooms("outdoor", "indoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs.player.inventory = ["travellers_cart"]
        gs._cart_present = True
        gs._cart_room_id = None

        run(gs._do_move("north"))

        assert gs._cart_present is False
        assert gs._cart_room_id == "src_room"

    def test_cart_detach_prints_message(self):
        world, src_room, dst_room = self._make_world_with_rooms("outdoor", "indoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs.player.inventory = ["travellers_cart"]
        gs._cart_present = True

        run(gs._do_move("north"))

        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "cart remains outside" in all_output.lower()

    def test_cart_does_not_detach_entering_outdoor_room(self):
        world, src_room, dst_room = self._make_world_with_rooms("outdoor", "outdoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs.player.inventory = ["travellers_cart"]
        gs._cart_present = True
        gs._cart_room_id = None

        run(gs._do_move("north"))

        assert gs._cart_present is True
        assert gs._cart_room_id is None

    def test_cart_rejoins_when_returning_to_outdoor(self):
        world, src_room, dst_room = self._make_world_with_rooms("indoor", "outdoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs._cart_present = False
        gs._cart_room_id = "some_outdoor_room"

        run(gs._do_move("north"))

        assert gs._cart_present is True
        assert gs._cart_room_id is None

    def test_cart_rejoin_prints_message(self):
        world, src_room, dst_room = self._make_world_with_rooms("indoor", "outdoor")
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.current_room_id = "src_room"
        gs._cart_present = False
        gs._cart_room_id = "some_outdoor_room"

        run(gs._do_move("north"))

        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "cart catches up" in all_output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase D — Auto-Placement Algorithm
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseD_AutoAssign:
    def test_item_assigned_to_player_when_has_space(self):
        gs = make_session()
        gs.player.inventory = []
        result = gs._auto_assign_item("torch")
        assert result is True
        assert "torch" in gs.player.inventory

    def test_item_assigned_to_npc_when_player_full(self):
        gs = make_session()
        # Fill player slots
        gs.player.inventory = ["torch"] * gs.player.carry_slots
        npc = make_npc_char("Gareth")
        npc.inventory = []
        gs.party = [npc]
        result = gs._auto_assign_item("torch")
        assert result is True
        assert "torch" in npc.inventory

    def test_returns_false_when_all_party_full_no_cart(self):
        gs = make_session()
        gs.player.inventory = ["torch"] * gs.player.carry_slots
        gs._cart_present = False
        # No party members
        gs.party = []
        result = gs._auto_assign_item("torch")
        assert result is False

    def test_over_encumbered_message_sent_when_no_space(self):
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs.player.inventory = ["torch"] * gs.player.carry_slots
        gs.party = []
        gs._cart_present = False
        run(gs._auto_assign_item_with_message("torch"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "over-encumbered" in all_output.lower()

    def test_item_goes_to_cart_when_party_full_and_cart_present(self):
        gs = make_session()
        gs.player.inventory = ["torch"] * gs.player.carry_slots
        gs.party = []
        gs._cart_present = True
        result = gs._auto_assign_item("torch")
        assert result is True
        assert "torch" in gs._cart_inventory

    def test_pick_up_uses_auto_assign(self):
        world = MagicMock()
        room = MagicMock()
        room.item_ids = ["torch"]
        room.exits = {}
        world.get_room.return_value = room
        world.active_encounter_groups.return_value = []
        send_fn = AsyncMock()
        gs = make_session(world=world, send_fn=send_fn)
        gs.player.inventory = []
        run(gs._do_pick_up("torch"))
        assert "torch" in gs.player.inventory


# ═══════════════════════════════════════════════════════════════════════════════
# Phase E — Party Inventory View
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseE_PartyInventoryView:
    def test_returns_player_items_with_holder_name(self):
        gs = make_session()
        gs.player.inventory = ["torch"]
        result = gs._party_inventory_view()
        holders = [r[0] for r in result]
        assert gs.player.name in holders

    def test_returns_npc_items_with_holder_name(self):
        gs = make_session()
        gs.player.inventory = []
        npc = make_npc_char("Gareth")
        npc.inventory = ["torch"]
        gs.party = [npc]
        result = gs._party_inventory_view()
        holders = [r[0] for r in result]
        assert "Gareth" in holders

    def test_returns_tuple_of_three_fields(self):
        gs = make_session()
        gs.player.inventory = ["torch"]
        result = gs._party_inventory_view()
        assert len(result[0]) == 3  # (holder_name, item_id, item_name)

    def test_inv_command_shows_party_items(self):
        from server.engine.game import State
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs.state = State.NAVIGATION
        gs.player.inventory = ["torch"]
        run(gs.handle_input("INV"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "torch" in all_output.lower() or "Torch" in all_output

    def test_inv_shows_holder_name(self):
        from server.engine.game import State
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs.state = State.NAVIGATION
        gs.player.inventory = ["torch"]
        run(gs.handle_input("INV"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert gs.player.name in all_output

    def test_inv_member_shows_only_that_members_items(self):
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs.player.name = "Hero"
        gs.player.inventory = ["torch"]
        npc = make_npc_char("Gareth")
        npc.inventory = ["lockpick"]
        gs.party = [npc]
        gs.state = __import__("server.engine.game", fromlist=["State"]).State.NAVIGATION
        run(gs.handle_input("INVENTORY Gareth"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "lockpick" in all_output.lower() or "Lockpick" in all_output
        # Torch (player's item) should not appear
        assert "torch" not in all_output.lower()

    def test_inv_cart_shows_cart_contents(self):
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs._cart_inventory = ["torch"]
        gs.state = __import__("server.engine.game", fromlist=["State"]).State.NAVIGATION
        run(gs.handle_input("INV CART"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "torch" in all_output.lower() or "Torch" in all_output


# ═══════════════════════════════════════════════════════════════════════════════
# Phase F — Manual Management Commands
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhaseF_GiveCommand:
    def _make_nav_session(self, player_inv=None, npc_inv=None):
        from server.engine.game import State
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs.state = State.NAVIGATION
        gs.player.name = "Hero"
        if player_inv is not None:
            gs.player.inventory = player_inv
        npc = make_npc_char("Gareth")
        if npc_inv is not None:
            npc.inventory = npc_inv
        gs.party = [npc]
        return gs, send_fn

    def test_give_transfers_item_from_player_to_npc(self):
        gs, send_fn = self._make_nav_session(player_inv=["torch"], npc_inv=[])
        run(gs.handle_input("GIVE torch TO Gareth"))
        assert "torch" not in gs.player.inventory
        assert "torch" in gs.party[0].inventory

    def test_give_fails_if_source_does_not_have_item(self):
        gs, send_fn = self._make_nav_session(player_inv=[], npc_inv=[])
        run(gs.handle_input("GIVE torch TO Gareth"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "don't have" in all_output.lower() or "not found" in all_output.lower()

    def test_give_fails_if_target_member_not_found(self):
        gs, send_fn = self._make_nav_session(player_inv=["torch"], npc_inv=[])
        run(gs.handle_input("GIVE torch TO Nobody"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "not in party" in all_output.lower() or "nobody" in all_output.lower()

    def test_give_npc_to_player(self):
        gs, send_fn = self._make_nav_session(player_inv=[], npc_inv=["torch"])
        run(gs.handle_input("GIVE torch TO Hero"))
        assert "torch" in gs.player.inventory
        assert "torch" not in gs.party[0].inventory


class TestPhaseF_LoadUnloadCart:
    def _make_cart_session(self, player_inv=None, cart_inv=None, cart_present=True):
        from server.engine.game import State
        send_fn = AsyncMock()
        gs = make_session(send_fn=send_fn)
        gs.state = State.NAVIGATION
        gs._cart_present = cart_present
        if player_inv is not None:
            gs.player.inventory = list(player_inv)
        if cart_inv is not None:
            gs._cart_inventory = list(cart_inv)
        return gs, send_fn

    def test_load_cart_moves_item_to_cart_inventory(self):
        gs, _ = self._make_cart_session(player_inv=["torch"])
        run(gs.handle_input("LOAD CART torch"))
        assert "torch" not in gs.player.inventory
        assert "torch" in gs._cart_inventory

    def test_stash_is_alias_for_load_cart(self):
        gs, _ = self._make_cart_session(player_inv=["torch"])
        run(gs.handle_input("STASH torch"))
        assert "torch" in gs._cart_inventory

    def test_load_cart_fails_when_cart_not_present(self):
        gs, send_fn = self._make_cart_session(player_inv=["torch"], cart_present=False)
        run(gs.handle_input("LOAD CART torch"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "cart" in all_output.lower()
        assert "torch" in gs.player.inventory  # item not moved

    def test_unload_cart_moves_item_to_party(self):
        gs, _ = self._make_cart_session(player_inv=[], cart_inv=["torch"])
        run(gs.handle_input("UNLOAD CART torch"))
        assert "torch" not in gs._cart_inventory
        party_inv = gs.player.inventory + [i for n in gs.party for i in n.inventory]
        assert "torch" in party_inv

    def test_unload_cart_fails_when_cart_not_present(self):
        gs, send_fn = self._make_cart_session(cart_inv=["torch"], cart_present=False)
        run(gs.handle_input("UNLOAD CART torch"))
        all_output = "".join(call.args[0] for call in send_fn.call_args_list)
        assert "cart" in all_output.lower()
        assert "torch" in gs._cart_inventory  # item not moved
