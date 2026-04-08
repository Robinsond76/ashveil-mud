"""
Typed item effect dataclasses.

Replaces string-based effect_type checks in combat.py and survival.py with
instanceof dispatch, making item effect handling explicit and refactorable.

Usage:
    from server.engine.item_effects import parse_item_effect, HealEffect

    effect = parse_item_effect(item.effect_type, item.effect_params)
    if isinstance(effect, HealEffect):
        char.heal(effect.amount)
"""
from __future__ import annotations

from dataclasses import dataclass


# ── Item effect types ─────────────────────────────────────────────────────────

@dataclass
class HealEffect:
    amount: int


@dataclass
class RestoreMPEffect:
    amount: int


@dataclass
class StatusRemoveEffect:
    status_id: str   # the status name to remove (e.g. "poison")


@dataclass
class BuffEffect:
    buff_id: str
    duration_minutes: int


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_item_effect(
    effect_type: str,
    effect_params: dict,
) -> "HealEffect | RestoreMPEffect | StatusRemoveEffect | BuffEffect | None":
    """
    Convert an item's effect_type + effect_params into a typed ItemEffect.

    Returns None for effect types that don't map to a consumable effect
    (e.g. "light_source", "campfire", "mount", "spellbook").
    """
    if not effect_type:
        return None

    if effect_type == "heal":
        return HealEffect(amount=effect_params.get("amount", 0))

    if effect_type == "restore_mp":
        return RestoreMPEffect(amount=effect_params.get("amount", 0))

    if effect_type == "status_remove":
        # JSON uses "status" key; we normalise to status_id
        status = effect_params.get("status") or effect_params.get("status_id", "")
        return StatusRemoveEffect(status_id=status)

    if effect_type == "food":
        buff = effect_params.get("buff", "")
        duration = effect_params.get("duration_minutes", 0)
        return BuffEffect(buff_id=buff, duration_minutes=duration)

    if effect_type == "drink":
        buff = effect_params.get("buff", "")
        duration = effect_params.get("duration_minutes", 0)
        return BuffEffect(buff_id=buff, duration_minutes=duration)

    return None
