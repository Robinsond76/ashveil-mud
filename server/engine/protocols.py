"""
Shared protocols — re-exports from domain.combatant.
"""
from __future__ import annotations

from server.engine.domain.combatant import Combatant, CombatantState

__all__ = ["Combatant", "CombatantState"]
