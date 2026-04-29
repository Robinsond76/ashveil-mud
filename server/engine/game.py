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

from server.config import MODIFIER_BONUS_PER_LEVEL
from server.engine.domain.character import Character, MODIFIER_CATALOGUE
from server.engine.combat.session import CombatSession
from server.engine.domain.npc import NPC
from server.engine.persistence import init_db, save_player
from server.engine.domain.skills import can_learn, get_skill, get_skill_tree
from server.engine.strategy import list_strategies
from server.engine.display.help_data import send_help
from server.engine.systems.campfire import do_formation, do_manage
from server.engine.systems.survival import (
    party_survival_aggregate,
    survival_tick_handler,
)
from server.engine.world.map import WorldMap
from server.engine.world.clock import WorldClock
from server.engine.states import State, HANDLER_REGISTRY
from server.engine.systems.utility_skills import handle_use_skill

from server.engine.display.formatting import box as _box
from server.engine.display.context_panel import send_context_update


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
        await send_context_update(self)

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
        await send_context_update(self)

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
                    await survival_tick_handler(self, temp_label, self._sitting)
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
    # Utility skill handler (delegates to systems/utility_skills)
    # ─────────────────────────────────────────────────────────────────────────

    _handle_use_skill = handle_use_skill

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


