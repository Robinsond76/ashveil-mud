"""Utility skill execution — extracted from GameSession."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.domain.skills import get_skill

if TYPE_CHECKING:
    from server.engine.game import GameSession


async def handle_use_skill(session: "GameSession", skill_id: str) -> None:
    """Handle utility skill usage."""
    skill = get_skill(skill_id)
    if skill is None:
        await session.send(f"  Unknown skill '{skill_id}'. Type SKILLS UTILITY for a list.\n")
        return

    if skill_id not in session.player.unlocked_skills:
        await session.send(
            f"  You haven't unlocked '{skill.name}'. Use SKILLS to see your skill tree.\n"
        )
        return

    if skill.use_context != "utility":
        await session.send(
            f"  '{skill.name}' is a combat skill — use it via your strategy in battle.\n"
        )
        return

    if skill.mp_cost > 0 and session.player.mp < skill.mp_cost:
        await session.send(
            f"  Not enough mana. '{skill.name}' costs {skill.mp_cost} MP "
            f"(you have {session.player.mp}).\n"
        )
        return

    if skill.stamina_cost > 0 and session.player.stamina < skill.stamina_cost:
        await session.send(
            f"  Not enough stamina. '{skill.name}' costs {skill.stamina_cost} "
            f"(you have {int(session.player.stamina)}).\n"
        )
        return

    if skill.required_items:
        party_inv: list[str] = list(session.player.inventory)
        for npc in session.party:
            party_inv.extend(npc.inventory)
        for item_id in skill.required_items:
            if item_id not in party_inv:
                await session.send(
                    f"  You need a {item_id} to use '{skill.name}'.\n"
                )
                return

    # Deduct costs
    session.player.mp -= skill.mp_cost
    session.player.stamina -= skill.stamina_cost

    # Consume items
    if skill.consumes_item and skill.required_items:
        for item_id in skill.required_items:
            if item_id in session.player.inventory:
                session.player.inventory.remove(item_id)
                break
            else:
                for npc in session.party:
                    if item_id in npc.inventory:
                        npc.inventory.remove(item_id)
                        break

    # Execute effect
    await execute_utility_effect(session, skill)


async def execute_utility_effect(session: "GameSession", skill) -> None:
    """Execute utility skill effect."""
    effect = skill.effect_type

    if effect == "unlock_door":
        await session.send(
            "  You probe the lock carefully... but there are no locked exits here.\n"
        )

    elif effect == "reveal_traps":
        await session.send("  You scan the room carefully. You detect no hidden traps.\n")

    elif effect == "provide_light":
        base = session.clock.game_minutes_elapsed if session.clock else 0
        session._arcane_light_until = base + 120
        await session.send(
            "  Arcane light fills the room, illuminating everything clearly for 120 game-minutes.\n"
        )

    elif effect == "identify_item":
        await session.send("  You sense the arcane properties of the items around you.\n")

    elif effect == "bless_camp":
        session._bless_camp_active = True
        await session.send(
            "  You bless the camp. Your next rest will reduce hunger drain by 50%.\n"
        )

    elif effect == "purify_food":
        await session.send("  You purify the food in your pack.\n")

    elif effect == "fortify_party":
        session._fortify_active = True
        await session.send(
            "  You bolster the party's defenses. Incoming damage will be reduced until your next battle.\n"
        )

    else:
        await session.send(f"  You use {skill.name}.\n")
