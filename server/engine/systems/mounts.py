"""Mount system — RIDE, DISMOUNT, HORSES, cart logic extracted from GameSession."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import MOUNT_STAMINA_REDUCTION
from server.engine.domain.items import get_item

if TYPE_CHECKING:
    from server.engine.game import GameSession


def horse_count(session: "GameSession") -> int:
    """Count mount-type items across party inventories."""
    members = ([session.player] if session.player else []) + list(session.party)
    count = 0
    for m in members:
        for item_id in m.inventory:
            item = get_item(item_id)
            if item and item.type == "mount":
                count += 1
    return count


def stamina_multiplier(session: "GameSession") -> float:
    """Return stamina drain multiplier based on horse-to-party ratio."""
    if not session._mounted:
        return 1.0
    count = horse_count(session)
    party_size = max(1, 1 + len(session.party))
    ratio = min(1.0, count / party_size)
    return 1.0 - (MOUNT_STAMINA_REDUCTION * ratio)


def party_has_cart(session: "GameSession") -> bool:
    """Return True if any party member has travellers_cart."""
    members = ([session.player] if session.player else []) + list(session.party)
    for m in members:
        if "travellers_cart" in m.inventory:
            return True
    return False


async def do_ride(session: "GameSession") -> None:
    """RIDE — mount up if horses are available."""
    if horse_count(session) == 0:
        await session.send("  You don't have any horses.\n")
        return
    room = session.world.get_room(session.current_room_id)
    if room and room.room_type != "outdoor":
        await session.send("  You can only mount up outdoors.\n")
        return
    session._mounted = True
    await session.send("  The party mounts up and prepares to ride.\n")


async def do_dismount(session: "GameSession") -> None:
    """DISMOUNT — dismount the party."""
    session._mounted = False
    await session.send("  The party dismounts.\n")


async def do_horses(session: "GameSession") -> None:
    """HORSES — show horse count and stamina reduction."""
    count = horse_count(session)
    party_size = 1 + len(session.party)
    ratio = min(1.0, count / max(1, party_size)) if session._mounted else 0.0
    reduction_pct = round(MOUNT_STAMINA_REDUCTION * ratio * 100)
    await session.send(
        f"  Horses: {count} | Party: {party_size} | Stamina drain: -{reduction_pct}%\n"
    )
