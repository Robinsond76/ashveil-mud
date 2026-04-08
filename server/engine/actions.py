"""
Typed action objects for combat dispatch.

Action dataclasses replace the raw string protocol previously returned by
evaluate_strategy() and parsed inside CombatSession._do_action().

CombatResult replaces the on_end callback, decoupling CombatSession from
GameSession — GameSession awaits run_and_get_result() and inspects the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Combat actions ────────────────────────────────────────────────────────────

@dataclass
class Attack:
    target: object = None  # Character | NPC | None


@dataclass
class Defend:
    pass


@dataclass
class Flee:
    pass


@dataclass
class UseSkill:
    skill_id: str
    target: object = None  # Character | NPC | None


@dataclass
class UseItem:
    item_id: str
    target: object = None  # Character | NPC | None


# ── Combat result ─────────────────────────────────────────────────────────────

@dataclass
class CombatResult:
    state: str              # "victory" or "defeat"
    summary: list           # list of display strings
    rewards: dict = field(default_factory=dict)  # {"xp": int, "gold": int, "loot": list[str]}
