"""Party/character stats command submodule."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import MODIFIER_BONUS_PER_LEVEL
from server.engine.display.formatting import box as _box
from server.engine.domain.character import MODIFIER_CATALOGUE
from server.engine.domain.skills import (
    render_skills_section,
    can_learn,
    get_skill_tree,
    get_skill,
)

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def _do_stats(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Show character stats."""
    await session.send(session.player.stats_summary() + "\n")


async def _do_gold(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Show gold amount."""
    await session.send(f"  You have {session.player.gold} gold.\n")


async def _do_skills(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Show skill tree."""
    await session.send(
        render_skills_section(
            session.player.class_type,
            session.player.unlocked_skills,
            session.player.skill_points,
            args.lower().strip()
        ) + "\n"
    )


async def _do_learn(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Learn a skill."""
    skill_id = args.strip()
    if not skill_id:
        await session.send("  Learn what? Usage: LEARN <skill_id>\n")
        return

    ok, reason = can_learn(
        session.player.class_type, skill_id,
        session.player.unlocked_skills, session.player.skill_points
    )
    if not ok:
        await session.send(f"  Cannot learn: {reason}\n")
        return

    tree = get_skill_tree(session.player.class_type)
    node = next(n for n in tree if n.skill_id == skill_id)
    session.player.skill_points -= node.unlock_cost
    session.player.unlocked_skills[skill_id] = 1
    skill = get_skill(skill_id)
    await session.send(f"  You learned {skill.name}!\n")


async def _do_modifiers(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Show character modifiers."""
    lines = [f"  Modifier Points available: {session.player.modifier_points}", ""]
    for mod_id, meta in MODIFIER_CATALOGUE.items():
        level = session.player.modifiers.get(mod_id, 0)
        bonus_pct = round(level * MODIFIER_BONUS_PER_LEVEL * 100)
        lines.append(f"  {meta['label']:<25} Lv.{level} (+{bonus_pct}%)")
    await session.send(_box("MODIFIERS", lines))


async def _do_upgrade(session: GameSession, args: str = "", raw_args: str = "") -> None:
    """Upgrade a modifier."""
    mod_id = args.strip().lower()
    if not mod_id:
        await session.send("  Upgrade what? Usage: UPGRADE <modifier_id>\n")
        return

    if mod_id not in MODIFIER_CATALOGUE:
        await session.send(f"  Unknown modifier. Valid: {', '.join(MODIFIER_CATALOGUE.keys())}\n")
        return

    if session.player.modifier_points < 1:
        await session.send("  You have no modifier points.\n")
        return

    session.player.modifier_points -= 1
    session.player.modifiers[mod_id] = session.player.modifiers.get(mod_id, 0) + 1

    meta = MODIFIER_CATALOGUE[mod_id]
    new_level = session.player.modifiers[mod_id]
    new_pct = round(new_level * MODIFIER_BONUS_PER_LEVEL * 100)
    await session.send(
        f"  {meta['label']} improved to Lv.{new_level} (+{new_pct}%).\n"
        f"  Modifier points remaining: {session.player.modifier_points}\n"
    )
