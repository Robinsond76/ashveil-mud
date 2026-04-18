"""State management for Ashveil MUD.

This module provides the State enum and handler registry for the
decomposed GameSession architecture. Handlers are singletons for
memory efficiency and thread safety.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.engine.states.base import StateHandler


class State(Enum):
    """Game session states."""

    CONNECT = "connect"
    CREATION = "creation"
    NAVIGATION = "navigation"
    CAMPFIRE = "campfire"
    STRATEGY = "strategy"
    COMBAT = "combat"


def _get_handlers() -> dict[State, StateHandler]:
    """Lazy-load handlers to avoid circular imports."""
    from server.engine.states.connect import ConnectHandler
    from server.engine.states.creation import CreationHandler
    from server.engine.states.navigation import NavigationHandler
    from server.engine.states.campfire import CampfireHandler
    from server.engine.states.strategy import StrategyHandler
    from server.engine.states.combat import CombatHandler

    return {
        State.CONNECT: ConnectHandler(),
        State.CREATION: CreationHandler(),
        State.NAVIGATION: NavigationHandler(),
        State.CAMPFIRE: CampfireHandler(),
        State.STRATEGY: StrategyHandler(),
        State.COMBAT: CombatHandler(),
    }


# Singleton handlers - loaded once on first access
HANDLER_REGISTRY: dict[State, StateHandler] = _get_handlers()
