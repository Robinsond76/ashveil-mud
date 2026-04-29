"""
Strategy rule engine.

A strategy is an ordered list of StrategyRule objects.
At each combat tick, evaluate_strategy() walks Rules top-to-bottom
and returns the first rule whose condition is satisfied.

Condition vocabulary:
  ALWAYS
  HP_SELF < X%
  HP_ALLY < X%
  MP_SELF < X%
  ENEMY_COUNT > N
  HAS_STATUS <status>
  ENEMY_HAS_STATUS <status>
  ALLY_HAS_STATUS <status>

Action vocabulary:
  ATTACK
  USE_SKILL <skill_id>
  USE_ITEM <item_id>
  DEFEND
  FLEE

Target vocabulary:
  NEAREST_ENEMY
  WEAKEST_ENEMY
  STRONGEST_ENEMY
  LOWEST_HP_ALLY
  LOWEST_HP_ENEMY
  SELF
  RANDOM_ENEMY
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from server.engine.combat.actions import Attack, Defend, Flee, UseSkill, UseItem

if TYPE_CHECKING:
    from server.engine.domain.character import Character


@dataclass
class StrategyRule:
    priority: int
    condition: str   # raw condition string, e.g. "HP_SELF < 30%"
    action: str      # raw action string, e.g. "USE_SKILL fireball"
    target: str      # raw target string, e.g. "STRONGEST_ENEMY"

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "condition": self.condition,
            "action": self.action,
            "target": self.target,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyRule":
        return cls(
            priority=d["priority"],
            condition=d["condition"],
            action=d["action"],
            target=d["target"],
        )

    def __str__(self) -> str:
        return (
            f"  [{self.priority:2d}] IF {self.condition} "
            f"DO {self.action} ON {self.target}"
        )


# ── Condition evaluator ──────────────────────────────────────────────────────

def _alive(combatants: list["Character"]) -> list["Character"]:
    return [c for c in combatants if c.is_alive]


def evaluate_condition(
    condition: str,
    actor: "Character",
    allies: list["Character"],   # all allies including actor
    enemies: list["Character"],  # all enemies
) -> bool:
    cond = condition.strip().upper()

    if cond == "ALWAYS":
        return True

    alive_enemies = _alive(enemies)
    alive_allies = _alive(allies)

    # HP_SELF < X%
    if cond.startswith("HP_SELF <"):
        try:
            pct = int(cond.split("<")[1].strip().rstrip("%")) / 100
            return (actor.hp / actor.max_hp) < pct
        except (IndexError, ValueError):
            return False

    # HP_ALLY < X%
    if cond.startswith("HP_ALLY <"):
        try:
            pct = int(cond.split("<")[1].strip().rstrip("%")) / 100
            return any((a.hp / a.max_hp) < pct for a in alive_allies if a is not actor)
        except (IndexError, ValueError):
            return False

    # MP_SELF < X%
    if cond.startswith("MP_SELF <"):
        try:
            pct = int(cond.split("<")[1].strip().rstrip("%")) / 100
            if actor.max_mp == 0:
                return True
            return (actor.mp / actor.max_mp) < pct
        except (IndexError, ValueError):
            return False

    # ENEMY_COUNT > N
    if cond.startswith("ENEMY_COUNT >"):
        try:
            n = int(cond.split(">")[1].strip())
            return len(alive_enemies) > n
        except (IndexError, ValueError):
            return False

    # HAS_STATUS <status>  (actor has this status)
    if cond.startswith("HAS_STATUS "):
        status = cond[len("HAS_STATUS "):].strip().lower()
        return status in getattr(actor, "status_effects", {})

    # ALLY_HAS_STATUS <status>
    if cond.startswith("ALLY_HAS_STATUS "):
        status = cond[len("ALLY_HAS_STATUS "):].strip().lower()
        return any(
            status in getattr(a, "status_effects", {})
            for a in alive_allies
        )

    # ENEMY_HAS_STATUS <status>
    if cond.startswith("ENEMY_HAS_STATUS "):
        status = cond[len("ENEMY_HAS_STATUS "):].strip().lower()
        return any(
            status in getattr(e, "status_effects", {})
            for e in alive_enemies
        )

    return False


# ── Target resolver ──────────────────────────────────────────────────────────

def resolve_target(
    target_str: str,
    actor: "Character",
    allies: list["Character"],
    enemies: list["Character"],
) -> "Character | None":
    t = target_str.strip().upper()
    alive_enemies = _alive(enemies)
    alive_allies = _alive(allies)

    if t == "NEAREST_ENEMY":
        return alive_enemies[0] if alive_enemies else None
    if t == "RANDOM_ENEMY":
        return random.choice(alive_enemies) if alive_enemies else None
    if t == "WEAKEST_ENEMY":
        return min(alive_enemies, key=lambda e: e.hp) if alive_enemies else None
    if t == "STRONGEST_ENEMY":
        return max(alive_enemies, key=lambda e: e.max_hp) if alive_enemies else None
    if t == "LOWEST_HP_ENEMY":
        return min(alive_enemies, key=lambda e: e.hp) if alive_enemies else None
    if t == "LOWEST_HP_ALLY":
        candidates = [a for a in alive_allies if a.is_alive]
        return min(candidates, key=lambda a: a.hp) if candidates else None
    if t == "SELF":
        return actor

    return alive_enemies[0] if alive_enemies else None


# ── Strategy evaluator ───────────────────────────────────────────────────────

def evaluate_strategy(
    actor: "Character",
    allies: list["Character"],
    enemies: list["Character"],
) -> tuple[object, "Character | None"]:
    """
    Walk the actor's strategy rules in priority order.
    Returns (Action, resolved_target) for the first matching rule.
    Falls back to (Attack(), nearest enemy) if nothing matches.
    """
    rules = sorted(
        [StrategyRule.from_dict(r) for r in actor.strategies],
        key=lambda r: r.priority,
    )

    for rule in rules:
        if evaluate_condition(rule.condition, actor, allies, enemies):
            target = resolve_target(rule.target, actor, allies, enemies)
            action_upper = rule.action.strip().upper()
            if action_upper == "ATTACK":
                return Attack(target=target), target
            if action_upper == "DEFEND":
                return Defend(), None
            if action_upper == "FLEE":
                return Flee(), None
            if action_upper.startswith("USE_SKILL"):
                skill_id = action_upper[len("USE_SKILL"):].strip().lower()
                return UseSkill(skill_id=skill_id, target=target), target
            if action_upper.startswith("USE_ITEM"):
                item_id = action_upper[len("USE_ITEM"):].strip().lower()
                return UseItem(item_id=item_id, target=target), target
            # Unknown action — fall through to default
            break

    # Fallback
    alive_enemies = _alive(enemies)
    default_target = alive_enemies[0] if alive_enemies else None
    return Attack(target=default_target), default_target


# ── Strategy editor helpers ───────────────────────────────────────────────────

def list_strategies(character: "Character") -> str:
    rules = sorted(
        [StrategyRule.from_dict(r) for r in character.strategies],
        key=lambda r: r.priority,
    )
    if not rules:
        return "  (no strategies set — will default to ATTACK NEAREST_ENEMY)"
    return "\n".join(str(r) for r in rules)


def add_strategy(
    character: "Character",
    priority: int,
    condition: str,
    action: str,
    target: str,
) -> str:
    # Validate action keyword
    action_upper = action.strip().upper()
    valid_actions = {"ATTACK", "DEFEND", "FLEE"}
    if not any(action_upper.startswith(a) for a in valid_actions | {"USE_SKILL", "USE_ITEM"}):
        return f"Unknown action '{action}'. Valid: ATTACK, DEFEND, FLEE, USE_SKILL <id>, USE_ITEM <id>"

    # Remove any rule at the same priority
    character.strategies = [
        r for r in character.strategies if r.get("priority") != priority
    ]
    rule = StrategyRule(priority=priority, condition=condition, action=action, target=target)
    character.strategies.append(rule.to_dict())
    character.strategies.sort(key=lambda r: r["priority"])
    return f"Strategy rule {priority} set: IF {condition} DO {action} ON {target}"


def remove_strategy(character: "Character", priority: int) -> str:
    before = len(character.strategies)
    character.strategies = [
        r for r in character.strategies if r.get("priority") != priority
    ]
    if len(character.strategies) < before:
        return f"Strategy rule {priority} removed."
    return f"No rule at priority {priority}."


def clear_strategies(character: "Character") -> str:
    character.strategies = []
    return "All strategies cleared."
