"""
Shared protocols for structural typing across the engine.

Using Protocol (PEP 544) lets combat.py, strategy.py, and skill resolution
accept both Character and NPC without explicit inheritance coupling.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


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
