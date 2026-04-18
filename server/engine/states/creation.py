"""Character creation wizard state handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import MIN_STAT, MAX_STAT, STAT_POINT_BUY_BUDGET
from server.engine.character import Character
from server.engine.npc import NPC, spawn_npc
from server.engine.states import State
from server.engine.strategy import list_strategies
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


class CreationHandler:
    """Multi-step character creation: class -> stats -> strategy -> done."""

    async def on_enter(self, session: GameSession) -> None:
        """Display class selection prompt."""
        await self._send_class_prompt(session)

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Route to appropriate step handler."""
        upper = text.strip().upper()

        if upper in ("HELP", "?"):
            await session._send_help("")
            return

        ctx = session._state_data
        step = ctx.get("step", "class")

        if step == "class":
            await self._handle_class_step(session, text)
        elif step == "stats":
            await self._handle_stats_step(session, text)
        elif step == "strategy":
            # Delegate to StrategyHandler but with creation context
            from server.engine.states.strategy import StrategyHandler
            handler = StrategyHandler()
            await handler.handle(session, text)

    async def _send_class_prompt(self, session: GameSession) -> None:
        """Display class selection options."""
        ctx = session._state_data
        lines = [f"  Creating character: {ctx['pending_name']}", ""]

        for key, cd in session.class_defs.items():
            lines.append(f"  {key.upper():<10} — {cd['description']}")
        lines.append("")
        lines.append("  Type WARRIOR, MAGE, THIEF, or CLERIC:")

        await session.send(_box("CHARACTER CREATION — Choose Class", lines[1:]))

    async def _handle_class_step(self, session: GameSession, text: str) -> None:
        """Process class selection."""
        cls = text.strip().lower()

        if cls not in session.class_defs:
            await session.send(f"  Unknown class '{text}'. Choose: warrior, mage, thief, cleric\n> ")
            return

        # Initialize creation context for stats step
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]
        ctx = session._state_data
        ctx["pending_class"] = cls
        ctx["step"] = "stats"
        ctx["pending_stats"] = {s: MIN_STAT for s in stats_list}
        ctx["stat_points_remaining"] = STAT_POINT_BUY_BUDGET

        await self._send_stat_prompt(session)

    async def _send_stat_prompt(self, session: GameSession) -> None:
        """Display stat assignment UI."""
        ctx = session._state_data
        cd = session.class_defs[ctx["pending_class"]]
        suggested = cd["suggested_stats"]
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]

        spent = sum(ctx["pending_stats"].values()) - MIN_STAT * 6
        remaining = STAT_POINT_BUY_BUDGET - spent

        lines = [
            f"  Class: {cd['display_name']}",
            f"  Points remaining: {remaining}  (budget: {STAT_POINT_BUY_BUDGET})",
            f"  Stats range: {MIN_STAT}–{MAX_STAT}",
            "",
            "  Current / Suggested:",
        ]
        for stat in stats_list:
            cur = ctx["pending_stats"].get(stat, MIN_STAT)
            sug = suggested.get(stat, MIN_STAT)
            lines.append(f"    {stat}: {cur:<4}  (suggested {sug})")

        lines += [
            "",
            "  Commands: SET STR 15 | SUGGEST | STATS | DONE | HELP",
        ]

        await session.send(_box("CHARACTER CREATION — Assign Stats", lines))

    async def _handle_stats_step(self, session: GameSession, text: str) -> None:
        """Process stat assignment commands."""
        upper = text.strip().upper()
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]
        ctx = session._state_data

        if upper in ("HELP", "?"):
            await session.send(
                f"  Commands during stat assignment:\n"
                f"    SET <stat> <value>  — assign a stat (e.g. SET STR 15)\n"
                f"    STATS               — show current assignments and remaining points\n"
                f"    SUGGEST             — apply the recommended spread for your class\n"
                f"    DONE                — confirm stats and continue\n"
                f"    QUIT                — exit the game\n"
                f"  Stats: STR DEX INT WIS CON AGI  (range: {MIN_STAT}\u2013{MAX_STAT})\n"
                f"  Point budget: {STAT_POINT_BUY_BUDGET}\n"
            )
            return

        if upper == "STATS":
            spent = sum(ctx["pending_stats"].values()) - MIN_STAT * 6
            remain = STAT_POINT_BUY_BUDGET - spent
            lines = [f"  Points remaining: {remain}  (budget: {STAT_POINT_BUY_BUDGET})"]
            for s in stats_list:
                lines.append(f"    {s}: {ctx['pending_stats'].get(s, MIN_STAT)}")
            await session.send("\n".join(lines) + "\n")
            return

        if upper == "SUGGEST":
            cd = session.class_defs[ctx["pending_class"]]
            ctx["pending_stats"] = dict(cd["suggested_stats"])
            spent = sum(ctx["pending_stats"].values()) - MIN_STAT * 6
            ctx["stat_points_remaining"] = STAT_POINT_BUY_BUDGET - spent
            lines = ["  Suggested stats applied:"]
            for s in stats_list:
                lines.append(f"    {s}: {ctx['pending_stats'].get(s, MIN_STAT)}")
            lines.append(f"  Points used: {spent}  |  Remaining: {ctx['stat_points_remaining']}")
            lines.append("  Type DONE to confirm, or SET <stat> <value> to adjust.")
            await session.send("\n".join(lines) + "\n")
            return

        if upper == "DONE":
            total = sum(ctx["pending_stats"].values()) - (MIN_STAT * 6)
            if total > STAT_POINT_BUY_BUDGET:
                await session.send(
                    f"  You've spent {total} points but only have {STAT_POINT_BUY_BUDGET}. Adjust stats.\n> "
                )
                return

            await self._finalize_character(session)
            return

        # SET <stat> <value>
        parts = upper.split()
        if len(parts) == 3 and parts[0] == "SET" and parts[1] in stats_list:
            try:
                val = int(parts[2])
            except ValueError:
                await session.send("  Usage: SET STR 15\n> ")
                return

            if val < MIN_STAT or val > MAX_STAT:
                await session.send(f"  Stat must be between {MIN_STAT} and {MAX_STAT}.\n> ")
                return

            old = ctx["pending_stats"].get(parts[1], MIN_STAT)
            new_spent = sum(ctx["pending_stats"].values()) - (MIN_STAT * 6) - old + val

            if new_spent > STAT_POINT_BUY_BUDGET:
                current_remain = STAT_POINT_BUY_BUDGET - (sum(ctx["pending_stats"].values()) - MIN_STAT * 6)
                await session.send(
                    f"  Not enough points. You have {current_remain} remaining but that would cost {val - old} more.\n> "
                )
                return

            ctx["pending_stats"][parts[1]] = val
            remain = STAT_POINT_BUY_BUDGET - new_spent
            await session.send(f"  {parts[1]} set to {val}. Points remaining: {remain}\n> ")
        else:
            await session.send("  Usage: SET STR 15 | SUGGEST | STATS | DONE | HELP\n> ")

    async def _finalize_character(self, session: GameSession) -> None:
        """Create the character and transition to strategy setup."""
        ctx = session._state_data
        cd = session.class_defs[ctx["pending_class"]]
        s = ctx["pending_stats"]

        max_hp = cd["base_hp"] + max(0, (s.get("CON", 10) - 10))
        max_mp = cd["base_mp"] + max(0, (s.get("WIS", 10) - 10) * 2)

        session.player = Character(
            name=ctx["pending_name"],
            class_type=ctx["pending_class"],
            STR=s["STR"], DEX=s["DEX"], INT=s["INT"],
            WIS=s["WIS"], CON=s["CON"], AGI=s["AGI"],
            max_hp=max_hp, hp=max_hp,
            max_mp=max_mp, mp=max_mp,
        )

        # Give starting equipment
        starter_equipment = {
            "warrior": {"weapon": "rusty_sword", "body": "leather_armor"},
            "mage":    {"weapon": "oak_staff",   "body": "cloth_robe"},
            "thief":   {"weapon": "iron_dagger", "body": "leather_armor"},
            "cleric":  {"weapon": "wooden_mace", "body": "leather_armor"},
        }
        for slot, item_id in starter_equipment.get(ctx["pending_class"], {}).items():
            session.player.equipment[slot] = item_id
        session.player.inventory = ["health_potion", "health_potion", "campfire_kit"]

        # Default starting strategies
        for i, strat_raw in enumerate(cd.get("default_strategies", []), start=1):
            session.player.strategies.append({
                "priority": i,
                "condition": strat_raw["condition"],
                "action": strat_raw["action"],
                "target": strat_raw["target"],
            })

        # Unlock starter skills
        for skill_id in cd.get("starter_skills", []):
            session.player.unlocked_skills[skill_id] = 1

        session.current_room_id = "town_square"
        session.last_campfire_room_id = "test_campfire"
        session.player.owner = session.player.name

        await session.send(
            _box(f"CHARACTER CREATED: {session.player.name}", [
                session.player.stats_summary(),
                "",
                "  Your starting strategies:",
                list_strategies(session.player),
                "",
                "  You may now customize your strategies before entering the world.",
                "  Commands: STRATEGY LIST, STRATEGY ADD <n> IF <cond> DO <act> ON <tgt>",
                "             STRATEGY REMOVE <n>, STRATEGY CLEAR",
                "",
                "  When ready, type:  START",
            ])
        )

        # Transition to strategy editor
        await session.transition_to(
            State.STRATEGY,
            target=session.player,
            context="creation"
        )
