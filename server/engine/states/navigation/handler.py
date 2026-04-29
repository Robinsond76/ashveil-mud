"""NavigationHandler — main exploration gameplay coordinator."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from server.config import STAMINA_DRAIN_PER_MOVE, MOUNT_STAMINA_REDUCTION
from server.engine.display.formatting import box as _box
from server.engine.states import State
from server.engine.world.environment import (
    do_time, do_weather, do_light, do_envdetails, do_light_source,
    carried_light,
)
from server.engine.systems.survival import (
    do_survival_status, do_eat, do_drink, do_buffs
)

from . import inventory as _inventory
from . import party as _party
from . import social as _social
from . import interaction as _interaction
from . import mounts as _mounts
from . import quick_look as _quick_look

if TYPE_CHECKING:
    from server.engine.game import GameSession


class NavigationHandler:
    """Handles navigation state — the main exploration gameplay."""

    DIR_ALIASES = {
        "n": "north", "s": "south", "e": "east", "w": "west",
        "u": "up", "d": "down",
        "north": "north", "south": "south", "east": "east",
        "west": "west", "up": "up", "down": "down",
    }

    _OPPOSITE_DIR = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "up": "down", "down": "up",
    }

    def __init__(self):
        self.commands: dict[str, Callable] = {
            "look": self._do_look,
            "l": self._do_look,
            "examine": self._do_examine,
            "x": self._do_examine,
            "inventory": self._do_inventory,
            "inv": self._do_inventory,
            "i": self._do_inventory,
            "equip": self._do_equip,
            "eq": self._do_equip,
            "unequip": self._do_unequip,
            "uneq": self._do_unequip,
            "drop": self._do_drop,
            "pick": self._do_pick_up,
            "take": self._do_pick_up,
            "get": self._do_pick_up,
            "give": self._do_give,
            "giv": self._do_give,
            "load": self._do_load_cart,
            "stash": self._do_load_cart,
            "unload": self._do_unload_cart,
            "stats": self._do_stats,
            "stat": self._do_stats,
            "gold": self._do_gold,
            "skills": self._do_skills,
            "sk": self._do_skills,
            "learn": self._do_learn,
            "lrn": self._do_learn,
            "modifiers": self._do_modifiers,
            "mods": self._do_modifiers,
            "upgrade": self._do_upgrade,
            "upg": self._do_upgrade,
            "party": self._do_party,
            "p": self._do_party,
            "talk": self._do_talk,
            "t": self._do_talk,
            "dismiss": self._do_dismiss,
            "dis": self._do_dismiss,
            "campfire": self._do_campfire,
            "rest": self._do_campfire,
            "status": self._do_status,
            "ss": self._do_status,
            "sit": self._do_sit,
            "stand": self._do_stand,
            "eat": self._do_eat,
            "ea": self._do_eat,
            "drink": self._do_drink,
            "dr": self._do_drink,
            "buffs": self._do_buffs,
            "b": self._do_buffs,
            "attack": self._do_attack,
            "k": self._do_attack,
            "use": self._do_use,
            "save": self._do_save,
            "sv": self._do_save,
            "time": self._do_time,
            "ti": self._do_time,
            "weather": self._do_weather,
            "wea": self._do_weather,
            "light": self._do_light,
            "lighting": self._do_light,
            "envdetails": self._do_envdetails,
            "env": self._do_envdetails,
            "lit": self._do_lit,
            "extinguish": self._do_extinguish,
            "douse": self._do_extinguish,
            "ride": self._do_ride,
            "dismount": self._do_dismount,
            "horses": self._do_horses,
            "hor": self._do_horses,
            "say": self._do_say,
            "'": self._do_say,
            "emote": self._do_emote,
            "me": self._do_emote,
            "shout": self._do_shout,
            "ooc": self._do_shout,
            "help": self._do_help,
            "lookmode": self._do_lookmode,
            "battlelook": self._do_battlelook,
        }

    async def on_enter(self, session: GameSession) -> None:
        """Subscribe to clock and show current room based on look_mode."""
        session._subscribe_clock()

        # Check if battle_look is forcing a quick look after combat
        force_quick = session._state_data.get("force_quick_look", False)

        if force_quick:
            # Battle look after combat - always show quick look
            await self._do_quicklook(session)
        elif session.player and session.player.look_mode == "QUICK":
            await self._do_quicklook(session)
        else:
            await self._do_look(session)

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Main command dispatch with O(1) lookup."""
        text_stripped = text.strip()
        if not text_stripped:
            return

        # Check for pending recruit response (from TALK command)
        if await self._try_recruit_response(session, text_stripped):
            return

        # Parse command
        parts = text_stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        raw_parts = text_stripped.split(maxsplit=1)
        raw_args = raw_parts[1] if len(raw_parts) > 1 else ""

        # Handle movement (not in commands dict)
        if cmd in self.DIR_ALIASES:
            await self._do_move(session, self.DIR_ALIASES[cmd])
            return

        if cmd == "go" and args:
            await self._do_move(session, args.lower())
            return

        # Handle LOAD CART / UNLOAD CART specially
        if cmd == "load" and args.lower().startswith("cart"):
            await self._do_load_cart(session, args[4:].strip(), raw_args)
            return

        if cmd == "unload" and args.lower().startswith("cart"):
            await self._do_unload_cart(session, args[6:].strip(), raw_args)
            return

        # Regular command dispatch
        if handler := self.commands.get(cmd):
            await handler(session, args, raw_args)
        else:
            await session.send(f"  Unknown command '{cmd}'. Type HELP for a list.\n")

    # ────────────────────────────────────────────────────────────────────────
    # Core navigation (kept in NavigationHandler)
    # ────────────────────────────────────────────────────────────────────────

    async def _do_look(self, session: GameSession, *args) -> None:
        """Look at current room."""
        from server.engine.domain.items import get_item
        from server.engine.domain.npc import get_npc_template

        room = session.world.get_room(session.current_room_id)
        if room is None:
            await session.send("  Error: current room not found.\n")
            return

        # Item names for display
        item_names = {i: get_item(i).name for i in room.item_ids if get_item(i)}

        # Recruitable NPCs
        npc_flavors = []
        if room.recruitable_npc_ids:
            for tid in room.recruitable_npc_ids:
                tpl = get_npc_template(tid)
                if tpl:
                    in_party = any(m.template_id == tid for m in session.party)
                    if not in_party:
                        npc_flavors.append(tpl.get("room_flavor", tpl["name"]))

        # Encounters
        encounter_lines = []
        active_groups = session.world.active_encounter_groups(session.current_room_id)
        for eg in active_groups:
            label = eg.label if eg.label else eg.group
            if room.id == "test_arena":
                encounter_lines.append(
                    f"[{eg.group}] {label} — {len(eg.members)} opponent(s)  "
                    f"(ATTACK {eg.group} to engage)"
                )
            else:
                encounter_lines.append(f"Hostile group present: {', '.join(eg.members)}")

        # Environment footer
        footer = ""
        if session.clock:
            footer = session.clock.env_footer(
                room.room_type, room.base_temp_f,
                carried_light(session.player, session.party, session.player.lit_sources, session.clock, session.send)
            )

        await session.send(room.render(item_names, npc_flavors, encounter_lines, env_footer=footer))

        # Other players
        if session.player:
            others = [
                n for n in await session.world.players_in_room(session.current_room_id)
                if n != session.player.name
            ]
            if others:
                await session.send(f"\n  Also here: {', '.join(others)}\n")

        # Stamina warning
        if session.player and session.player.stamina <= 0.0:
            await session.send(
                "  !! The party is completely exhausted. Rest to recover stamina. !!\n"
            )

    async def _do_quicklook(self, session: GameSession, *args) -> None:
        from server.engine.domain.items import get_item
        from server.engine.domain.npc import get_npc_template

        room = session.world.get_room(session.current_room_id)
        if room is None:
            await session.send("  Error: current room not found.\n")
            return

        item_names = {i: get_item(i).name for i in room.item_ids if get_item(i)}

        npc_flavors = []
        if room.recruitable_npc_ids:
            for tid in room.recruitable_npc_ids:
                tpl = get_npc_template(tid)
                if tpl:
                    in_party = any(m.template_id == tid for m in session.party)
                    if not in_party:
                        npc_flavors.append(tpl.get("room_flavor", tpl["name"]))

        encounter_lines = []
        active_groups = session.world.active_encounter_groups(session.current_room_id)
        for eg in active_groups:
            label = eg.label if eg.label else eg.group
            if room.id == "test_arena":
                encounter_lines.append(
                    f"[{eg.group}] {label} — {len(eg.members)} opponent(s)"
                )
            else:
                encounter_lines.append(f"{', '.join(eg.members)}")

        other_players = []
        if session.player:
            other_players = [
                n for n in await session.world.players_in_room(session.current_room_id)
                if n != session.player.name
            ]

        await session.send(room.render_quick(item_names, npc_flavors, encounter_lines, other_players))

        if session.player and session.player.stamina <= 0.0:
            await session.send(
                "  !! The party is completely exhausted. Rest to recover stamina. !!\n"
            )

    async def _do_move(self, session: GameSession, direction: str) -> None:
        """Move in a direction."""
        room = session.world.get_room(session.current_room_id)
        if room is None:
            await session.send("  You are in the void. Something went wrong.\n")
            return

        dest_id = room.exits.get(direction)
        if not dest_id:
            await session.send(f"  You can't go {direction} from here.\n")
            return

        # Block exhausted movement
        if session.player and session.player.stamina <= 0.0:
            await session.send("  You are too exhausted to move. Rest to recover your stamina.\n")
            return

        # Drain stamina
        if session.player:
            members = [session.player] + list(session.party)
            mount_mult = 1.0
            if session._mounted:
                from server.engine.domain.items import get_item
                horse_count = sum(
                    1 for m in members for item_id in m.inventory
                    if (item := get_item(item_id))
                    and item.type == "mount"
                )
                party_size = max(1, len(members))
                ratio = min(1.0, horse_count / party_size)
                mount_mult = 1.0 - (MOUNT_STAMINA_REDUCTION * ratio)

            for m in members:
                drain = STAMINA_DRAIN_PER_MOVE * mount_mult
                if session.clock and "fortified" in m.get_active_buffs(session.clock):
                    drain *= 0.7
                m.stamina = max(0.0, m.stamina - drain)

        # Cart and horse logic
        dest_room = session.world.get_room(dest_id)
        if dest_room:
            # Cart logic
            if dest_room.room_type in ("indoor", "underground") and session._cart_present:
                session._cart_present = False
                session._cart_room_id = session.current_room_id
                await session.send(
                    f"  Your cart remains outside at {room.id.replace('_', ' ').title()}.\n"
                )
            elif dest_room.room_type == "outdoor" and session._cart_room_id is not None:
                session._cart_present = True
                session._cart_room_id = None
                await session.send("  Your cart catches up with the party.\n")

            # Horse logic
            if dest_room.room_type in ("indoor", "underground") and session._mounted:
                session._mounted = False
                session._horses_outside = True
                await session.send(
                    f"  Your horses wait outside at {room.id.replace('_', ' ').title()}.\n"
                )
            elif dest_room.room_type == "outdoor" and session._horses_outside:
                session._horses_outside = False
                session._mounted = True
                await session.send("  Your horses fall back into step with the party.\n")

        # Broadcast and move
        player_name = session.player.name if session.player else "Someone"
        old_room_id = session.current_room_id

        await session.world.leave_room(player_name, old_room_id)
        await session.broadcast_to_room(f"  {player_name} heads {direction}.\n", exclude_self=True)

        session.current_room_id = dest_id

        await session.world.enter_room(player_name, dest_id)
        opposite = self._OPPOSITE_DIR.get(direction, direction)
        await session.broadcast_to_room(f"  {player_name} arrives from the {opposite}.\n", exclude_self=True)

        # Show room based on look_mode preference
        if session.player and session.player.look_mode == "QUICK":
            await self._do_quicklook(session)
        else:
            await self._do_look(session)

    # ────────────────────────────────────────────────────────────────────────
    # Thin wrappers delegating to command submodules
    # ────────────────────────────────────────────────────────────────────────

    # -- inventory --
    async def _do_inventory(self, session: GameSession, args: str = "", *_) -> None:
        await _inventory._do_inventory(session, args, "")

    async def _do_equip(self, session: GameSession, args: str = "", *_) -> None:
        await _inventory._do_equip(session, args, "")

    async def _do_unequip(self, session: GameSession, args: str = "", *_) -> None:
        await _inventory._do_unequip(session, args, "")

    async def _do_drop(self, session: GameSession, args: str = "", *_) -> None:
        await _inventory._do_drop(session, args, "")

    # -- party --
    async def _do_stats(self, session: GameSession, *args) -> None:
        await _party._do_stats(session, "", "")

    async def _do_gold(self, session: GameSession, *args) -> None:
        await _party._do_gold(session, "", "")

    async def _do_skills(self, session: GameSession, args: str = "", *_) -> None:
        await _party._do_skills(session, args, "")

    async def _do_learn(self, session: GameSession, args: str = "", *_) -> None:
        await _party._do_learn(session, args, "")

    async def _do_modifiers(self, session: GameSession, *args) -> None:
        await _party._do_modifiers(session, "", "")

    async def _do_upgrade(self, session: GameSession, args: str = "", *_) -> None:
        await _party._do_upgrade(session, args, "")

    # -- social --
    async def _do_examine(self, session: GameSession, args: str = "", *_) -> None:
        await _social._do_examine(session, args, "")

    async def _do_say(self, session: GameSession, args: str = "", raw_args: str = "") -> None:
        await _social._do_say(session, args, raw_args)

    async def _do_emote(self, session: GameSession, args: str = "", raw_args: str = "") -> None:
        await _social._do_emote(session, args, raw_args)

    async def _do_shout(self, session: GameSession, args: str = "", raw_args: str = "") -> None:
        await _social._do_shout(session, args, raw_args)

    # -- interaction --
    async def _do_attack(self, session: GameSession, args: str = "", *_) -> None:
        await _interaction._do_attack(session, args, "")

    async def _do_talk(self, session: GameSession, args: str = "", *_) -> None:
        await _interaction._do_talk(session, args, "")

    async def _do_pick_up(self, session: GameSession, args: str = "", *_) -> None:
        await _interaction._do_pick_up(session, args, "")

    async def _do_give(self, session: GameSession, args: str = "", *_) -> None:
        await _interaction._do_give(session, args, "")

    # -- mounts --
    async def _do_ride(self, session: GameSession, *args) -> None:
        await _mounts._do_ride(session, "", "")

    async def _do_dismount(self, session: GameSession, *args) -> None:
        await _mounts._do_dismount(session, "", "")

    async def _do_horses(self, session: GameSession, *args) -> None:
        await _mounts._do_horses(session, "", "")

    async def _do_load_cart(self, session: GameSession, args: str = "", *_) -> None:
        await _mounts._do_load_cart(session, args, "")

    async def _do_unload_cart(self, session: GameSession, args: str = "", *_) -> None:
        await _mounts._do_unload_cart(session, args, "")

    # -- quick look --
    async def _do_lookmode(self, session: GameSession, args: str = "", *_) -> None:
        await _quick_look._do_lookmode(session, args, "")

    async def _do_battlelook(self, session: GameSession, args: str = "", *_) -> None:
        await _quick_look._do_battlelook(session, args, "")

    # ────────────────────────────────────────────────────────────────────────
    # Commands that remain fully in NavigationHandler
    # ────────────────────────────────────────────────────────────────────────

    async def _do_party(self, session: GameSession, *args) -> None:
        """Show party status."""
        from server.engine.systems.survival import party_survival_aggregate

        lines = []
        lines.append(session.player.stats_summary())
        lines.append("")
        if not session.party:
            lines.append("  (no companions)")
        for i, npc in enumerate(session.party, 1):
            lines.append(f"  [{i}] {npc.stats_summary()}")
            lines.append("")

        h_pct, t_pct, s_pct = party_survival_aggregate(session.player, session.party)
        lines.append(
            f"  Survival  Stamina {s_pct * 100:.0f}%  "
            f"Hunger {h_pct * 100:.0f}%  "
            f"Thirst {t_pct * 100:.0f}%"
        )
        await session.send(_box("PARTY", lines))

    async def _do_dismiss(self, session: GameSession, args: str = "", *_) -> None:
        """Dismiss a companion."""
        name = args.lower().strip()
        if not name:
            await session.send("  Dismiss who?\n")
            return

        for npc in session.party:
            if name in npc.name.lower():
                session.party.remove(npc)
                await session.send(f"  {npc.name} has left your party.\n")
                return

        await session.send(f"  No companion named '{args}' in your party.\n")

    async def _do_campfire(self, session: GameSession, *args) -> None:
        """Enter campfire state."""
        room = session.world.get_room(session.current_room_id)
        if not room:
            return

        has_kit = "campfire_kit" in session.player.inventory
        if not room.is_campfire and not has_kit:
            await session.send("  No campfire here. Find a campfire room or use a Campfire Kit.\n")
            return

        if has_kit and not room.is_campfire:
            session.player.inventory.remove("campfire_kit")

        if room.is_campfire:
            session.last_campfire_room_id = session.current_room_id

        await session.transition_to(State.CAMPFIRE)

    async def _do_status(self, session: GameSession, *args) -> None:
        """Show survival status."""
        await do_survival_status(session.send, session.player, session.party)

    async def _do_sit(self, session: GameSession, *args) -> None:
        """Sit down to rest."""
        session._sitting = True
        await session.send("  You sit down to rest.\n")

    async def _do_stand(self, session: GameSession, *args) -> None:
        """Stand up."""
        session._sitting = False
        await session.send("  You stand up.\n")

    async def _do_eat(self, session: GameSession, args: str = "", *_) -> None:
        """Eat food."""
        await do_eat(session.send, session.player, session.party, session.clock, args)

    async def _do_drink(self, session: GameSession, args: str = "", *_) -> None:
        """Drink."""
        await do_drink(session.send, session.player, session.party, session.clock, args)

    async def _do_buffs(self, session: GameSession, *args) -> None:
        """Show active buffs."""
        await do_buffs(session.send, session.player, session.party, session.clock)

    async def _do_use(self, session: GameSession, args: str = "", *_) -> None:
        """Use a utility skill."""
        await session._handle_use_skill(args.lower().strip())

    async def _do_save(self, session: GameSession, *args) -> None:
        """Save game."""
        session.save()
        await session.send("  Game saved.\n")

    async def _do_time(self, session: GameSession, *args) -> None:
        """Show game time."""
        await do_time(session.send, session.clock)

    async def _do_weather(self, session: GameSession, *args) -> None:
        """Show weather."""
        room = session.world.get_room(session.current_room_id)
        await do_weather(session.send, session.clock, room)

    async def _do_light(self, session: GameSession, *args) -> None:
        """Show lighting info."""
        room = session.world.get_room(session.current_room_id)
        await do_light(session.send, session.clock, room, session.player.lit_sources, lambda: carried_light(
            session.player, session.party, session.player.lit_sources, session.clock, session.send
        ))

    async def _do_envdetails(self, session: GameSession, *args) -> None:
        """Show environment details."""
        room = session.world.get_room(session.current_room_id)
        await do_envdetails(session.send, session.clock, room, lambda: carried_light(
            session.player, session.party, session.player.lit_sources, session.clock, session.send
        ))

    async def _do_lit(self, session: GameSession, args: str = "", *_) -> None:
        """Light a light source."""
        await do_light_source(session.send, session.player, session.party, session.player.lit_sources, session.clock, args, extinguish=False)

    async def _do_extinguish(self, session: GameSession, args: str = "", *_) -> None:
        """Extinguish a light source."""
        await do_light_source(session.send, session.player, session.party, session.player.lit_sources, session.clock, args, extinguish=True)

    async def _do_help(self, session: GameSession, args: str = "", *_) -> None:
        """Show help."""
        await session._send_help(args)

    async def _try_recruit_response(self, session: GameSession, text: str) -> bool:
        """Handle YES/NO response after TALK command."""
        from server.engine.domain.npc import spawn_npc

        if not hasattr(session, "_pending_recruit") or session._pending_recruit is None:
            return False

        upper = text.strip().upper()
        if upper not in ("YES", "NO", "Y", "N"):
            return False

        tid = session._pending_recruit
        session._pending_recruit = None

        if upper in ("YES", "Y"):
            npc = spawn_npc(tid, session.class_defs)
            if npc:
                npc.owner = session.player.name
                session.party.append(npc)
                await session.send(
                    f"\n  {npc.name} joins your party!\n"
                    f"  Their default strategies are already configured.\n"
                    f"  Visit the campfire to customise them with MANAGE {npc.name}.\n"
                )
            else:
                await session.send("  Something went wrong recruiting that NPC.\n")
        else:
            await session.send("  You decline.\n")

        return True
