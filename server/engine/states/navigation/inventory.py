"""Inventory command submodule."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.systems.inventory import do_inventory, do_equip, do_unequip, do_drop

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def _do_inventory(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Show inventory."""
    await do_inventory(session.send, session.player, session.party, session._cart_inventory, args)


async def _do_equip(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Equip an item."""
    await do_equip(session.send, session.player, args)


async def _do_unequip(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Unequip an item."""
    await do_unequip(session.send, session.player, args)


async def _do_drop(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Drop an item."""
    room = session.world.get_room(session.current_room_id)
    await do_drop(session.send, session.player, room, session.broadcast_to_room, args)
