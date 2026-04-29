"""Inventory operations — extracted from GameSession."""
from __future__ import annotations

import random

from server.engine.domain.items import EQUIPMENT_SLOTS, get_item, total_equipped_weight


from server.engine.display.formatting import box as _box


def party_inventory_view(player, party) -> list[tuple[str, str, str]]:
    """Return (holder_name, item_id, item_name) for all party inventories."""
    result: list[tuple[str, str, str]] = []
    members = ([player] if player else []) + list(party)
    for m in members:
        for item_id in m.inventory:
            item = get_item(item_id)
            name = item.name if item else item_id
            result.append((m.name, item_id, name))
    type_order = {"weapon": 0, "armor": 1, "consumable": 2}
    result.sort(key=lambda t: type_order.get(
        (get_item(t[1]).type if get_item(t[1]) else "misc"), 3
    ))
    return result


async def do_inventory(send_fn, player, party, cart_inventory, args: str = "") -> None:
    args_stripped = args.strip()
    args_upper = args_stripped.upper()

    # INV CART
    if args_upper == "CART":
        if not cart_inventory:
            await send_fn(_box("CART", ["  (empty)"]))
        else:
            lines = []
            for item_id in cart_inventory:
                item = get_item(item_id)
                lines.append(f"  {item.name if item else item_id}")
            await send_fn(_box("CART", [""] + lines))
        return

    # INVENTORY <member>
    if args_stripped:
        target_name = args_stripped.lower()
        members = ([player] if player else []) + list(party)
        target = next(
            (m for m in members if m.name.lower() == target_name), None
        )
        if not target:
            await send_fn(f"  '{args_stripped}' is not in your party.\n")
            return
        lines = []
        if not target.inventory:
            lines.append("  (empty)")
        else:
            counts: dict[str, int] = {}
            for i in target.inventory:
                counts[i] = counts.get(i, 0) + 1
            for item_id, count in counts.items():
                item = get_item(item_id)
                lines.append(f"  x{count}  {item.name if item else item_id}")
        await send_fn(_box(f"INVENTORY — {target.name}", [""] + lines))
        return

    # Unified party view
    party_items = party_inventory_view(player, party)
    lines: list[str] = []
    if not party_items:
        lines.append("  (empty)")
    else:
        for holder, item_id, item_name in party_items:
            lines.append(f"  {item_name:<30} [{holder}]")

    lines.append("")
    lines.append("  EQUIPPED (player):")
    for slot in EQUIPMENT_SLOTS:
        eid = player.equipment.get(slot)
        item = get_item(eid) if eid else None
        lines.append(f"    {slot:<8}: {item.name if item else '---'}")

    lines.append(f"\n  Carry weight: {total_equipped_weight(player.equipment)} "
                 f"  Speed: {player.effective_speed}")
    await send_fn(_box("INVENTORY", [""] + lines))


async def do_equip(send_fn, player, args: str) -> None:
    item_name = args.lower().strip()
    for item_id in player.inventory:
        item = get_item(item_id)
        if item and item_name in item.name.lower():
            slot = item.slot if item.slot else ("weapon" if item.type == "weapon" else None)
            if not slot:
                await send_fn(f"  {item.name} can't be equipped.\n")
                return
            current = player.equipment.get(slot)
            if current:
                player.inventory.append(current)
            player.equipment[slot] = item_id
            player.inventory.remove(item_id)
            await send_fn(
                f"  You equip {item.name}. Speed is now {player.effective_speed}.\n"
            )
            return
    await send_fn(f"  You don't have '{args}' in your inventory.\n")


async def do_unequip(send_fn, player, args: str) -> None:
    slot = args.lower().strip()
    if slot not in EQUIPMENT_SLOTS:
        await send_fn(f"  Unknown slot '{args}'. Slots: {', '.join(EQUIPMENT_SLOTS)}\n")
        return
    eid = player.equipment.get(slot)
    if not eid:
        await send_fn(f"  Nothing in slot '{slot}'.\n")
        return
    player.inventory.append(eid)
    player.equipment[slot] = None
    item = get_item(eid)
    await send_fn(
        f"  You unequip {item.name if item else eid}. Speed is now {player.effective_speed}.\n"
    )


async def do_drop(send_fn, player, room, broadcast_fn, args: str) -> None:
    item_name = args.lower().strip()
    for item_id in player.inventory:
        item = get_item(item_id)
        if item and item_name in item.name.lower():
            player.inventory.remove(item_id)
            if room:
                room.item_ids.append(item_id)
            await send_fn(f"  You drop {item.name}.\n")
            player_name = player.name if player else "Someone"
            await broadcast_fn(
                f"  {player_name} drops the {item.name}.\n", exclude_self=True
            )
            return
    await send_fn(f"  You don't have '{args}'.\n")


