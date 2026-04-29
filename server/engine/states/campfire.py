"""Campfire state handler — rest, party management, skills."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.states import State
from server.engine.domain.skills import render_skill_tree
from server.engine.display.formatting import box as _box

if TYPE_CHECKING:
    from server.engine.game import GameSession


class CampfireHandler:
    """Handles campfire rest state commands."""

    async def on_enter(self, session: GameSession) -> None:
        """Display campfire menu and options."""
        await session.send(
            _box("CAMPFIRE", [
                "  A warm fire crackles before you.",
                "",
                "  PARTY                — View party stats",
                "  FORMATION           — View / change battle positions",
                "  MANAGE <name>        — Edit that member's strategies",
                "  REST                 — Restore HP/MP and save",
                "  SKILLS               — View skill tree",
                "  LEARN <skill>        — Spend skill points",
                "  MODIFIERS / MODS     — View modifiers",
                "  UPGRADE <modifier>   — Spend modifier points",
                "  DISMISS <name>       — Remove companion",
                "  LEAVE                — Return to exploration",
            ])
        )

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process campfire commands."""
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("LEAVE", "EXIT", "BACK"):
            await session.transition_to(State.NAVIGATION)
            await session.send("  You leave the campfire.\n")
            # Trigger look
            from server.engine.states.navigation import NavigationHandler
            nav = NavigationHandler()
            await nav._do_look(session)
            return

        if cmd == "REST":
            await self._do_rest(session)
            return

        if cmd == "PARTY":
            await session._do_show_party()
            return

        if cmd == "FORMATION":
            await session._do_formation(args)
            return

        if cmd == "MANAGE":
            await session._do_manage(args)
            return

        if cmd == "DISMISS":
            await session._do_dismiss(args)
            return

        if cmd == "SKILLS":
            await session.send(
                render_skill_tree(
                    session.player.class_type,
                    session.player.unlocked_skills,
                    session.player.skill_points,
                ) + "\n"
            )
            return

        if cmd == "LEARN":
            await session._do_learn(args.lower())
            return

        if cmd in ("MODIFIERS", "MODS"):
            await session._do_show_modifiers()
            return

        if cmd == "UPGRADE":
            await session._do_upgrade(args.lower())
            return

        if cmd == "SAVE":
            session.save()
            await session.send("  Game saved.\n")
            return

        if cmd == "HELP":
            await session._send_help(args)
            return

        if cmd == "USE":
            await session.send("  You can only use utility skills while exploring (NAVIGATION).\n")
            return

        await session.send(f"  Unknown campfire command. Type HELP.\n")

    async def _do_rest(self, session: GameSession) -> None:
        """Restore all stats and save."""
        # Restore player
        session.player.hp = session.player.max_hp
        session.player.mp = session.player.max_mp
        session.player.stamina = session.player.max_stamina

        # Restore party
        for npc in session.party:
            npc.hp = npc.max_hp
            npc.mp = npc.max_mp
            npc.stamina = npc.max_stamina

        session.save()
        await session.send("  You rest and recover fully. Game saved.\n")
