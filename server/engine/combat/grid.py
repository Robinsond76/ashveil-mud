"""Combat position grid — constants and assignment logic."""
from __future__ import annotations

from typing import Any

FRONT_ROW = 0
BACK_ROW = 1
MELEE_CLASSES = {"warrior", "thief"}
RANGED_WEAPON_TYPES = {"bow", "staff"}
MAX_GRID_SLOTS = 6


class CombatTooManyMembers(Exception):
    """Raised when party+enemies exceeds grid capacity."""
    pass


def assign_positions(party_members: list[Any]) -> list[tuple[int, int]]:
    """Assign grid positions (row, col) to party members.

    Melee classes go to FRONT row, ranged/casters to BACK row.
    Raises CombatTooManyMembers if more than MAX_GRID_SLOTS members.
    """
    if len(party_members) > MAX_GRID_SLOTS:
        raise CombatTooManyMembers(
            f"Too many combatants ({len(party_members)}). Grid capacity is {MAX_GRID_SLOTS}."
        )

    front_col = 0
    back_col = 0
    positions = []

    for member in party_members:
        class_type = getattr(member, 'class_type', 'warrior')
        is_melee = class_type in MELEE_CLASSES

        if hasattr(member, 'equipment'):
            weapon = member.equipment.get("weapon")
            if weapon and isinstance(weapon, dict) and weapon.get("weapon_type") in RANGED_WEAPON_TYPES:
                is_melee = False
            elif weapon and hasattr(weapon, 'weapon_type') and weapon.weapon_type in RANGED_WEAPON_TYPES:
                is_melee = False

        if is_melee:
            positions.append((FRONT_ROW, min(front_col, 2)))
            front_col += 1
        else:
            positions.append((BACK_ROW, min(back_col, 2)))
            back_col += 1

    return positions
