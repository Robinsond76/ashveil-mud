"""
Skill model and registry.
Skills are loaded once from data/skills/*.json.
Skill trees are embedded in data/classes/classes.json.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    id: str
    name: str
    description: str
    class_type: str
    mp_cost: int
    cooldown_ticks: int
    effect_type: str
    effect_params: dict[str, Any] = field(default_factory=dict)
    use_context: str = "combat"
    stamina_cost: int = 0
    required_items: list[str] = field(default_factory=list)
    consumes_item: bool = False

    def short_desc(self) -> str:
        return f"{self.name} (MP:{self.mp_cost}, CD:{self.cooldown_ticks}t) — {self.description}"


@dataclass
class SkillTreeNode:
    skill_id: str
    unlock_cost: int          # skill points required
    prerequisites: list[str]  # skill IDs that must be unlocked first


# ── Registry ────────────────────────────────────────────────────────────────

_SKILL_REGISTRY: dict[str, Skill] = {}
_SKILL_TREES: dict[str, list[SkillTreeNode]] = {}  # class_type → tree nodes


def load_skills(data_dir: str) -> None:
    """Load skill definitions from data/skills/*.json and trees from classes.json."""
    skills_dir = os.path.join(data_dir, "skills")
    for fname in os.listdir(skills_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(skills_dir, fname), encoding="utf-8") as f:
            raw_list = json.load(f)
        for raw in raw_list:
            skill = Skill(
                id=raw["id"],
                name=raw["name"],
                description=raw.get("description", ""),
                class_type=raw["class_type"],
                mp_cost=raw.get("mp_cost", 0),
                cooldown_ticks=raw.get("cooldown_ticks", 3),
                effect_type=raw["effect_type"],
                effect_params=raw.get("effect_params", {}),
                use_context=raw.get("use_context", "combat"),
                stamina_cost=raw.get("stamina_cost", 0),
                required_items=raw.get("required_items", []),
                consumes_item=raw.get("consumes_item", False),
            )
            _SKILL_REGISTRY[skill.id] = skill

    # Load skill trees from classes.json
    classes_path = os.path.join(data_dir, "classes", "classes.json")
    with open(classes_path, encoding="utf-8") as f:
        classes_data = json.load(f)
    for class_type, class_def in classes_data.items():
        tree = []
        for node_raw in class_def.get("skill_tree", []):
            tree.append(SkillTreeNode(
                skill_id=node_raw["id"],
                unlock_cost=node_raw["unlock_cost"],
                prerequisites=node_raw.get("prerequisites", []),
            ))
        _SKILL_TREES[class_type] = tree


def get_skill(skill_id: str) -> Skill | None:
    return _SKILL_REGISTRY.get(skill_id)


def get_skill_tree(class_type: str) -> list[SkillTreeNode]:
    return _SKILL_TREES.get(class_type, [])


def get_utility_skills(class_type: str) -> list[Skill]:
    return [s for s in _SKILL_REGISTRY.values()
            if s.class_type == class_type and s.use_context == "utility"]


def get_combat_skills(class_type: str) -> list[Skill]:
    return [s for s in _SKILL_REGISTRY.values()
            if s.class_type == class_type and s.use_context == "combat"]


def render_skills_section(
    class_type: str,
    unlocked: dict[str, int],
    skill_points: int,
    context: str = "",
) -> str:
    context = context.strip().lower()
    if context == "utility":
        return _render_utility_section(class_type, unlocked)
    elif context == "combat":
        return _render_combat_section(class_type, unlocked, skill_points)
    else:
        return (
            _render_combat_section(class_type, unlocked, skill_points)
            + "\n"
            + _render_utility_section(class_type, unlocked)
        )


def _render_combat_section(
    class_type: str,
    unlocked: dict[str, int],
    skill_points: int,
) -> str:
    tree = get_skill_tree(class_type)
    if not tree:
        return "  No combat skills found."
    lines = [
        "  ── COMBAT SKILLS ──────────────────────────────────────",
        f"  Skill Points available: {skill_points}",
        "",
    ]
    for node in tree:
        skill = get_skill(node.skill_id)
        if skill is None:
            continue
        status = "[LEARNED]" if node.skill_id in unlocked else "[ LOCKED ]"
        lines.append(f"  {status} {skill.name} (cost: {node.unlock_cost} pt)")
        lines.append(f"           {skill.description}")
        if node.prerequisites:
            lines.append(f"           Requires: {', '.join(node.prerequisites)}")
        lines.append("")
    return "\n".join(lines)


def _render_utility_section(
    class_type: str,
    unlocked: dict[str, int],
) -> str:
    skills = get_utility_skills(class_type)
    lines = [
        "  ── UTILITY SKILLS ──────────────────────────────────────",
        "",
    ]
    if not skills:
        lines.append("  No utility skills available for your class.")
    else:
        for skill in skills:
            status = "[LEARNED]" if skill.id in unlocked else "[ LOCKED ]"
            cost_parts: list[str] = []
            if skill.mp_cost > 0:
                cost_parts.append(f"MP:{skill.mp_cost}")
            if skill.stamina_cost > 0:
                cost_parts.append(f"Stamina:{skill.stamina_cost}")
            cost_str = ", ".join(cost_parts) if cost_parts else "Free"
            lines.append(f"  {status} {skill.name} ({cost_str}) — {skill.description}")
            if skill.required_items:
                lines.append(f"           Requires: {', '.join(skill.required_items)}")
            lines.append("")
    return "\n".join(lines)


def can_learn(
    class_type: str,
    skill_id: str,
    unlocked: dict[str, int],
    skill_points: int,
) -> tuple[bool, str]:
    """
    Returns (True, "") if the character can learn/upgrade the skill,
    or (False, reason) otherwise.
    """
    tree = get_skill_tree(class_type)
    node = next((n for n in tree if n.skill_id == skill_id), None)
    if node is None:
        return False, f"'{skill_id}' is not in the {class_type} skill tree."
    # Check class ownership
    skill = get_skill(skill_id)
    if skill is None:
        return False, f"Unknown skill '{skill_id}'."
    if skill.class_type != class_type:
        return False, f"'{skill_id}' is not available to {class_type}."
    # Check prerequisites
    for prereq in node.prerequisites:
        if prereq not in unlocked:
            prereq_skill = get_skill(prereq)
            prereq_name = prereq_skill.name if prereq_skill else prereq
            return False, f"Requires '{prereq_name}' first."
    # Check points
    if skill_points < node.unlock_cost:
        return False, f"Requires {node.unlock_cost} skill point(s). You have {skill_points}."
    return True, ""


def render_skill_tree(
    class_type: str,
    unlocked: dict[str, int],
    skill_points: int,
) -> str:
    tree = get_skill_tree(class_type)
    if not tree:
        return "No skill tree found."
    lines = [f"  Skill Points available: {skill_points}", ""]
    for node in tree:
        skill = get_skill(node.skill_id)
        if skill is None:
            continue
        status = "[LEARNED]" if node.skill_id in unlocked else "[ LOCKED ]"
        prereq_str = ""
        if node.prerequisites:
            prereq_str = f"  Requires: {', '.join(node.prerequisites)}"
        lines.append(f"  {status} {skill.name} (cost: {node.unlock_cost} pt)")
        lines.append(f"           {skill.description}")
        if prereq_str:
            lines.append(f"           {prereq_str}")
        lines.append("")
    return "\n".join(lines)
