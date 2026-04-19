"""Connect state handler — login and authentication."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.persistence import load_player, delete_player
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
            "\nEnter your character name (new or existing):\n"
            "To delete a character, type: DELETE <name>\n> "
        )

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed for connect state."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process login name or deletion commands."""
        name = text.strip()
        upper = name.upper()
        ctx = session._state_data

        # Check if we're in pending deletion confirmation mode
        if ctx.get("pending_deletion"):
            await self._handle_deletion_confirmation(session, name)
            return

        if upper in ("HELP", "?"):
            await session._send_help("")
            return

        # Check for DELETE command
        if upper.startswith("DELETE "):
            char_name = name[7:].strip()
            await self._initiate_deletion(session, char_name)
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

    async def _initiate_deletion(self, session: GameSession, char_name: str) -> None:
        """Initiate character deletion process."""
        if not char_name:
            await session.send("  Usage: DELETE <character_name>\n> ")
            return

        # Check if character exists
        save = load_player(char_name)
        if save is None:
            await session.send(
                f"\n  No character named '{char_name}' found.\n"
                "  Please check the spelling and try again.\n\n> "
            )
            return

        # Set pending deletion in state data
        session._state_data["pending_deletion"] = char_name.lower()

        await session.send(
            f"\n  ════════════════════════════════════════════════════════════\n"
            f"  WARNING: CHARACTER DELETION\n"
            f"  ──────────────────────────────────────────────────────────\n"
            f"  You are about to PERMANENTLY delete character: {char_name}\n"
            f"  This action cannot be undone!\n\n"
            f"  To confirm deletion, type the character name again: '{char_name}'\n"
            f"  To cancel, type: CANCEL\n"
            f"  ════════════════════════════════════════════════════════════\n> "
        )

    async def _handle_deletion_confirmation(self, session: GameSession, confirmation: str) -> None:
        """Handle deletion confirmation or cancellation."""
        ctx = session._state_data
        char_name = ctx.get("pending_deletion", "")

        # Clear pending deletion from state
        ctx["pending_deletion"] = None

        # Check for cancellation
        if confirmation.upper() == "CANCEL":
            await session.send(
                "\n  Character deletion cancelled.\n"
                "\nEnter your character name (new or existing):\n"
                "To delete a character, type: DELETE <name>\n> "
            )
            return

        # Check if confirmation matches (case-insensitive)
        if confirmation.lower() != char_name.lower():
            await session.send(
                f"\n  Name does not match. Deletion cancelled.\n"
                f"\nEnter your character name (new or existing):\n"
                f"To delete a character, type: DELETE <name>\n> "
            )
            return

        # Confirm deletion
        deleted = delete_player(char_name)
        if deleted:
            await session.send(
                f"\n  Character '{char_name}' has been successfully deleted.\n"
                "\nEnter your character name (new or existing):\n"
                "To delete a character, type: DELETE <name>\n> "
            )
        else:
            await session.send(
                f"\n  Error: Could not delete character '{char_name}'.\n"
                "  The character may have already been deleted.\n"
                "\nEnter your character name (new or existing):\n"
                "To delete a character, type: DELETE <name>\n> "
            )
