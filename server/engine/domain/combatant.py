"""Combat participant protocol — interface contract for combatants."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CombatParticipant(Protocol):
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
