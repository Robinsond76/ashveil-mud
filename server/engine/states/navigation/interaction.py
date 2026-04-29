"""Interaction command submodule."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.states import State
from server.engine.systems.inventory import do_pick_up, do_give
from server.engine.world.environment import effective_light

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def _do_attack(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Initiate combat."""
    from server.engine.domain.npc import get_npc_template

    room = session.world.get_room(session.current_room_id)
    if not room:
        return

    group_id = args.strip().upper() if args else None
    active = session.world.active_encounter_groups(session.current_room_id)

    if not active:
        await session.send("  There's no one left to fight here.\n")
        return

    # Lighting check
    if session.clock:
        eff_light = effective_light(
            session.player, session.party,
            session.player.lit_sources, session.clock, room
        )
        if eff_light < 0.05:
            target_group = (
                next((g for g in active if g.group == group_id), None)
                if group_id else active[0]
            )
            enemy_has_darkvision = False
            if target_group:
                for tid in target_group.members:
                    tpl = get_npc_template(tid)
                    if tpl and tpl.get("darkvision", False):
                        enemy_has_darkvision = True
                        break
            if not enemy_has_darkvision:
                await session.send(
                    "  It is pitch black — you cannot fight what you cannot see.\n"
                    "  Light a torch or find another source of light.\n"
                )
                return

    # Arena: pick group by letter
    if room.id == "test_arena":
        if not group_id:
            await session.send("  Specify a group: ATTACK A, ATTACK B, ATTACK C, or ATTACK D\n")
            return
        target_group = next((g for g in active if g.group == group_id), None)
        if not target_group:
            await session.send(f"  Group '{group_id}' is defeated or doesn't exist.\n")
            return
        arena_group = group_id
    else:
        target_group = active[0]
        arena_group = None

    await session.transition_to(
        State.COMBAT,
        encounter_group=target_group,
        arena_group=arena_group
    )


async def _do_talk(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Talk to a recruitable NPC."""
    from server.engine.domain.npc import get_npc_template

    name = args.lower().strip()
    if not name:
        await session.send("  Talk to who?\n")
        return

    room = session.world.get_room(session.current_room_id)
    if not room:
        return

    for tid in room.recruitable_npc_ids:
        tpl = get_npc_template(tid)
        if tpl and name in tpl["name"].lower():
            already_in_party = any(m.template_id == tid for m in session.party)
            if already_in_party:
                await session.send(f"  {tpl['name']} is already in your party.\n")
                return
            if len(session.party) >= 4:
                await session.send("  Your party is full. Dismiss someone first.\n")
                return

            await session.send(tpl.get("recruit_dialogue", f"{tpl['name']} nods at you.\n"))

            # Store pending recruit in session state
            session._pending_recruit = tid
            return

    await session.send(f"  There's no one named '{args}' here to talk to.\n")


async def _do_pick_up(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Pick up an item."""
    room = session.world.get_room(session.current_room_id)
    item_arg = args.lstrip("UP").strip() if args.upper().startswith("UP") else args
    await do_pick_up(
        session.send, session.player, session.party, room,
        session._cart_inventory, session._cart_present,
        session.broadcast_to_room, item_arg.strip()
    )


async def _do_give(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Give item to party member."""
    await do_give(session.send, session.player, session.party, args)
