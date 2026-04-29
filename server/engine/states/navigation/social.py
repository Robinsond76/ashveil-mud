"""Social command submodule."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.display.formatting import box as _box
from server.engine.systems.chat import do_say, do_emote, do_shout

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def _do_examine(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Examine an item or NPC."""
    from server.engine.domain.items import get_item
    from server.engine.domain.npc import get_npc_template

    target = args.lower().strip()
    if not target:
        await session.send("  Examine what?\n")
        return

    room = session.world.get_room(session.current_room_id)

    # Check room items
    for item_id in room.item_ids:
        item = get_item(item_id)
        if item and target in item.name.lower():
            await session.send(_box(item.name, [item.description, item.short_desc()]))
            return

    # Check inventory
    for item_id in session.player.inventory:
        item = get_item(item_id)
        if item and target in item.name.lower():
            await session.send(_box(item.name, [item.description, item.short_desc()]))
            return

    # Check recruitable NPCs
    for tid in room.recruitable_npc_ids:
        tpl = get_npc_template(tid)
        if tpl and target in tpl["name"].lower():
            await session.send(_box(
                tpl["name"],
                [tpl.get("room_flavor", ""), f"Class: {tpl['class_type'].capitalize()}, Level {tpl['level']}"]
            ))
            return

    await session.send(f"  You don't see '{args}' here.\n")


async def _do_say(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Say something to the room."""
    player_name = session.player.name if session.player else "Someone"
    await do_say(session.send, session.broadcast_to_room, player_name, raw_args)


async def _do_emote(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Perform an emote."""
    player_name = session.player.name if session.player else "Someone"
    await do_emote(session.send, session.broadcast_to_room, player_name, raw_args)


async def _do_shout(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Shout to all players."""
    player_name = session.player.name if session.player else "Someone"
    await do_shout(session.send, session._sessions, player_name, raw_args)
