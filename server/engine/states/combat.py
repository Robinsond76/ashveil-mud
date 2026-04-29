"""Combat state handler — orchestrates CombatSession."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import DEBUG_NO_DEATH_PENALTY, DEATH_XP_LOSS_PCT, DEATH_GOLD_LOSS_PCT, DEBUG_RESPAWN_ROOM_ID
from server.engine.combat import CombatSession
from server.engine.npc import spawn_npc
from server.engine.states import State

if TYPE_CHECKING:
    from server.engine.game import GameSession


class CombatHandler:
    """Handles combat state — delegates to CombatSession."""

    async def on_enter(self, session: GameSession) -> None:
        """Setup and run combat to completion."""
        ctx = session._state_data
        encounter_group = ctx.get("encounter_group")
        arena_group = ctx.get("arena_group")

        # Spawn enemies
        enemy_npcs = []
        for tid in encounter_group.members:
            npc = spawn_npc(tid, session.class_defs)
            if npc:
                enemy_npcs.append(npc)

        if not enemy_npcs:
            await session.send("  Could not spawn enemies.\n")
            await session.transition_to(State.NAVIGATION)
            return

        # Auto-dismount
        if session._mounted:
            session._was_mounted = True
            session._mounted = False
            await session.send("  The party dismounts as combat begins.\n")

        # Create combat session
        player_party = [session.player] + session.party

        from server.engine.environment import effective_light
        from server.engine.survival import apply_survival_penalties

        room = session.world.get_room(session.current_room_id)
        lighting = effective_light(
            session.player, session.party,
            session.player.lit_sources, session.clock, room
        )
        survival_mult, _ = apply_survival_penalties(session.player, session.party)

        combat = CombatSession(
            player_party=player_party,
            enemy_party=enemy_npcs,
            send=session.send,
            lighting=lighting,
            survival_multiplier=survival_mult,
        )

        session._combat = combat

        # Run combat
        result = await combat.run_and_get_result()

        # Process results
        await session.send("\n".join(result.summary))

        if result.state == "victory":
            encounter_group.mark_defeated()
            combat.collect_rewards(player_party, session.class_defs)
            await self._handle_victory(session)
        else:
            await self._handle_defeat(session)

        session._combat = None

    async def on_exit(self, session: GameSession) -> None:
        """Cleanup combat state."""
        session._combat = None

    async def handle(self, session: GameSession, text: str) -> None:
        """Process minimal combat commands (only HELP is really useful)."""
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)

        if parts and parts[0] == "HELP":
            topic = parts[1] if len(parts) > 1 else ""
            await session._send_help(topic)
            return

        if parts and parts[0] == "USE":
            await session.send("  You cannot use utility skills while in combat.\n")
            return

        await session.send("  Combat is in progress. Your strategies are running...\n")

    async def _handle_victory(self, session: GameSession) -> None:
        """Handle victory transition."""
        # Auto-remount after victory if in outdoor room
        if session._was_mounted:
            room = session.world.get_room(session.current_room_id)
            if room and room.room_type == "outdoor":
                session._mounted = True
                await session.send("  The party remounts and continues on.\n")
            session._was_mounted = False

        # Set battle_look flag in state_data so navigation.on_enter can handle it
        # This avoids duplicate quick look when look_mode is QUICK
        do_quick_look = session.player and session.player.battle_look and session.player.look_mode == "FULL"
        await session.transition_to(State.NAVIGATION, force_quick_look=do_quick_look)

    async def _handle_defeat(self, session: GameSession) -> None:
        """Handle defeat transition."""
        if not DEBUG_NO_DEATH_PENALTY:
            xp_loss = round(session.player.xp * DEATH_XP_LOSS_PCT)
            gold_loss = round(session.player.gold * DEATH_GOLD_LOSS_PCT)
            session.player.xp = max(0, session.player.xp - xp_loss)
            session.player.gold = max(0, session.player.gold - gold_loss)
            await session.send(f"  You lost {xp_loss} XP and {gold_loss} gold.\n")

        # Restore HP/MP
        session.player.hp = session.player.max_hp
        session.player.mp = session.player.max_mp
        for npc in session.party:
            npc.hp = npc.max_hp
            npc.mp = npc.max_mp

        # Respawn
        respawn = DEBUG_RESPAWN_ROOM_ID if DEBUG_NO_DEATH_PENALTY else session.last_campfire_room_id
        session.current_room_id = respawn

        # Set battle_look flag in state_data so navigation.on_enter can handle it
        # This avoids duplicate quick look when look_mode is QUICK
        do_quick_look = session.player and session.player.battle_look and session.player.look_mode == "FULL"
        await session.transition_to(State.NAVIGATION, force_quick_look=do_quick_look)
        await session.send("\n  You find yourself back at the Proving Grounds, wounds healed.\n")
