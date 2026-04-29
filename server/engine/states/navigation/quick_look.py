"""Quick look / battle look command submodule."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def _do_lookmode(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Toggle look mode."""
    upper = args.strip().upper()

    if not upper:
        mode = session.player.look_mode
        await session.send(f"  Current look mode: {mode}\n  Usage: LOOKMODE FULL | LOOKMODE QUICK\n")
        return

    if upper not in ("FULL", "QUICK"):
        await session.send("  Usage: LOOKMODE FULL | LOOKMODE QUICK\n")
        return

    session.player.look_mode = upper
    await session.send(f"  Look mode set to {upper}.\n")


async def _do_battlelook(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Toggle battle look."""
    upper = args.strip().upper()

    if not upper:
        status = "ON" if session.player.battle_look else "OFF"
        await session.send(f"  Battle look is {status}.\n  Usage: BATTLELOOK ON | BATTLELOOK OFF\n")
        return

    if upper not in ("ON", "OFF"):
        await session.send("  Usage: BATTLELOOK ON | BATTLELOOK OFF\n")
        return

    session.player.battle_look = (upper == "ON")
    status = "ON" if session.player.battle_look else "OFF"
    await session.send(f"  Battle look set to {status}.\n")
