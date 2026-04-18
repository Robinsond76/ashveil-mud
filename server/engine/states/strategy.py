"""Strategy editor state handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.states import State
from server.engine.strategy import (
    add_strategy, clear_strategies, list_strategies, remove_strategy
)
from server.engine.skills import get_skill

if TYPE_CHECKING:
    from server.engine.game import GameSession


def _box(title: str, lines: list[str]) -> str:
    """Format a boxed display."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class StrategyHandler:
    """Handles strategy editing for characters and companions."""

    async def on_enter(self, session: GameSession) -> None:
        """No special entry behavior - prompt comes from previous state."""
        pass

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process strategy editor commands."""
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)
        cmd = parts[0] if parts else ""

        ctx = session._state_data
        char = ctx.get("target")

        # Help
        if cmd in ("HELP", "?"):
            topic = parts[1] if len(parts) > 1 else ""
            await session._send_help(topic)
            return

        # Exit strategy editor
        if upper in ("DONE", "BACK", "EXIT", "START"):
            await self._exit_editor(session)
            return

        if upper == "STRATEGY LIST" or upper == "LIST":
            await session.send(_box(f"Strategies: {char.name}", [list_strategies(char)]))
            return

        if upper == "SKILLS":
            await self._show_skills(session, char)
            return

        if upper.startswith("STRATEGY ADD"):
            await self._parse_strategy_add(session, char, text)
            return

        if upper.startswith("STRATEGY REMOVE"):
            await self._handle_remove(session, char, upper)
            return

        if upper == "STRATEGY CLEAR":
            msg = clear_strategies(char)
            await session.send(f"  {msg}\n")
            return

        # Unknown command - show help
        await self._send_editor_help(session)

    async def _exit_editor(self, session: GameSession) -> None:
        """Exit back to appropriate state based on context."""
        ctx = session._state_data

        if ctx.get("context") == "creation":
            # First time entering world
            await session.transition_to(State.NAVIGATION)
            await session.send("\n  Entering the world of Ashveil...\n")
            # Trigger look via navigation handler
            from server.engine.states.navigation import NavigationHandler
            nav = NavigationHandler()
            await nav._do_look(session)
        else:
            # From campfire - go back
            await session.transition_to(State.CAMPFIRE)
            target_name = ctx.get("target", {}).name if ctx.get("target") else "companion"
            await session.send(
                f"  Strategy for {target_name} saved.\n"
                "  Back at campfire. Type HELP for available commands.\n"
            )

    async def _show_skills(self, session: GameSession, char) -> None:
        """Display character's unlocked skills."""
        if not char.unlocked_skills:
            await session.send(f"  {char.name} has no skills unlocked yet.\n")
            return

        lines = [f"  Unlocked skills for {char.name} ({char.class_type.capitalize()}):"]
        for skill_id in char.unlocked_skills:
            skill = get_skill(skill_id)
            if skill:
                lines.append(
                    f"    {skill_id:<20} — {skill.name}  (MP:{skill.mp_cost})  {skill.description}"
                )
            else:
                lines.append(f"    {skill_id}")

        lines.append("")
        lines.append("  Use the skill ID in a strategy:  DO USE_SKILL <id>")
        await session.send("\n".join(lines) + "\n")

    async def _parse_strategy_add(self, session: GameSession, char, text: str) -> None:
        """Parse STRATEGY ADD command."""
        try:
            upper = text.strip().upper()
            after_add = upper[len("STRATEGY ADD"):].strip()

            # Split on IF, DO, ON
            if_idx = after_add.index(" IF ")
            do_idx = after_add.index(" DO ")
            on_idx = after_add.index(" ON ")

            priority_str = after_add[:if_idx].strip()
            condition = after_add[if_idx + 4:do_idx].strip()
            action = after_add[do_idx + 4:on_idx].strip()
            target = after_add[on_idx + 4:].strip()
            priority = int(priority_str)
        except (ValueError, AttributeError):
            await session.send(
                "  Usage: STRATEGY ADD <number> IF <condition> DO <action> ON <target>\n"
                "  Example: STRATEGY ADD 1 IF HP_SELF < 30% DO DEFEND ON SELF\n"
            )
            return

        msg = add_strategy(char, priority, condition, action, target)
        await session.send(f"  {msg}\n")
        await session.send(list_strategies(char) + "\n")

    async def _handle_remove(self, session: GameSession, char, upper: str) -> None:
        """Handle STRATEGY REMOVE command."""
        parts = upper.split()
        if len(parts) >= 3:
            try:
                n = int(parts[2])
                msg = remove_strategy(char, n)
                await session.send(f"  {msg}\n")
            except ValueError:
                await session.send("  Usage: STRATEGY REMOVE <number>\n")

    async def _send_editor_help(self, session: GameSession) -> None:
        """Display strategy editor help text."""
        await session.send(
            "  Strategy editor commands:\n"
            "    STRATEGY LIST                          — show current rules\n"
            "    SKILLS                                 — list unlocked skills\n"
            "    STRATEGY ADD <n> IF <cond> DO <act> ON <tgt>\n"
            "    STRATEGY REMOVE <n>\n"
            "    STRATEGY CLEAR\n"
            "    DONE  (save and exit editor)\n"
            "\n"
            "  Conditions: ALWAYS | HP_SELF < X% | HP_ALLY < X% | MP_SELF < X%\n"
            "              ENEMY_COUNT > N | HAS_STATUS <s> | ENEMY_HAS_STATUS <s>\n"
            "  Actions:    ATTACK | DEFEND | FLEE | USE_SKILL <id> | USE_ITEM <id>\n"
            "  Targets:    NEAREST_ENEMY | WEAKEST_ENEMY | STRONGEST_ENEMY\n"
            "              LOWEST_HP_ALLY | LOWEST_HP_ENEMY | SELF | RANDOM_ENEMY\n"
        )
