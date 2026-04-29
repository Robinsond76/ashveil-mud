"""State-specific context data structures.

Each state can store transient data in session._state_data using these
TypedDict definitions for type safety and documentation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from server.engine.domain.character import Character
    from server.engine.domain.npc import NPC


class ConnectContext(TypedDict):
    """No additional context needed for connect state."""

    pass


class CreationContext(TypedDict):
    """Context for character creation wizard.

    Tracks the multi-step creation process: class selection -> stat assignment -> strategy setup.
    """

    step: str  # "class" | "stats" | "strategy"
    pending_name: str
    pending_class: NotRequired[str]
    pending_stats: NotRequired[dict[str, int]]
    stat_points_remaining: NotRequired[int]


class StrategyContext(TypedDict):
    """Context for strategy editor.

    Used in both creation (setting up initial strategies) and campfire (editing companion strategies).
    """

    target: Character | NPC  # Who we're editing strategies for
    context: str  # "creation" | "campfire"


class CombatContext(TypedDict):
    """Context for combat state."""

    encounter_group: object  # EncounterGroup from world.py
    arena_group: str | None  # For arena fights: "A", "B", "C", "D"


# Union type for session._state_data field
StateContext = ConnectContext | CreationContext | StrategyContext | CombatContext | None