def auto_assign_item(player, party, item_id: str, cart_inventory: list, cart_present: bool) -> bool:
    """Place item_id into the first party member with available slots.
    Falls back to cart if present. Returns True on success."""
    members = ([player] if player else []) + list(party)
    candidates = [m for m in members if len(m.inventory) < m.carry_slots]
    if candidates:
        choice = random.choice(candidates)
        choice.inventory.append(item_id)
        return True
    if cart_present:
        cart_inventory.append(item_id)
        return True
    return False


async def auto_assign_item_with_message(
    send_fn, player, party, item_id: str, cart_inventory: list, cart_present: bool
) -> bool:
    """Like auto_assign_item but sends an over-encumbered message on failure."""
    ok = auto_assign_item(player, party, item_id, cart_inventory, cart_present)
    if not ok:
        await send_fn("  Your party is over-encumbered. Drop something first.\n")
    return ok


async def do_pick_up(
    send_fn, player, party, room, cart_inventory: list, cart_present: bool,
    broadcast_fn, args: str
) -> None:
    item_name = args.lower().strip()
    if not room:
        return
    for item_id in room.item_ids:
        item = get_item(item_id)
        if item and item_name in item.name.lower():
            room.item_ids.remove(item_id)
            ok = await auto_assign_item_with_message(
                send_fn, player, party, item_id, cart_inventory, cart_present
            )
            if not ok:
                room.item_ids.append(item_id)
                return
            await send_fn(f"  You pick up {item.name}.\n")
            player_name = player.name if player else "Someone"
            await broadcast_fn(
                f"  {player_name} picks up the {item.name}.\n", exclude_self=True
            )
            return
    await send_fn(f"  You don't see '{args}' here.\n")


async def do_give(send_fn, player, party, args: str) -> None:
    """GIVE <item> TO <member>"""
    lower = args.lower()
    if " to " not in lower:
        await send_fn("  Usage: GIVE <item> TO <member>\n")
        return
    idx = lower.index(" to ")
    item_part = args[:idx].strip()
    target_name = args[idx + 4:].strip()

    members = ([player] if player else []) + list(party)
    source = None
    found_id = None
    for m in members:
        for item_id in m.inventory:
            item = get_item(item_id)
            if item and item_part.lower() in item.name.lower():
                source = m
                found_id = item_id
                break
        if source:
            break

    if not source or not found_id:
        await send_fn(f"  '{item_part}' not found in party inventory.\n")
        return

    target = next(
        (m for m in members if m.name.lower() == target_name.lower()), None
    )
    if not target:
        await send_fn(f"  '{target_name}' is not in your party.\n")
        return

    if len(target.inventory) >= target.carry_slots:
        await send_fn(f"  {target.name} doesn't have room for that.\n")
        return

    source.inventory.remove(found_id)
    target.inventory.append(found_id)
    item_obj = get_item(found_id)
    await send_fn(
        f"  {item_obj.name if item_obj else found_id} transferred to {target.name}.\n"
    )


async def do_load_cart(send_fn, player, party, cart_inventory: list, cart_present: bool, args: str) -> None:
    """STASH <item> — move item from party to cart_inventory."""
    if not cart_present:
        await send_fn("  Your cart is not here.\n")
        return
    item_name = args.strip().lower()
    members = ([player] if player else []) + list(party)
    for m in members:
        for item_id in m.inventory:
            item = get_item(item_id)
            if item and item_name in item.name.lower():
                m.inventory.remove(item_id)
                cart_inventory.append(item_id)
                await send_fn(f"  {item.name} stashed in the cart.\n")
                return
    await send_fn(f"  '{args.strip()}' not found in party inventory.\n")


async def do_unload_cart(
    send_fn, player, party, cart_inventory: list, cart_present: bool, args: str
) -> None:
    """UNLOAD <item> — move item from cart_inventory to party."""
    if not cart_present:
        await send_fn("  Your cart is not here.\n")
        return
    item_name = args.strip().lower()
    for item_id in cart_inventory:
        item = get_item(item_id)
        if item and item_name in item.name.lower():
            cart_inventory.remove(item_id)
            ok = await auto_assign_item_with_message(
                send_fn, player, party, item_id, cart_inventory, cart_present
            )
            if not ok:
                cart_inventory.append(item_id)
                return
            await send_fn(f"  {item.name} unloaded from cart.\n")
            return
    await send_fn(f"  '{args.strip()}' not found in cart.\n")
