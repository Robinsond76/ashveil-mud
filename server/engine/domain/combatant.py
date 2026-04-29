"""Combatant types — CombatantState wrapper and Combatant Protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from server.engine.domain.character import Character
    from server.engine.domain.npc import NPC


@runtime_checkable
class Combatant(Protocol):
    """Minimum interface for anything that participates in combat."""
    name: str
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    equipment: dict
    inventory: list

    @property
    def is_alive(self) -> bool: ...


@dataclass
class CombatantState:
    """Combat-only state attached to a Character/NPC during combat.

    Keeps combat fields separate from the base Character/NPC model
    so they never leak into persistence or non-combat contexts.
    """
    combatant: Character | NPC
    speed: int = 0            # effective_speed during combat
    grid_row: int = 0         # 0=FRONT, 1=BACK
    grid_col: int = 0         # 0, 1, or 2
    strategies: dict = field(default_factory=dict)
    active_buffs: dict[str, int] = field(default_factory=dict)
    status_effects: dict[str, int] = field(default_factory=dict)
    action_cooldown: float = 0.0
