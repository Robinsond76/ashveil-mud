"""Connect state handler — login and authentication."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.persistence import load_player
from server.engine.states import State

if TYPE_CHECKING:
    from server.engine.game import GameSession


class ConnectHandler:
    """Handles player login and account creation flow."""

    async def on_enter(self, session: GameSession) -> None:
        """Display welcome message and prompt for name."""
        await session.send(
            "\n" + "═" * 60 + "\n"
            "  Welcome to ASHVEIL MUD\n"
            "  A text-based fantasy world\n" +
            "═" * 60 + "\n"
            "\nEnter your character name (new or existing):\n> "
        )

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed for connect state."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process login name."""
        name = text.strip()

        if name.upper() in ("HELP", "?"):
            await session._send_help("")
            return

        if not name.isalpha() or len(name) < 2 or len(name) > 20:
            await session.send("  Name must be 2–20 letters only. Try again:\n> ")
            return

        # Try to load existing save
        save = load_player(name)
        if save:
            await session._load_save(save)
            session._subscribe_clock()
            await session.send(f"\n  Welcome back, {session.player.name}!\n")
            await session.transition_to(State.NAVIGATION)
            # Trigger look after transition
            from server.engine.states.navigation import NavigationHandler
            nav = NavigationHandler()
            await nav._do_look(session)
        else:
            # New character - go to creation wizard
            await session.transition_to(
                State.CREATION,
                step="class",
                pending_name=name
            )
