"""Mounts and cart command submodule."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import MOUNT_STAMINA_REDUCTION
from server.engine.systems.inventory import do_load_cart, do_unload_cart

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def _do_ride(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Mount horses."""
    from server.engine.domain.items import get_item

    horse_count = sum(
        1 for m in ([session.player] + list(session.party))
        for item_id in m.inventory
        if (item := get_item(item_id)) and item.type == "mount"
    )

    if horse_count == 0:
        await session.send("  You don't have any horses.\n")
        return

    room = session.world.get_room(session.current_room_id)
    if room and room.room_type != "outdoor":
        await session.send("  You can only mount up outdoors.\n")
        return

    session._mounted = True
    await session.send("  The party mounts up and prepares to ride.\n")


async def _do_dismount(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Dismount horses."""
    session._mounted = False
    await session.send("  The party dismounts.\n")


async def _do_horses(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Show horse status."""
    from server.engine.domain.items import get_item

    horse_count = sum(
        1 for m in ([session.player] + list(session.party))
        for item_id in m.inventory
        if (item := get_item(item_id)) and item.type == "mount"
    )
    party_size = 1 + len(session.party)
    ratio = min(1.0, horse_count / max(1, party_size)) if session._mounted else 0.0
    reduction_pct = round(MOUNT_STAMINA_REDUCTION * ratio * 100)

    await session.send(
        f"  Horses: {horse_count} | Party: {party_size} | Stamina drain: -{reduction_pct}%\n"
    )


async def _do_load_cart(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Load item into cart."""
    await do_load_cart(session.send, session.player, session.party, session._cart_inventory, session._cart_present, args)


async def _do_unload_cart(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Unload item from cart."""
    await do_unload_cart(session.send, session.player, session.party, session._cart_inventory, session._cart_present, args)
