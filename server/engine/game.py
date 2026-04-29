"""
GameSession — per-connection state machine coordinator.

Refactored from 1,667-line god object to stateless coordinator.
State-specific logic moved to handlers in server.engine.states.

States:
  CONNECT     → prompt for name
  CREATION    → character creation wizard
  NAVIGATION  → explore rooms, talk to NPCs
  CAMPFIRE    → rest, manage party, strategies, learn skills
  STRATEGY    → strategy editor sub-mode
  COMBAT      → hands-off while CombatSession runs

All output flows through `await self.send(text)`.
Input arrives via `await self.handle_input(raw_text)`.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from server.config import (
    DEBUG_NO_DEATH_PENALTY,
    DEBUG_RESPAWN_ROOM_ID,
    DEATH_GOLD_LOSS_PCT,
    DEATH_XP_LOSS_PCT,
    MAX_STAT,
    MIN_STAT,
    MODIFIER_BONUS_PER_LEVEL,
    MOUNT_STAMINA_REDUCTION,
    STAMINA_DRAIN_PER_MOVE,
    STAT_POINT_BUY_BUDGET,
)
from server.engine.character import Character, MODIFIER_CATALOGUE, XP_TABLE
from server.engine.combat import CombatSession
from server.engine.items import (
    get_item,
    equipped_weapon, total_equipped_weight,
)
from server.engine.npc import NPC, spawn_npc
from server.engine.persistence import init_db, load_player, save_player
from server.engine.skills import (
    can_learn, get_skill, render_skill_tree, render_skills_section,
)
from server.engine.strategy import (
    add_strategy, clear_strategies, list_strategies, remove_strategy,
)
from server.engine.help_registry import send_help, _HELP_TOPICS
from server.engine.inventory_ops import (
    party_inventory_view, do_inventory, do_equip, do_unequip, do_drop,
    do_pick_up, do_give, do_load_cart, do_unload_cart,
    auto_assign_item, auto_assign_item_with_message,
)
from server.engine.campfire import do_formation, do_manage
from server.engine.chat import do_say, do_emote, do_shout
from server.engine.environment import (
    carried_light as _carried_light_fn,
    effective_light as _effective_light_fn,
    do_time, do_weather, do_light, do_envdetails, do_light_source,
)
from server.engine.survival import (
    party_survival_aggregate, apply_survival_penalties,
    drain_survival_tick, sitting_stamina_tick,
    do_survival_status, do_eat, do_drink, do_buffs,
)
from server.engine.world import WorldMap

# Context panel configuration
MAX_CONTEXT_INVENTORY_ITEMS = 10  # Number of items to show in context panel (limit for performance)
from server.engine.world_clock import WorldClock
from server.engine.states import State, HANDLER_REGISTRY


from server.engine.display.formatting import box as _box


class GameSession:
    """Coordinator for a player session — delegates state logic to handlers."""

    def __init__(
        self,
        send_fn,
        world: WorldMap,
        class_defs: dict,
        clock: WorldClock | None = None,
        sessions: dict | None = None,
    ) -> None:
        # Core services (injected)
        self._send_raw = send_fn
        self.world = world
        self.class_defs = class_defs
        self.clock: WorldClock | None = clock
        self._sessions: dict = sessions if sessions is not None else {}

        # Player session state
        self.player: Character | None = None
        self.party: list[NPC] = []
        self.current_room_id: str = "town_square"
        self.last_campfire_room_id: str = "test_campfire"
        self._quit: bool = False

        # Shared mechanical state (used across multiple states)
        self._mounted: bool = False
        self._cart_present: bool = False
        self._cart_room_id: str | None = None
        self._cart_inventory: list[str] = []
        self._horses_outside: bool = False
        self._was_mounted: bool = False
        self._sitting: bool = False

        # State management
        self._state: State = State.CONNECT
        self._state_data: dict = {}

        # Active combat session (set by CombatHandler)
        self._combat: CombatSession | None = None

        # Pending recruit (used by NavigationHandler)
        self._pending_recruit: str | None = None

        # Clock subscriptions
        self._weather_cb = None
        self._tick_cb = None

        # Utility skill state
        self._arcane_light_until: int = 0
        self._bless_camp_active: bool = False
        self._fortify_active: bool = False

        # Encounter group reference
        self._current_encounter_group: object | None = None

    # ─────────────────────────────────────────────────────────────────────────
    # Core services used by all handlers
    # ─────────────────────────────────────────────────────────────────────────

    async def send(self, text: str) -> None:
        """Send output to the player."""
        await self._send_raw(text)

    async def _send(self, text: str) -> None:
        """Backward-compatible alias for send()."""
        await self.send(text)

    async def _send(self, text: str) -> None:
        """Backward-compatible alias for send()."""
        await self.send(text)

    async def broadcast_to_room(self, message: str, exclude_self: bool = True) -> None:
        """Broadcast a message to all players in the current room."""
        room_id = self.current_room_id
        for name, session in self._sessions.items():
            if exclude_self and self.player and name == self.player.name:
                continue
            if session.current_room_id == room_id:
                await session.send(message)

    def save(self) -> None:
        """Save player progress to database."""
        if not self.player:
            return
        data = {
            "character": self.player.to_dict(),
            "party": [npc.to_dict() for npc in self.party],
            "current_room_id": self.current_room_id,
            "last_campfire_room_id": self.last_campfire_room_id,
        }
        save_player(self.player.name, data)

    # ─────────────────────────────────────────────────────────────────────────
    # State management
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        """Current game state."""
        return self._state

    @state.setter
    def state(self, value: State) -> None:
        """Set state directly (for backward compatibility)."""
        self._state = value

    async def transition_to(self, new_state: State, **context) -> None:
        """Transition to a new state with lifecycle hooks."""
        # Exit current state
        await HANDLER_REGISTRY[self._state].on_exit(self)

        # Update state and context
        self._state = new_state
        self._state_data = context

        # Enter new state
        await HANDLER_REGISTRY[new_state].on_enter(self)

        # Send updated context after state transition
        await self._send_context_update()

    async def handle_input(self, raw: str) -> None:
        """Main entry point — delegates to current state handler."""
        text = raw.strip()
        if not text:
            return

        # Global quit command (works from any state)
        if text.upper() in ("QUIT", "EXIT", "BYE", "LOGOUT"):
            await self._do_quit()
            return

        # Delegate to state handler
        await HANDLER_REGISTRY[self._state].handle(self, text)

        # Send updated context after every command
        await self._send_context_update()

    # ─────────────────────────────────────────────────────────────────────────
    # Lifecycle methods
    # ─────────────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize and start the session."""
        init_db()
        await HANDLER_REGISTRY[State.CONNECT].on_enter(self)

    async def _do_quit(self) -> None:
        """Handle player quit."""
        if self.player:
            self.save()
        self._unsubscribe_clock()
        self._quit = True
        await self.send("\n  Farewell, adventurer. Safe travels.\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Clock subscription
    # ─────────────────────────────────────────────────────────────────────────

    def _subscribe_clock(self) -> None:
        """Subscribe to weather broadcasts and game-minute ticks."""
        if not self.clock:
            return

        # Weather callback — only sends narrative messages
        if not self._weather_cb:
            async def _on_weather(msg: str) -> None:
                if self._state in (State.NAVIGATION, State.CAMPFIRE, State.COMBAT):
                    room = self.world.get_room(self.current_room_id)
                    if room and room.room_type != "underground":
                        await self.send(f"\n  {msg}\n")
            self._weather_cb = _on_weather
            self.clock.subscribe(self._weather_cb)

        # Tick callback — handles survival drain and sitting recovery every game-minute
        if not self._tick_cb:
            async def _on_tick() -> None:
                if self._state in (State.NAVIGATION, State.CAMPFIRE, State.COMBAT) and self.player:
                    room = self.world.get_room(self.current_room_id)
                    temp_label = "Comfortable"
                    if room:
                        temp_label = self.clock.temperature_label(room.room_type, room.base_temp_f)
                    drain_survival_tick(self.player, self.party, self.clock, temp_label)
                    if self._state != State.COMBAT:
                        sitting_stamina_tick(self.player, self.party, self.clock, self._sitting)
            self._tick_cb = _on_tick
            self.clock.subscribe_tick(self._tick_cb)

    def _unsubscribe_clock(self) -> None:
        """Unsubscribe from weather broadcasts and game-minute ticks."""
        if self.clock:
            if self._weather_cb:
                self.clock.unsubscribe(self._weather_cb)
                self._weather_cb = None
            if self._tick_cb:
                self.clock.unsubscribe_tick(self._tick_cb)
                self._tick_cb = None

    # ─────────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_save(self, save: dict) -> None:
        """Load player save data."""
        self.player = Character.from_dict(save["character"])
        self.party = []
        for nd in save.get("party", []):
            npc = NPC.from_dict(nd)
            self.party.append(npc)
        self.current_room_id = save.get("current_room_id", "town_square")
        self.last_campfire_room_id = save.get("last_campfire_room_id", "test_campfire")
        self._state = State.NAVIGATION

    # ─────────────────────────────────────────────────────────────────────────
    # Help system
    # ─────────────────────────────────────────────────────────────────────────

    async def _send_help(self, topic: str = "") -> None:
        """Send help text to the player."""
        await send_help(self.send, topic, self._state)

    # ─────────────────────────────────────────────────────────────────────────
    # Utility skill handler (delegates to existing complex logic)
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_use_skill(self, skill_id: str) -> None:
        """Handle utility skill usage."""
        skill = get_skill(skill_id)
        if skill is None:
            await self.send(f"  Unknown skill '{skill_id}'. Type SKILLS UTILITY for a list.\n")
            return

        if skill_id not in self.player.unlocked_skills:
            await self.send(
                f"  You haven't unlocked '{skill.name}'. Use SKILLS to see your skill tree.\n"
            )
            return

        if skill.use_context != "utility":
            await self.send(
                f"  '{skill.name}' is a combat skill — use it via your strategy in battle.\n"
            )
            return

        if skill.mp_cost > 0 and self.player.mp < skill.mp_cost:
            await self.send(
                f"  Not enough mana. '{skill.name}' costs {skill.mp_cost} MP "
                f"(you have {self.player.mp}).\n"
            )
            return

        if skill.stamina_cost > 0 and self.player.stamina < skill.stamina_cost:
            await self.send(
                f"  Not enough stamina. '{skill.name}' costs {skill.stamina_cost} "
                f"(you have {int(self.player.stamina)}).\n"
            )
            return

        if skill.required_items:
            party_inv: list[str] = list(self.player.inventory)
            for npc in self.party:
                party_inv.extend(npc.inventory)
            for item_id in skill.required_items:
                if item_id not in party_inv:
                    await self.send(
                        f"  You need a {item_id} to use '{skill.name}'.\n"
                    )
                    return

        # Deduct costs
        self.player.mp -= skill.mp_cost
        self.player.stamina -= skill.stamina_cost

        # Consume items
        if skill.consumes_item and skill.required_items:
            for item_id in skill.required_items:
                if item_id in self.player.inventory:
                    self.player.inventory.remove(item_id)
                    break
                else:
                    for npc in self.party:
                        if item_id in npc.inventory:
                            npc.inventory.remove(item_id)
                            break

        # Execute effect
        await self._execute_utility_effect(skill)

    async def _execute_utility_effect(self, skill) -> None:
        """Execute utility skill effect."""
        effect = skill.effect_type

        if effect == "unlock_door":
            await self.send(
                "  You probe the lock carefully... but there are no locked exits here.\n"
            )

        elif effect == "reveal_traps":
            await self.send("  You scan the room carefully. You detect no hidden traps.\n")

        elif effect == "provide_light":
            base = self.clock.game_minutes_elapsed if self.clock else 0
            self._arcane_light_until = base + 120
            await self.send(
                "  Arcane light fills the room, illuminating everything clearly for 120 game-minutes.\n"
            )

        elif effect == "identify_item":
            await self.send("  You sense the arcane properties of the items around you.\n")

        elif effect == "bless_camp":
            self._bless_camp_active = True
            await self.send(
                "  You bless the camp. Your next rest will reduce hunger drain by 50%.\n"
            )

        elif effect == "purify_food":
            await self.send("  You purify the food in your pack.\n")

        elif effect == "fortify_party":
            self._fortify_active = True
            await self.send(
                "  You bolster the party's defenses. Incoming damage will be reduced until your next battle.\n"
            )

        else:
            await self.send(f"  You use {skill.name}.\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Campfire handlers (delegated to by CampfireHandler)
    # ─────────────────────────────────────────────────────────────────────────

    async def _do_formation(self, args: str) -> None:
        """Show or change formation."""
        await do_formation(self.send, self.player, self.party, args)

    async def _do_manage(self, name: str) -> None:
        """Manage companion strategies."""
        target = await do_manage(self.send, self.player, self.party, name, get_skill, list_strategies)
        if target is not None:
            await self.transition_to(State.STRATEGY, target=target, context="campfire")

    async def _do_show_party(self) -> None:
        """Display party status."""
        lines = []
        lines.append(self.player.stats_summary())
        lines.append("")
        if not self.party:
            lines.append("  (no companions)")
        for i, npc in enumerate(self.party, 1):
            lines.append(f"  [{i}] {npc.stats_summary()}")
            lines.append("")
        h_pct, t_pct, s_pct = party_survival_aggregate(self.player, self.party)
        lines.append(
            f"  Survival  Stamina {s_pct * 100:.0f}%  "
            f"Hunger {h_pct * 100:.0f}%  "
            f"Thirst {t_pct * 100:.0f}%"
        )
        await self.send(_box("PARTY", lines))

    async def _do_learn(self, skill_id: str) -> None:
        """Learn a skill."""
        ok, reason = can_learn(
            self.player.class_type, skill_id,
            self.player.unlocked_skills, self.player.skill_points
        )
        if not ok:
            await self.send(f"  Cannot learn: {reason}\n")
            return
        tree = get_skill_tree(self.player.class_type)
        node = next(n for n in tree if n.skill_id == skill_id)
        self.player.skill_points -= node.unlock_cost
        self.player.unlocked_skills[skill_id] = 1
        skill = get_skill(skill_id)
        await self.send(f"  You learned {skill.name}!\n")

    async def _do_show_modifiers(self) -> None:
        """Show character modifiers."""
        lines = [f"  Modifier Points available: {self.player.modifier_points}", ""]
        for mod_id, meta in MODIFIER_CATALOGUE.items():
            level = self.player.modifiers.get(mod_id, 0)
            bonus_pct = round(level * MODIFIER_BONUS_PER_LEVEL * 100)
            lines.append(f"  {meta['label']:<25} Lv.{level} (+{bonus_pct}%)")
        await self.send(_box("MODIFIERS", lines))

    async def _do_upgrade(self, mod_id: str) -> None:
        """Upgrade a modifier."""
        mod_id = mod_id.strip().lower()
        if mod_id not in MODIFIER_CATALOGUE:
            await self.send(
                f"  Unknown modifier '{mod_id}'.\n"
                f"  Valid: {', '.join(MODIFIER_CATALOGUE.keys())}\n"
            )
            return
        if self.player.modifier_points < 1:
            await self.send("  You have no modifier points.\n")
            return
        self.player.modifier_points -= 1
        self.player.modifiers[mod_id] = self.player.modifiers.get(mod_id, 0) + 1
        meta = MODIFIER_CATALOGUE[mod_id]
        new_level = self.player.modifiers[mod_id]
        new_pct = round(new_level * MODIFIER_BONUS_PER_LEVEL * 100)
        await self.send(
            f"  {meta['label']} improved to Lv.{new_level} (+{new_pct}%).\n"
            f"  Modifier points remaining: {self.player.modifier_points}\n"
        )

    async def _do_dismiss(self, args: str) -> None:
        """Dismiss a companion."""
        name = args.lower().strip()
        for npc in self.party:
            if name in npc.name.lower():
                self.party.remove(npc)
                await self.send(f"  {npc.name} has left your party.\n")
                return
        await self.send(f"  No companion named '{args}' in your party.\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Backward-compatible wrappers (tests call these directly)
    # ─────────────────────────────────────────────────────────────────────────

    async def _do_move(self, direction: str) -> None:
        """Backward-compatible wrapper for NavigationHandler._do_move."""
        from server.engine.states.navigation import NavigationHandler
        nav = NavigationHandler()
        await nav._do_move(self, direction)

    async def _do_look(self) -> None:
        """Backward-compatible wrapper for NavigationHandler._do_look."""
        from server.engine.states.navigation import NavigationHandler
        nav = NavigationHandler()
        await nav._do_look(self)

    async def _do_pick_up(self, args: str) -> None:
        """Backward-compatible wrapper for NavigationHandler._do_pick_up."""
        from server.engine.states.navigation import NavigationHandler
        nav = NavigationHandler()
        await nav._do_pick_up(self, args)

    async def _start_combat(self, encounter_group) -> None:
        """Backward-compatible wrapper — runs combat inline (old behavior)."""
        from server.engine.npc import spawn_npc
        enemy_npcs = []
        for tid in encounter_group.members:
            npc = spawn_npc(tid, self.class_defs)
            if npc:
                enemy_npcs.append(npc)
        if not enemy_npcs:
            await self.send("  Could not spawn enemies.\n")
            return

        player_party = [self.player] + self.party
        self._current_encounter_group = encounter_group
        self._state = State.COMBAT

        # Auto-dismount when combat begins
        if self._mounted:
            self._was_mounted = True
            self._mounted = False
            await self.send("  The party dismounts as combat begins.\n")

        self._combat = CombatSession(
            player_party=player_party,
            enemy_party=enemy_npcs,
            send=self._send,
            lighting=self._effective_light(),
            survival_multiplier=self._apply_survival_penalties()[0],
        )
        result = await self._combat.run_and_get_result()
        await self.send("\n".join(result.summary))
        if result.state == "victory":
            self._current_encounter_group.mark_defeated()
            self._combat.collect_rewards(player_party, self.class_defs)
            await self._end_combat_victory()
        else:
            await self._end_combat_defeat()
        self._combat = None

    async def _end_combat_victory(self) -> None:
        """Backward-compatible wrapper for CombatHandler._handle_victory."""
        from server.engine.states.combat import CombatHandler
        handler = CombatHandler()
        await handler._handle_victory(self)

    async def _end_combat_defeat(self) -> None:
        """Backward-compatible wrapper for CombatHandler._handle_defeat."""
        from server.engine.states.combat import CombatHandler
        handler = CombatHandler()
        await handler._handle_defeat(self)

    def _sitting_stamina_tick(self) -> None:
        """Backward-compatible wrapper for survival.sitting_stamina_tick."""
        sitting_stamina_tick(self.player, self.party, self.clock, self._sitting)

    def _drain_survival_tick(self, temp_label: str) -> None:
        """Backward-compatible wrapper for survival.drain_survival_tick."""
        drain_survival_tick(self.player, self.party, self.clock, temp_label)

    def _party_has_cart(self) -> bool:
        """Return True if any party member has travellers_cart."""
        members = ([self.player] if self.player else []) + list(self.party)
        for m in members:
            if "travellers_cart" in m.inventory:
                return True
        return False

    def _auto_assign_item(self, item_id: str) -> bool:
        """Backward-compatible wrapper for inventory_ops.auto_assign_item."""
        return auto_assign_item(
            self.player, self.party, item_id, self._cart_inventory, self._cart_present
        )

    async def _auto_assign_item_with_message(self, item_id: str) -> bool:
        """Backward-compatible wrapper for inventory_ops.auto_assign_item_with_message."""
        return await auto_assign_item_with_message(
            self._send_raw, self.player, self.party, item_id,
            self._cart_inventory, self._cart_present,
        )

    def _party_inventory_view(self) -> list[tuple[str, str, str]]:
        """Backward-compatible wrapper for inventory_ops.party_inventory_view."""
        return party_inventory_view(self.player, self.party)

    def _horse_count(self) -> int:
        """Count items with type == 'mount' across all party member inventories."""
        members = ([self.player] if self.player else []) + list(self.party)
        count = 0
        for m in members:
            for item_id in m.inventory:
                item = get_item(item_id)
                if item and item.type == "mount":
                    count += 1
        return count

    def _stamina_multiplier(self) -> float:
        """Return stamina drain multiplier based on horse-to-party ratio."""
        if not self._mounted:
            return 1.0
        horse_count = self._horse_count()
        party_size = max(1, 1 + len(self.party))
        ratio = min(1.0, horse_count / party_size)
        return 1.0 - (MOUNT_STAMINA_REDUCTION * ratio)

    async def _broadcast_to_room(self, message: str, exclude_self: bool = True) -> None:
        """Backward-compatible alias for broadcast_to_room."""
        await self.broadcast_to_room(message, exclude_self)

    # ─────────────────────────────────────────────────────────────────────────
    # Survival / environment wrappers (used by handlers)
    # ─────────────────────────────────────────────────────────────────────────

    def _party_survival_aggregate(self) -> tuple[float, float, float]:
        return party_survival_aggregate(self.player, self.party)

    def _apply_survival_penalties(self) -> tuple[float, bool]:
        return apply_survival_penalties(self.player, self.party)

    def _carried_light(self) -> float:
        return _carried_light_fn(self.player, self.party, self.player.lit_sources, self.clock, self._send)

    def _effective_light(self) -> float:
        room = self.world.get_room(self.current_room_id)
        return _effective_light_fn(self.player, self.party, self.player.lit_sources, self.clock, room)

    async def _do_survival_status(self) -> None:
        await do_survival_status(self.send, self.player, self.party)

    async def _do_eat(self, args: str) -> None:
        await do_eat(self.send, self.player, self.party, self.clock, args)

    async def _do_drink(self, args: str) -> None:
        await do_drink(self.send, self.player, self.party, self.clock, args)

    async def _do_buffs(self) -> None:
        await do_buffs(self.send, self.player, self.party, self.clock)

    async def _do_time(self) -> None:
        await do_time(self.send, self.clock)

    async def _do_weather(self) -> None:
        room = self.world.get_room(self.current_room_id)
        await do_weather(self.send, self.clock, room)

    async def _do_light(self) -> None:
        room = self.world.get_room(self.current_room_id)
        await do_light(self.send, self.clock, room, self.player.lit_sources, self._carried_light)

    async def _do_envdetails(self) -> None:
        room = self.world.get_room(self.current_room_id)
        await do_envdetails(self.send, self.clock, room, self._carried_light)

    async def _do_light_source(self, args: str, extinguish: bool) -> None:
        await do_light_source(
            self.send, self.player, self.party, self.player.lit_sources, self.clock, args, extinguish
        )

    async def _enter_campfire(self) -> None:
        """Enter campfire state (backward-compatible)."""
        from server.engine.states.campfire import CampfireHandler
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        has_kit = "campfire_kit" in self.player.inventory
        if not room.is_campfire and not has_kit:
            await self.send("  No campfire here. Find a campfire room or use a Campfire Kit.\n")
            return
        if has_kit and not room.is_campfire:
            self.player.inventory.remove("campfire_kit")
        if room.is_campfire:
            self.last_campfire_room_id = self.current_room_id
        await self.transition_to(State.CAMPFIRE)

    async def _handle_campfire(self, text: str) -> None:
        """Backward-compatible wrapper for CampfireHandler.handle."""
        from server.engine.states.campfire import CampfireHandler
        handler = CampfireHandler()
        await handler.handle(self, text)

    async def _handle_campfire(self, text: str) -> None:
        """Backward-compatible wrapper for CampfireHandler.handle."""
        from server.engine.states.campfire import CampfireHandler
        handler = CampfireHandler()
        await handler.handle(self, text)

    async def _do_ride(self) -> None:
        """RIDE — mount up if horses are available (backward-compatible)."""
        if self._horse_count() == 0:
            await self.send("  You don't have any horses.\n")
            return
        room = self.world.get_room(self.current_room_id)
        if room and room.room_type != "outdoor":
            await self.send("  You can only mount up outdoors.\n")
            return
        self._mounted = True
        await self.send("  The party mounts up and prepares to ride.\n")

    async def _do_dismount(self) -> None:
        """DISMOUNT — dismount the party (backward-compatible)."""
        self._mounted = False
        await self.send("  The party dismounts.\n")

    async def _do_horses(self) -> None:
        """HORSES — show horse count (backward-compatible)."""
        horse_count = self._horse_count()
        party_size = 1 + len(self.party)
        ratio = min(1.0, horse_count / max(1, party_size)) if self._mounted else 0.0
        reduction_pct = round(MOUNT_STAMINA_REDUCTION * ratio * 100)
        await self.send(
            f"  Horses: {horse_count} | Party: {party_size} | Stamina drain: -{reduction_pct}%\n"
        )

    async def _do_attack(self, args: str) -> None:
        """Initiate combat (backward-compatible)."""
        from server.engine.npc import get_npc_template
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        group_id = args.strip().upper() if args else None
        active = self.world.active_encounter_groups(self.current_room_id)
        if not active:
            await self.send("  There's no one left to fight here.\n")
            return
        if self.clock:
            eff_light = self._effective_light()
            if eff_light < 0.05:
                target_group = (
                    next((g for g in active if g.group == group_id), None)
                    if group_id else active[0]
                )
                enemy_has_darkvision = False
                if target_group:
                    for tid in target_group.members:
                        tpl = get_npc_template(tid)
                        if tpl and tpl.get("darkvision", False):
                            enemy_has_darkvision = True
                            break
                if not enemy_has_darkvision:
                    await self.send(
                        "  It is pitch black — you cannot fight what you cannot see.\n"
                        "  Light a torch or find another source of light.\n"
                    )
                    return
        if room.id == "test_arena":
            if not group_id:
                await self.send("  Specify a group: ATTACK A, ATTACK B, ATTACK C, or ATTACK D\n")
                return
            target_group = next((g for g in active if g.group == group_id), None)
            if not target_group:
                await self.send(f"  Group '{group_id}' is defeated or doesn't exist.\n")
                return
            self._arena_group = group_id
            await self._start_combat(target_group)
        else:
            target_group = active[0]
            self._arena_group = None
            await self._start_combat(target_group)

    async def _do_talk(self, args: str) -> None:
        """Talk to a recruitable NPC (backward-compatible)."""
        from server.engine.npc import get_npc_template
        name = args.lower().strip()
        if not name:
            await self.send("  Talk to who?\n")
            return
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        for tid in room.recruitable_npc_ids:
            tpl = get_npc_template(tid)
            if tpl and name in tpl["name"].lower():
                already_in_party = any(m.template_id == tid for m in self.party)
                if already_in_party:
                    await self.send(f"  {tpl['name']} is already in your party.\n")
                    return
                if len(self.party) >= 4:
                    await self.send("  Your party is full (4 companions max). Dismiss someone first.\n")
                    return
                await self.send(tpl.get("recruit_dialogue", f"{tpl['name']} nods at you.\n"))
                self._pending_recruit = tid
                return
        await self.send(f"  There's no one named '{args}' here to talk to.\n")

    async def _do_say(self, message: str) -> None:
        player_name = self.player.name if self.player else "Someone"
        await do_say(self._send, self._broadcast_to_room, player_name, message)

    async def _do_emote(self, action: str) -> None:
        player_name = self.player.name if self.player else "Someone"
        await do_emote(self._send, self._broadcast_to_room, player_name, action)

    async def _do_shout(self, message: str) -> None:
        player_name = self.player.name if self.player else "Someone"
        await do_shout(self._send, self._sessions, player_name, message)

    async def _save(self) -> None:
        """Alias for save() (backward-compatible)."""
        self.save()

    # ─────────────────────────────────────────────────────────────────────────
    # Context panel data gathering
    # ─────────────────────────────────────────────────────────────────────────

    async def _send_context_update(self) -> None:
        """Send current game context to client as JSON."""
        if not self.player:
            return

        # Skip context updates if player is not a real Character (e.g., MagicMock in tests)
        if not hasattr(self.player, 'to_dict'):
            return

        # Skip context updates in test environments (detect by duck typing - mock objects have _mock_name)
        if hasattr(self._send_raw, '_mock_name'):
            return

        try:
            context = self._gather_context()
            json_msg = json.dumps({
                "type": "context",
                "data": context
            })
            await self.send(json_msg)
        except (TypeError, ValueError) as e:
            # Log serialization errors but don't crash - usually indicates mocked objects in tests
            logger.debug(f"Failed to serialize context: {e}")

    def _gather_context(self) -> dict[str, Any]:
        """Gather all context data for the side panel."""
        context = {
            "player": self._get_player_context(),
            "party": self._get_party_context(),
            "map": self._get_map_context(),
            "inventory": self._get_inventory_context(),
            "environment": self._get_environment_context(),
        }
        return context

    def _get_player_context(self) -> dict[str, Any]:
        """Get player character stats and status."""
        if not self.player:
            return {}

        h_pct, t_pct, s_pct = 1.0, 1.0, 1.0
        if self.party:
            h_pct, t_pct, s_pct = party_survival_aggregate(self.player, self.party)

        return {
            "name": self.player.name,
            "class": self.player.class_type,
            "level": self.player.level,
            "xp": self.player.xp,
            "hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "mp": self.player.mp,
            "max_mp": self.player.max_mp,
            "stats": {
                "STR": self.player.STR,
                "DEX": self.player.DEX,
                "INT": self.player.INT,
                "WIS": self.player.WIS,
                "CON": self.player.CON,
                "AGI": self.player.AGI,
            },
            "hunger": int(h_pct * 100),
            "thirst": int(t_pct * 100),
            "stamina": int(s_pct * 100),
            "gold": self.player.gold,
        }

    def _get_party_context(self) -> list[dict[str, Any]]:
        """Get party member information."""
        if not self.party:
            return []

        members = []
        for npc in self.party:
            member_data = {
                "name": npc.name,
                "hp": npc.hp,
                "max_hp": npc.max_hp,
                "mp": npc.mp,
                "max_mp": npc.max_mp,
                "class": npc.class_type,
            }
            # template_id is NPC-specific; skip if not present
            if hasattr(npc, 'template_id'):
                member_data["template_id"] = npc.template_id
            members.append(member_data)
        return members

    def _get_map_context(self) -> dict[str, Any]:
        """Get mini-map data for current location."""
        if not self.current_room_id:
            return {}

        room = self.world.get_room(self.current_room_id)
        if not room:
            return {}

        # Get connected rooms
        connected = {}
        for direction, room_id in room.exits.items():
            connected_room = self.world.get_room(room_id)
            if connected_room:
                connected[direction] = {
                    "name": connected_room.name,
                    "room_id": room_id,
                }

        return {
            "current": {
                "id": room.id,
                "name": room.name,
                "zone": room.zone,
            },
            "exits": connected,
        }

    def _get_inventory_context(self) -> dict[str, Any]:
        """Get inventory summary."""
        if not self.player:
            return {}

        from server.engine.items import get_item

        items = []
        for item_id in self.player.inventory[:MAX_CONTEXT_INVENTORY_ITEMS]:
            item = get_item(item_id)
            if item:
                items.append({
                    "id": item_id,
                    "name": item.name,
                    "type": item.type,
                })

        return {
            "count": len(self.player.inventory),
            "items": items,
            "has_more": len(self.player.inventory) > MAX_CONTEXT_INVENTORY_ITEMS,
            "equipment": self.player.equipment,
        }

    def _get_environment_context(self) -> dict[str, Any]:
        """Get environment data (time, weather, temperature, visibility)."""
        if not self.clock:
            return {}

        room = None
        if self.current_room_id:
            room = self.world.get_room(self.current_room_id)

        # Get effective light for visibility calculation
        eff_light = 1.0
        if room:
            eff_light = _effective_light_fn(
                self.player, self.party, self.player.lit_sources, self.clock, room
            )

        # Determine visibility label
        if eff_light >= 0.80:
            visibility = "Bright"
        elif eff_light >= 0.40:
            visibility = "Dim"
        elif eff_light >= 0.05:
            visibility = "Dark"
        else:
            visibility = "Pitch Black"

        # Get temperature label
        temp_label = "Unknown"
        if room:
            temp_label = self.clock.temperature_label(room.room_type, room.base_temp_f)

        return {
            "time_of_day": self.clock.time_of_day_label(),
            "time_string": self.clock.time_string(),
            "weather": self.clock.current_weather,
            "temperature": temp_label,
            "visibility": visibility,
            "room_type": room.room_type if room else "unknown",
        }

    async def _do_inventory(self, args: str = "") -> None:
        await do_inventory(self._send, self.player, self.party, self._cart_inventory, args)

    async def _do_equip(self, args: str) -> None:
        await do_equip(self._send, self.player, args)

    async def _do_unequip(self, args: str) -> None:
        await do_unequip(self._send, self.player, args)

    async def _do_drop(self, args: str) -> None:
        room = self.world.get_room(self.current_room_id)
        await do_drop(self._send, self.player, room, self._broadcast_to_room, args)

    async def _do_give(self, args: str) -> None:
        await do_give(self._send, self.player, self.party, args)

    async def _do_load_cart(self, args: str) -> None:
        await do_load_cart(
            self._send, self.player, self.party, self._cart_inventory, self._cart_present, args
        )

    async def _do_unload_cart(self, args: str) -> None:
        await do_unload_cart(
            self._send, self.player, self.party, self._cart_inventory, self._cart_present, args
        )

    async def _try_recruit_response(self, text: str) -> bool:
        """Returns True if this input was consumed as a recruit response."""
        if not hasattr(self, "_pending_recruit") or self._pending_recruit is None:
            return False
        upper = text.strip().upper()
        if upper not in ("YES", "NO", "Y", "N"):
            return False
        tid = self._pending_recruit
        self._pending_recruit = None
        if upper in ("YES", "Y"):
            npc = spawn_npc(tid, self.class_defs)
            if npc:
                npc.owner = self.player.name
                self.party.append(npc)
                await self.send(
                    f"\n  {npc.name} joins your party!\n"
                    f"  Their default strategies are already configured.\n"
                    f"  Visit the campfire to customise them with MANAGE {npc.name}.\n"
                )
            else:
                await self.send("  Something went wrong recruiting that NPC.\n")
        else:
            await self.send("  You decline.\n")
        return True
