"""Base protocol for state handlers.

State handlers encapsulate all behavior for a specific game state.
They are stateless singletons - all mutable state lives in GameSession.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from server.engine.game import GameSession


@runtime_checkable
class StateHandler(Protocol):
    """Handler for a specific game state.

    Implementations must be stateless - all data lives in the session.
    """

    async def on_enter(self, session: GameSession) -> None:
        """Called when transitioning INTO this state.

        Use this to set up subscriptions, display initial output, etc.
        """
        ...

    async def on_exit(self, session: GameSession) -> None:
        """Called when transitioning OUT of this state.

        Use this to clean up subscriptions, save state, etc.
        """
        ...

    async def handle(self, session: GameSession, text: str) -> None:
        """Process input text for this state.

        This is the main entry point for player commands while in this state.

        Args:
            session: The game session (provides player, world, send, etc.)
            text: Raw input text from the player
        """
        ...
