"""
GameSession — per-connection state machine.

States:
  CONNECT     → prompt for name
  CREATION    → character creation wizard
  NAVIGATION  → explore rooms, talk to NPCs
  CAMPFIRE    → rest, manage party, strategies, learn skills
  STRATEGY    → strategy editor sub-mode
  COMBAT      → hands-off while CombatSession runs

All output flows through `self._send(text)`.
Input arrives via `handle_input(raw_text)`.
"""
from __future__ import annotations

import json
import math
import os
import random
from enum import Enum
from typing import Any

from server.config import (
    DEBUG_NO_DEATH_PENALTY,
    DEBUG_RESPAWN_ROOM_ID,
    DEATH_GOLD_LOSS_PCT,
    DEATH_XP_LOSS_PCT,
    MAX_STAT,
    MIN_STAT,
    MODIFIER_BONUS_PER_LEVEL,
    STAT_POINT_BUY_BUDGET,
    WEIGHT_DIVISOR,
)
from server.engine.character import Character, MODIFIER_CATALOGUE, XP_TABLE
from server.engine.combat import CombatSession, CombatState
from server.engine.items import (
    EQUIPMENT_SLOTS, all_items, get_item,
    equipped_weapon, total_equipped_weight,
)
from server.engine.npc import NPC, spawn_npc
from server.engine.persistence import init_db, load_player, save_player
from server.engine.skills import (
    can_learn, get_skill, render_skill_tree,
)
from server.engine.strategy import (
    add_strategy, clear_strategies, list_strategies, remove_strategy,
)
from server.engine.world import WorldMap
from server.engine.world_clock import WorldClock, light_label


class State(Enum):
    CONNECT = "connect"
    CREATION = "creation"
    NAVIGATION = "navigation"
    CAMPFIRE = "campfire"
    STRATEGY = "strategy"
    COMBAT = "combat"


# ── Helper ────────────────────────────────────────────────────────────────────

def _box(title: str, lines: list[str]) -> str:
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class GameSession:
    def __init__(
        self,
        send_fn,   # async callable: send_fn(text: str) → Awaitable
        world: WorldMap,
        class_defs: dict,
        clock: WorldClock | None = None,
    ) -> None:
        self._send_raw = send_fn
        self.world = world
        self.class_defs = class_defs
        self.clock: WorldClock | None = clock

        self.state = State.CONNECT
        self.player: Character | None = None
        self.party: list[NPC] = []            # up to 4 NPC companions
        self.current_room_id: str = "town_square"
        self.last_campfire_room_id: str = "test_campfire"

        # Creation wizard state
        self._creation_step: str = "name"
        self._pending_name: str = ""
        self._pending_class: str = ""
        self._pending_stats: dict[str, int] = {}
        self._stat_points_remaining: int = STAT_POINT_BUY_BUDGET

        # Strategy editor context
        self._strategy_target: Character | NPC | None = None
        self._strategy_context: str = ""  # "creation" | "campfire"

        # Active combat session
        self._combat: CombatSession | None = None

        # Which arena group is being fought
        self._arena_group: str | None = None

        # Session quit flag (checked in main.py after handle_input)
        self._quit: bool = False

        # Light sources: item_id → expiry in absolute game-minutes
        # (only sources that have been explicitly lit by the player)
        self._lit_sources: dict[str, int] = {}

        # Sitting flag for passive stamina recovery
        self._sitting: bool = False

        # Weather/clock callback ref (stored for unsubscribe)
        self._weather_cb = None

    async def _send(self, text: str) -> None:
        await self._send_raw(text)

    # ── World clock helpers ───────────────────────────────────────────────────

    def _subscribe_clock(self) -> None:
        """Subscribe to weather broadcasts once a player is in the world."""
        if self.clock and not self._weather_cb:
            async def _on_weather(msg: str) -> None:
                # Only push to players who are actively in the world (not in menus)
                if self.state in (State.NAVIGATION, State.CAMPFIRE, State.COMBAT):
                    room = self.world.get_room(self.current_room_id)
                    # Underground rooms are shielded from outdoor weather messages
                    if room and room.room_type != "underground":
                        await self._send(f"\n  {msg}\n")
                    # Drain survival stats each game-minute tick
                    if self.player:
                        temp_label = "Comfortable"
                        if self.clock and room:
                            temp_label = self.clock.temperature_label(
                                room.room_type, room.base_temp_f
                            )
                        self._drain_survival_tick(temp_label)
                        # Passive sitting recovery
                        if self.state != State.COMBAT:
                            self._sitting_stamina_tick()
            self._weather_cb = _on_weather
            self.clock.subscribe(self._weather_cb)

    def _unsubscribe_clock(self) -> None:
        if self.clock and self._weather_cb:
            self.clock.unsubscribe(self._weather_cb)
            self._weather_cb = None

    # ── Survival helpers ──────────────────────────────────────────────────────

    def _party_survival_aggregate(self) -> tuple[float, float, float]:
        """Return (hunger_pct, thirst_pct, stamina_pct) averaged across the whole party."""
        members = [self.player] + list(self.party)
        total_hunger  = sum(m.hunger  for m in members)
        total_thirst  = sum(m.thirst  for m in members)
        total_stamina = sum(m.stamina for m in members)
        total_max_h   = sum(m.max_hunger  for m in members)
        total_max_t   = sum(m.max_thirst  for m in members)
        total_max_s   = sum(m.max_stamina for m in members)
        return (
            total_hunger  / total_max_h if total_max_h else 1.0,
            total_thirst  / total_max_t if total_max_t else 1.0,
            total_stamina / total_max_s if total_max_s else 1.0,
        )

    def _apply_survival_penalties(self) -> tuple[float, bool]:
        """Return (combat_stat_multiplier, movement_blocked) based on party aggregate."""
        hunger_pct, thirst_pct, stamina_pct = self._party_survival_aggregate()
        multiplier = 1.0
        blocked = False

        # Stamina penalties
        if stamina_pct <= 0.10:
            blocked = True
        elif stamina_pct <= 0.30:
            multiplier *= 0.85

        # Hunger + thirst combined (average of the two)
        ht_avg = (hunger_pct + thirst_pct) / 2.0
        if ht_avg < 0.20:
            multiplier *= 0.75
        elif ht_avg < 0.40:
            multiplier *= 0.90

        return multiplier, blocked

    def _drain_survival_tick(self, temp_label: str) -> None:
        """Decrement hunger and thirst for every party member by one game-minute's drain."""
        members = [self.player] + list(self.party)
        for m in members:
            hunger_drain = m.hunger_drain_rate()
            thirst_drain = m.thirst_drain_rate(temp_label)
            m.hunger = max(0.0, m.hunger - hunger_drain)
            m.thirst = max(0.0, m.thirst - thirst_drain)

    def _sitting_stamina_tick(self) -> None:
        """Restore +1 stamina per game-minute while sitting (out of combat)."""
        if not self._sitting:
            return
        members = [self.player] + list(self.party)
        for m in members:
            m.stamina = min(m.max_stamina, m.stamina + 1.0)

    def _carried_light(self) -> float:
        """
        Return the highest light level from all lit sources currently held
        by any party member.  Expired sources are silently removed.
        """
        if not self._lit_sources or not self.clock:
            return 0.0
        now = self.clock.total_minutes
        # Expire burned-out sources
        expired = [k for k, exp in self._lit_sources.items() if exp <= now]
        for k in expired:
            del self._lit_sources[k]
            # Build a friendly name for the notification
            item = get_item(k)
            iname = item.name if item else k
            # Queue a non-blocking notification; fire-and-forget
            import asyncio
            asyncio.get_event_loop().create_task(
                self._send(f"\n  Your {iname} has burned out.\n")
            )
        if not self._lit_sources:
            return 0.0
        # Collect all item_ids in party inventory
        all_inv: list[str] = list(self.player.inventory) if self.player else []
        for npc in self.party:
            all_inv.extend(npc.inventory)
        best = 0.0
        for item_id in list(self._lit_sources):
            if item_id in all_inv:
                item = get_item(item_id)
                if item:
                    best = max(best, item.effect_params.get("light_level", 0.0))
        return best

    def _effective_light(self) -> float:
        """Effective light level [0,1] in the current room."""
        if not self.clock:
            return 1.0
        room = self.world.get_room(self.current_room_id)
        if not room:
            return 1.0
        return self.clock.effective_light(room.room_type, self._carried_light())

    # ═══════════════════════════════════════════════════════════════════
    # Entry point
    # ═══════════════════════════════════════════════════════════════════

    async def start(self) -> None:
        init_db()
        await self._send(
            "\n" + "═" * 60 + "\n"
            "  Welcome to ASHVEIL MUD\n"
            "  A text-based fantasy world\n" +
            "═" * 60 + "\n"
            "\nEnter your character name (new or existing):\n> "
        )

    # ═══════════════════════════════════════════════════════════════════
    # Main input dispatcher
    # ═══════════════════════════════════════════════════════════════════

    async def handle_input(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return

        if self.state == State.CONNECT:
            await self._handle_connect(text)
        elif self.state == State.CREATION:
            await self._handle_creation(text)
        elif self.state == State.NAVIGATION:
            await self._handle_navigation(text)
        elif self.state == State.CAMPFIRE:
            await self._handle_campfire(text)
        elif self.state == State.STRATEGY:
            await self._handle_strategy(text)
        elif self.state == State.COMBAT:
            await self._send("  Combat is in progress. Your strategies are running...")

    # ═══════════════════════════════════════════════════════════════════
    # CONNECT
    # ═══════════════════════════════════════════════════════════════════

    async def _handle_connect(self, name: str) -> None:
        if not name.isalpha() or len(name) < 2 or len(name) > 20:
            await self._send("  Name must be 2–20 letters only. Try again:\n> ")
            return
        # Try to load existing save
        save = load_player(name)
        if save:
            await self._load_save(save)
            self._subscribe_clock()
            await self._send(f"\n  Welcome back, {self.player.name}!\n")
            await self._do_look()
        else:
            self._pending_name = name
            self.state = State.CREATION
            self._creation_step = "class"
            await self._send_class_prompt()

    # ═══════════════════════════════════════════════════════════════════
    # CHARACTER CREATION
    # ═══════════════════════════════════════════════════════════════════

    async def _send_class_prompt(self) -> None:
        lines = [f"  Creating character: {self._pending_name}", ""]
        for key, cd in self.class_defs.items():
            lines.append(f"  {key.upper():<10} — {cd['description']}")
        lines.append("")
        lines.append("  Type WARRIOR, MAGE, THIEF, or CLERIC:")
        await self._send(_box("CHARACTER CREATION — Choose Class", lines[1:]))

    async def _handle_creation(self, text: str) -> None:
        step = self._creation_step

        if step == "class":
            upper = text.strip().upper()
            if upper in ("HELP", "?"):
                await self._send(
                    "  Commands:\n"
                    "    WARRIOR / MAGE / THIEF / CLERIC  — choose your class\n"
                    "    QUIT  — exit the game\n"
                    "> "
                )
                return
            cls = text.strip().lower()
            if cls not in self.class_defs:
                await self._send(f"  Unknown class '{text}'. Choose: warrior, mage, thief, cleric\n> ")
                return
            self._pending_class = cls
            self._creation_step = "stats"
            await self._send_stat_prompt()

        elif step == "stats":
            await self._handle_stat_input(text)

        elif step == "strategy":
            await self._handle_strategy(text)

    async def _send_stat_prompt(self) -> None:
        cd = self.class_defs[self._pending_class]
        suggested = cd["suggested_stats"]
        if not self._pending_stats:
            self._pending_stats = {s: MIN_STAT for s in ["STR", "DEX", "INT", "WIS", "CON", "AGI"]}
            self._stat_points_remaining = STAT_POINT_BUY_BUDGET
        spent = sum(self._pending_stats.values()) - MIN_STAT * 6
        remaining = STAT_POINT_BUY_BUDGET - spent
        lines = [
            f"  Class: {cd['display_name']}",
            f"  Points remaining: {remaining}  (budget: {STAT_POINT_BUY_BUDGET})",
            f"  Stats range: {MIN_STAT}–{MAX_STAT}",
            "",
            "  Current / Suggested:",
        ]
        for stat, val in suggested.items():
            cur = self._pending_stats.get(stat, MIN_STAT)
            lines.append(f"    {stat}: {cur:<4}  (suggested {val})")
        lines += [
            "",
            "  Commands: SET STR 15 | SUGGEST | STATS | DONE | HELP",
        ]
        await self._send(_box("CHARACTER CREATION — Assign Stats", lines))

    async def _handle_stat_input(self, text: str) -> None:
        upper = text.strip().upper()
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]

        if upper in ("HELP", "?"):
            await self._send(
                f"  Commands during stat assignment:\n"
                f"    SET <stat> <value>  — assign a stat (e.g. SET STR 15)\n"
                f"    STATS               — show current assignments and remaining points\n"
                f"    SUGGEST             — apply the recommended spread for your class\n"
                f"    DONE                — confirm stats and continue\n"
                f"    QUIT                — exit the game\n"
                f"  Stats: STR DEX INT WIS CON AGI  (range: {MIN_STAT}\u2013{MAX_STAT})\n"
                f"  Point budget: {STAT_POINT_BUY_BUDGET}\n"
            )
            return

        if upper == "STATS":
            spent = sum(self._pending_stats.values()) - MIN_STAT * 6
            remain = STAT_POINT_BUY_BUDGET - spent
            lines = [f"  Points remaining: {remain}  (budget: {STAT_POINT_BUY_BUDGET})"]
            for s in stats_list:
                lines.append(f"    {s}: {self._pending_stats.get(s, MIN_STAT)}")
            await self._send("\n".join(lines) + "\n")
            return

        if upper == "SUGGEST":
            cd = self.class_defs[self._pending_class]
            self._pending_stats = dict(cd["suggested_stats"])
            spent = sum(self._pending_stats.values()) - MIN_STAT * 6
            self._stat_points_remaining = STAT_POINT_BUY_BUDGET - spent
            lines = ["  Suggested stats applied:"]
            for s in stats_list:
                lines.append(f"    {s}: {self._pending_stats.get(s, MIN_STAT)}")
            lines.append(f"  Points used: {spent}  |  Remaining: {self._stat_points_remaining}")
            lines.append("  Type DONE to confirm, or SET <stat> <value> to adjust.")
            await self._send("\n".join(lines) + "\n")
            return

        if upper == "DONE":
            total = sum(self._pending_stats.values()) - (MIN_STAT * 6)
            if total > STAT_POINT_BUY_BUDGET:
                await self._send(
                    f"  You've spent {total} points but only have {STAT_POINT_BUY_BUDGET}. Adjust stats.\n> "
                )
                return
            self._creation_step = "strategy"
            await self._finalize_character_stats()
            return

        # SET <stat> <value>
        parts = upper.split()
        if len(parts) == 3 and parts[0] == "SET" and parts[1] in stats_list:
            try:
                val = int(parts[2])
            except ValueError:
                await self._send("  Usage: SET STR 15\n> ")
                return
            if val < MIN_STAT or val > MAX_STAT:
                await self._send(f"  Stat must be between {MIN_STAT} and {MAX_STAT}.\n> ")
                return
            old = self._pending_stats.get(parts[1], MIN_STAT)
            # Compute new total spent — correct formula (no off-by-MIN_STAT)
            new_spent = sum(self._pending_stats.values()) - (MIN_STAT * 6) - old + val
            if new_spent > STAT_POINT_BUY_BUDGET:
                current_remain = STAT_POINT_BUY_BUDGET - (sum(self._pending_stats.values()) - MIN_STAT * 6)
                await self._send(
                    f"  Not enough points. You have {current_remain} remaining but that would cost {val - old} more.\n> "
                )
                return
            self._pending_stats[parts[1]] = val
            remain = STAT_POINT_BUY_BUDGET - new_spent
            await self._send(f"  {parts[1]} set to {val}. Points remaining: {remain}\n> ")
        else:
            await self._send("  Usage: SET STR 15 | SUGGEST | STATS | DONE | HELP\n> ")

    async def _finalize_character_stats(self) -> None:
        cd = self.class_defs[self._pending_class]
        s = self._pending_stats
        max_hp = cd["base_hp"] + max(0, (s.get("CON", 10) - 10))
        max_mp = cd["base_mp"] + max(0, (s.get("WIS", 10) - 10) * 2)

        self.player = Character(
            name=self._pending_name,
            class_type=self._pending_class,
            STR=s["STR"], DEX=s["DEX"], INT=s["INT"],
            WIS=s["WIS"], CON=s["CON"], AGI=s["AGI"],
            max_hp=max_hp, hp=max_hp,
            max_mp=max_mp, mp=max_mp,
        )
        # Apply suggested starting modifiers at level 0
        # Give starting equipment based on class
        starter_equipment = {
            "warrior": {"weapon": "rusty_sword", "body": "leather_armor"},
            "mage":    {"weapon": "oak_staff",   "body": "cloth_robe"},
            "thief":   {"weapon": "iron_dagger", "body": "leather_armor"},
            "cleric":  {"weapon": "wooden_mace", "body": "leather_armor"},
        }
        for slot, item_id in starter_equipment.get(self._pending_class, {}).items():
            self.player.equipment[slot] = item_id
        self.player.inventory = ["health_potion", "health_potion", "campfire_kit"]

        # Default starting strategies from class definition
        for i, strat_raw in enumerate(cd.get("default_strategies", []), start=1):
            self.player.strategies.append({
                "priority": i,
                "condition": strat_raw["condition"],
                "action": strat_raw["action"],
                "target": strat_raw["target"],
            })

        self.current_room_id = "town_square"
        self.last_campfire_room_id = "test_campfire"

        await self._send(
            _box(f"CHARACTER CREATED: {self.player.name}", [
                self.player.stats_summary(),
                "",
                "  Your starting strategies:",
                list_strategies(self.player),
                "",
                "  You may now customize your strategies before entering the world.",
                "  Commands: STRATEGY LIST, STRATEGY ADD <n> IF <cond> DO <act> ON <tgt>",
                "             STRATEGY REMOVE <n>, STRATEGY CLEAR",
                "",
                "  When ready, type:  START",
            ])
        )
        # Enter strategy editor for the player
        self._strategy_target = self.player
        self._strategy_context = "creation"
        self.state = State.STRATEGY

    # ═══════════════════════════════════════════════════════════════════
    # STRATEGY EDITOR (shared by creation + campfire)
    # ═══════════════════════════════════════════════════════════════════

    async def _handle_strategy(self, text: str) -> None:
        upper = text.strip().upper()
        char = self._strategy_target

        # Exit strategy editor
        if upper in ("DONE", "BACK", "EXIT", "START"):
            if self._strategy_context == "creation":
                self.state = State.NAVIGATION
                self._subscribe_clock()
                await self._send("\n  Entering the world of Ashveil...\n")
                await self._do_look()
            else:
                self.state = State.CAMPFIRE
                await self._send(
                    f"  Strategy for {char.name} saved.\n"
                    "  Back at campfire. Type HELP for available commands.\n"
                )
            return

        if upper == "STRATEGY LIST" or upper == "LIST":
            await self._send(_box(f"Strategies: {char.name}", [list_strategies(char)]))
            return

        if upper == "SKILLS":
            if not char.unlocked_skills:
                await self._send(f"  {char.name} has no skills unlocked yet.\n")
            else:
                lines = [f"  Unlocked skills for {char.name} ({char.class_type.capitalize()}):"]
                for skill_id in char.unlocked_skills:
                    skill = get_skill(skill_id)
                    if skill:
                        lines.append(
                            f"    {skill_id:<20} — {skill.name}  (MP:{skill.mp_cost})  {skill.description}"
                        )
                    else:
                        lines.append(f"    {skill_id}")
                lines.append("")
                lines.append("  Use the skill ID in a strategy:  DO USE_SKILL <id>")
                await self._send("\n".join(lines) + "\n")
            return

        if upper.startswith("STRATEGY ADD"):
            # STRATEGY ADD <n> IF <cond> DO <action> ON <target>
            await self._parse_strategy_add(char, text)
            return

        if upper.startswith("STRATEGY REMOVE"):
            parts = upper.split()
            if len(parts) >= 3:
                try:
                    n = int(parts[2])
                    msg = remove_strategy(char, n)
                    await self._send(f"  {msg}\n")
                except ValueError:
                    await self._send("  Usage: STRATEGY REMOVE <number>\n")
            return

        if upper == "STRATEGY CLEAR":
            msg = clear_strategies(char)
            await self._send(f"  {msg}\n")
            return

        await self._send(
            "  Strategy editor commands:\n"
            "    STRATEGY LIST                          — show current rules\n"
            "    SKILLS                                 — list this character's unlocked skills\n"
            "    STRATEGY ADD <n> IF <cond> DO <act> ON <tgt>\n"
            "    STRATEGY REMOVE <n>\n"
            "    STRATEGY CLEAR\n"
            "    DONE  (save and exit editor)\n"
            "\n"
            "  Conditions: ALWAYS | HP_SELF < X% | HP_ALLY < X% | MP_SELF < X%\n"
            "              ENEMY_COUNT > N | HAS_STATUS <s> | ENEMY_HAS_STATUS <s>\n"
            "  Actions:    ATTACK | DEFEND | FLEE | USE_SKILL <id> | USE_ITEM <id>\n"
            "  Targets:    NEAREST_ENEMY | WEAKEST_ENEMY | STRONGEST_ENEMY\n"
            "              LOWEST_HP_ALLY | LOWEST_HP_ENEMY | SELF | RANDOM_ENEMY\n"
        )

    async def _parse_strategy_add(self, char: Character | NPC, text: str) -> None:
        # Expected: STRATEGY ADD <n> IF <condition> DO <action> ON <target>
        try:
            upper = text.strip().upper()
            after_add = upper[len("STRATEGY ADD"):].strip()
            # Split on IF, DO, ON
            if_idx = after_add.index(" IF ")
            do_idx = after_add.index(" DO ")
            on_idx = after_add.index(" ON ")
            priority_str = after_add[:if_idx].strip()
            condition = after_add[if_idx + 4:do_idx].strip()
            action = after_add[do_idx + 4:on_idx].strip()
            target = after_add[on_idx + 4:].strip()
            priority = int(priority_str)
        except (ValueError, AttributeError):
            await self._send(
                "  Usage: STRATEGY ADD <number> IF <condition> DO <action> ON <target>\n"
                "  Example: STRATEGY ADD 1 IF HP_SELF < 30% DO DEFEND ON SELF\n"
            )
            return

        msg = add_strategy(char, priority, condition, action, target)
        await self._send(f"  {msg}\n")
        await self._send(list_strategies(char) + "\n")

    # ═══════════════════════════════════════════════════════════════════
    # NAVIGATION
    # ═══════════════════════════════════════════════════════════════════

    DIR_ALIASES = {
        "N": "north", "S": "south", "E": "east", "W": "west",
        "U": "up", "D": "down",
        "NORTH": "north", "SOUTH": "south", "EAST": "east",
        "WEST": "west", "UP": "up", "DOWN": "down",
    }

    async def _handle_navigation(self, text: str) -> None:
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # Movement
        if cmd in self.DIR_ALIASES:
            await self._do_move(self.DIR_ALIASES[cmd])
            return
        if cmd == "GO":
            await self._do_move(args.lower())
            return

        # Look / examine
        if cmd == "LOOK":
            await self._do_look()
            return
        if cmd == "EXAMINE":
            await self._do_examine(args)
            return

        # Inventory management
        if cmd == "INVENTORY" or cmd == "INV" or cmd == "I":
            await self._do_inventory()
            return
        if cmd == "EQUIP":
            await self._do_equip(args)
            return
        if cmd == "UNEQUIP":
            await self._do_unequip(args)
            return
        if cmd == "DROP":
            await self._do_drop(args)
            return
        if cmd in ("PICK", "TAKE", "GET"):
            item_arg = args.lstrip("UP").strip() if args.upper().startswith("UP") else args
            await self._do_pick_up(item_arg.strip())
            return

        # Character info
        if cmd == "STATS" or cmd == "STAT":
            await self._send(self.player.stats_summary() + "\n")
            return
        if cmd == "GOLD":
            await self._send(f"  You have {self.player.gold} gold.\n")
            return
        if cmd == "SKILLS":
            await self._send(
                render_skill_tree(
                    self.player.class_type,
                    self.player.unlocked_skills,
                    self.player.skill_points,
                ) + "\n"
            )
            return
        if cmd == "LEARN":
            await self._do_learn(args.lower())
            return
        if cmd == "MODIFIERS" or cmd == "MODS":
            await self._do_show_modifiers()
            return
        if cmd == "UPGRADE":
            await self._do_upgrade(args.lower())
            return

        # Party
        if cmd == "PARTY":
            await self._do_show_party()
            return
        if cmd == "TALK":
            await self._do_talk(args)
            return
        if cmd == "DISMISS":
            await self._do_dismiss(args)
            return

        # Campfire
        if cmd == "CAMPFIRE" or cmd == "REST":
            await self._enter_campfire()
            return

        # Survival commands
        if cmd == "STATUS":
            await self._do_survival_status()
            return
        if cmd == "SIT":
            self._sitting = True
            await self._send("  You sit down to rest.\n")
            return
        if cmd == "STAND":
            self._sitting = False
            await self._send("  You stand up.\n")
            return
        if cmd == "EAT":
            await self._do_eat(args)
            return
        if cmd == "DRINK":
            await self._do_drink(args)
            return

        # Combat (arena)
        if cmd == "ATTACK":
            await self._do_attack(args)
            return

        # Save
        if cmd == "SAVE":
            self._save()
            await self._send("  Game saved.\n")
            return

        # ── Environment commands ──────────────────────────────────────────────
        if cmd == "TIME":
            await self._do_time()
            return
        if cmd == "WEATHER":
            await self._do_weather()
            return
        if cmd in ("LIGHT", "LIGHTING"):
            await self._do_light()
            return
        if cmd in ("ENVDETAILS", "ENV"):
            await self._do_envdetails()
            return
        if cmd == "LIT":
            await self._do_light_source(args, extinguish=False)
            return
        if cmd in ("EXTINGUISH", "DOUSE"):
            await self._do_light_source(args, extinguish=True)
            return

        if cmd == "HELP":
            await self._send_help(args)
            return

        await self._send(f"  Unknown command '{text}'. Type HELP for a list.\n")

    async def _do_move(self, direction: str) -> None:
        room = self.world.get_room(self.current_room_id)
        if room is None:
            await self._send("  You are in the void. Something went wrong.\n")
            return
        dest_id = room.exits.get(direction)
        if not dest_id:
            await self._send(f"  You can't go {direction} from here.\n")
            return
        # Block movement when stamina is depleted
        if self.player and self.player.stamina <= 0.0:
            await self._send(
                "  You are too exhausted to move. Rest to recover your stamina.\n"
            )
            return
        # Drain 2 stamina from all party members per move
        if self.player:
            members = [self.player] + list(self.party)
            for m in members:
                m.stamina = max(0.0, m.stamina - 2.0)
        self.current_room_id = dest_id
        await self._do_look()

    async def _do_look(self) -> None:
        room = self.world.get_room(self.current_room_id)
        if room is None:
            await self._send("  Error: current room not found.\n")
            return

        item_names = {i: get_item(i).name for i in room.item_ids if get_item(i)}

        # Recruitable NPC flavor lines
        npc_flavors: list[str] = []
        if room.recruitable_npc_ids:
            from server.engine.npc import get_npc_template
            for tid in room.recruitable_npc_ids:
                tpl = get_npc_template(tid)
                if tpl:
                    # Check not already in party
                    in_party = any(m.template_id == tid for m in self.party)
                    if not in_party:
                        npc_flavors.append(tpl.get("room_flavor", tpl["name"]))

        # Encounter summaries
        encounter_lines: list[str] = []
        active_groups = self.world.active_encounter_groups(self.current_room_id)
        for eg in active_groups:
            label = eg.label if eg.label else eg.group
            if room.id == "test_arena":
                encounter_lines.append(
                    f"[{eg.group}] {label} — {len(eg.members)} opponent(s)  "
                    f"(ATTACK {eg.group} to engage)"
                )
            else:
                encounter_lines.append(
                    f"Hostile group present: {', '.join(eg.members)}"
                )

        # Build environment footer from world clock
        footer = ""
        if self.clock:
            footer = self.clock.env_footer(
                room.room_type, room.base_temp_f, self._carried_light()
            )

        await self._send(room.render(item_names, npc_flavors, encounter_lines, env_footer=footer))

        # Stamina exhaustion warning
        if self.player and self.player.stamina <= 0.0:
            await self._send(
                "  !! The party is completely exhausted. Rest to recover stamina. !!\n"
            )

    async def _do_examine(self, target: str) -> None:
        tl = target.lower().strip()
        room = self.world.get_room(self.current_room_id)

        # Check room items
        for item_id in room.item_ids:
            item = get_item(item_id)
            if item and tl in item.name.lower():
                await self._send(
                    _box(item.name, [item.description, item.short_desc()])
                )
                return

        # Check inventory
        for item_id in self.player.inventory:
            item = get_item(item_id)
            if item and tl in item.name.lower():
                await self._send(
                    _box(item.name, [item.description, item.short_desc()])
                )
                return

        # Check recruitable NPCs
        from server.engine.npc import get_npc_template
        for tid in room.recruitable_npc_ids:
            tpl = get_npc_template(tid)
            if tpl and tl in tpl["name"].lower():
                await self._send(
                    _box(
                        tpl["name"],
                        [tpl.get("room_flavor", ""), f"Class: {tpl['class_type'].capitalize()}, Level {tpl['level']}"],
                    )
                )
                return

        await self._send(f"  You don't see '{target}' here.\n")

    # ── Inventory ─────────────────────────────────────────────────────────────

    async def _do_inventory(self) -> None:
        lines = []
        if not self.player.inventory:
            lines.append("  (empty)")
        else:
            counts: dict[str, int] = {}
            for i in self.player.inventory:
                counts[i] = counts.get(i, 0) + 1
            for item_id, count in counts.items():
                item = get_item(item_id)
                name = item.name if item else item_id
                lines.append(f"  x{count}  {name}")

        lines.append("")
        lines.append("  EQUIPPED:")
        for slot in EQUIPMENT_SLOTS:
            eid = self.player.equipment.get(slot)
            item = get_item(eid) if eid else None
            lines.append(f"    {slot:<8}: {item.name if item else '---'}")

        lines.append(f"\n  Carry weight: {total_equipped_weight(self.player.equipment)} "
                     f"  Speed: {self.player.effective_speed}")
        await self._send(_box("INVENTORY", [""] + lines))

    async def _do_equip(self, args: str) -> None:
        item_name = args.lower().strip()
        for item_id in self.player.inventory:
            item = get_item(item_id)
            if item and item_name in item.name.lower():
                slot = item.slot if item.slot else ("weapon" if item.type == "weapon" else None)
                if not slot:
                    await self._send(f"  {item.name} can't be equipped.\n")
                    return
                # Unequip current
                current = self.player.equipment.get(slot)
                if current:
                    self.player.inventory.append(current)
                self.player.equipment[slot] = item_id
                self.player.inventory.remove(item_id)
                await self._send(
                    f"  You equip {item.name}. Speed is now {self.player.effective_speed}.\n"
                )
                return
        await self._send(f"  You don't have '{args}' in your inventory.\n")

    async def _do_unequip(self, args: str) -> None:
        slot = args.lower().strip()
        if slot not in EQUIPMENT_SLOTS:
            await self._send(f"  Unknown slot '{args}'. Slots: {', '.join(EQUIPMENT_SLOTS)}\n")
            return
        eid = self.player.equipment.get(slot)
        if not eid:
            await self._send(f"  Nothing in slot '{slot}'.\n")
            return
        self.player.inventory.append(eid)
        self.player.equipment[slot] = None
        item = get_item(eid)
        await self._send(
            f"  You unequip {item.name if item else eid}. Speed is now {self.player.effective_speed}.\n"
        )

    async def _do_drop(self, args: str) -> None:
        item_name = args.lower().strip()
        for item_id in self.player.inventory:
            item = get_item(item_id)
            if item and item_name in item.name.lower():
                self.player.inventory.remove(item_id)
                room = self.world.get_room(self.current_room_id)
                if room:
                    room.item_ids.append(item_id)
                await self._send(f"  You drop {item.name}.\n")
                return
        await self._send(f"  You don't have '{args}'.\n")

    async def _do_pick_up(self, args: str) -> None:
        item_name = args.lower().strip()
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        for item_id in room.item_ids:
            item = get_item(item_id)
            if item and item_name in item.name.lower():
                room.item_ids.remove(item_id)
                self.player.inventory.append(item_id)
                await self._send(f"  You pick up {item.name}.\n")
                return
        await self._send(f"  You don't see '{args}' here.\n")

    # ── Skills & Modifiers ────────────────────────────────────────────────────

    async def _do_learn(self, skill_id: str) -> None:
        ok, reason = can_learn(
            self.player.class_type, skill_id,
            self.player.unlocked_skills, self.player.skill_points,
        )
        if not ok:
            await self._send(f"  Cannot learn: {reason}\n")
            return
        from server.engine.skills import get_skill_tree
        tree = get_skill_tree(self.player.class_type)
        node = next(n for n in tree if n.skill_id == skill_id)
        self.player.skill_points -= node.unlock_cost
        self.player.unlocked_skills[skill_id] = 1
        skill = get_skill(skill_id)
        await self._send(f"  You learned {skill.name}!\n")

    async def _do_show_modifiers(self) -> None:
        lines = [f"  Modifier Points available: {self.player.modifier_points}", ""]
        for mod_id, meta in MODIFIER_CATALOGUE.items():
            level = self.player.modifiers.get(mod_id, 0)
            bonus_pct = round(level * MODIFIER_BONUS_PER_LEVEL * 100)
            lines.append(f"  {meta['label']:<25} Lv.{level} (+{bonus_pct}%)")
        await self._send(_box("MODIFIERS", lines))

    async def _do_upgrade(self, mod_id: str) -> None:
        mod_id = mod_id.strip().lower()
        if mod_id not in MODIFIER_CATALOGUE:
            await self._send(
                f"  Unknown modifier '{mod_id}'.\n"
                f"  Valid: {', '.join(MODIFIER_CATALOGUE.keys())}\n"
            )
            return
        if self.player.modifier_points < 1:
            await self._send("  You have no modifier points.\n")
            return
        self.player.modifier_points -= 1
        self.player.modifiers[mod_id] = self.player.modifiers.get(mod_id, 0) + 1
        meta = MODIFIER_CATALOGUE[mod_id]
        new_level = self.player.modifiers[mod_id]
        new_pct = round(new_level * MODIFIER_BONUS_PER_LEVEL * 100)
        await self._send(
            f"  {meta['label']} improved to Lv.{new_level} (+{new_pct}%).\n"
            f"  Modifier points remaining: {self.player.modifier_points}\n"
        )

    # ── Party ─────────────────────────────────────────────────────────────────

    async def _do_show_party(self) -> None:
        lines = []
        lines.append(self.player.stats_summary())
        lines.append("")
        if not self.party:
            lines.append("  (no companions)")
        for i, npc in enumerate(self.party, 1):
            lines.append(f"  [{i}] {npc.stats_summary()}")
            lines.append("")
        # Survival aggregate row
        h_pct, t_pct, s_pct = self._party_survival_aggregate()
        lines.append(
            f"  Survival  Stamina {s_pct * 100:.0f}%  "
            f"Hunger {h_pct * 100:.0f}%  "
            f"Thirst {t_pct * 100:.0f}%"
        )
        await self._send(_box("PARTY", lines))

    async def _do_survival_status(self) -> None:
        h_pct, t_pct, s_pct = self._party_survival_aggregate()
        lines = [
            f"  Stamina : {s_pct * 100:.0f}%",
            f"  Hunger  : {h_pct * 100:.0f}%",
            f"  Thirst  : {t_pct * 100:.0f}%",
        ]
        await self._send(_box("SURVIVAL STATUS", lines))

    async def _do_eat(self, args: str) -> None:
        item_name = args.lower().strip()
        if not item_name:
            await self._send("  Eat what? Usage: EAT <item>\n")
            return
        # Find item in inventory by name or id
        for item_id in list(self.player.inventory):
            item = get_item(item_id)
            if not item:
                continue
            if item_name in item.name.lower() or item_name == item_id.lower():
                if item.type not in ("food",):
                    if item.effect_type not in ("restore_hunger", "restore_hunger_thirst"):
                        await self._send(f"  You can't eat {item.name}.\n")
                        return
                self.player.inventory.remove(item_id)
                hunger_gain = item.effect_params.get("amount", item.effect_params.get("hunger", 0))
                thirst_gain = item.effect_params.get("thirst", 0)
                self.player.hunger  = min(self.player.max_hunger,  self.player.hunger  + hunger_gain)
                self.player.thirst  = min(self.player.max_thirst,  self.player.thirst  + thirst_gain)
                await self._send(f"  You eat the {item.name}. (Hunger +{hunger_gain})\n")
                return
        await self._send(f"  You don't have '{item_name}' in your inventory.\n")

    async def _do_drink(self, args: str) -> None:
        item_name = args.lower().strip()
        if not item_name:
            await self._send("  Drink what? Usage: DRINK <item>\n")
            return
        for item_id in list(self.player.inventory):
            item = get_item(item_id)
            if not item:
                continue
            if item_name in item.name.lower() or item_name == item_id.lower():
                if item.type not in ("drink",) and item.effect_type not in (
                    "restore_thirst", "restore_hunger_thirst"
                ):
                    await self._send(f"  You can't drink {item.name}.\n")
                    return
                if item.effect_type not in ("restore_thirst", "restore_hunger_thirst"):
                    await self._send(f"  {item.name} doesn't restore thirst.\n")
                    return
                self.player.inventory.remove(item_id)
                thirst_gain = item.effect_params.get("amount", item.effect_params.get("thirst", 0))
                hunger_gain = item.effect_params.get("hunger", 0)
                self.player.thirst  = min(self.player.max_thirst,  self.player.thirst  + thirst_gain)
                self.player.hunger  = min(self.player.max_hunger,  self.player.hunger  + hunger_gain)
                await self._send(f"  You drink the {item.name}. (Thirst +{thirst_gain})\n")
                return
        await self._send(f"  You don't have '{item_name}' in your inventory.\n")


        name = args.lower().strip()
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        from server.engine.npc import get_npc_template

        for tid in room.recruitable_npc_ids:
            tpl = get_npc_template(tid)
            if tpl and name in tpl["name"].lower():
                already_in_party = any(m.template_id == tid for m in self.party)
                if already_in_party:
                    await self._send(f"  {tpl['name']} is already in your party.\n")
                    return
                if len(self.party) >= 4:
                    await self._send("  Your party is full (4 companions max). Dismiss someone first.\n")
                    return
                await self._send(tpl.get("recruit_dialogue", f"{tpl['name']} nods at you.\n"))
                self._pending_recruit = tid
                self.state = State.NAVIGATION   # handled in next input
                return
        await self._send(f"  There's no one named '{args}' here to talk to.\n")

    async def _do_dismiss(self, args: str) -> None:
        name = args.lower().strip()
        for npc in self.party:
            if name in npc.name.lower():
                self.party.remove(npc)
                await self._send(f"  {npc.name} has left your party.\n")
                return
        await self._send(f"  No companion named '{args}' in your party.\n")

    # ── Pickup yes/no from TALK ───────────────────────────────────────────────

    _pending_recruit: str | None = None

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
                self.party.append(npc)
                await self._send(
                    f"\n  {npc.name} joins your party!\n"
                    f"  Their default strategies are already configured.\n"
                    f"  Visit the campfire to customise them with MANAGE {npc.name}.\n"
                )
            else:
                await self._send("  Something went wrong recruiting that NPC.\n")
        else:
            await self._send("  You decline.\n")
        return True

    # Override handle_input to intercept YES/NO after TALK
    async def handle_input(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return

        # Global QUIT — works from any state
        if text.upper() in ("QUIT", "EXIT", "BYE", "LOGOUT"):
            if self.player:
                self._save()
            self._unsubscribe_clock()
            self._quit = True
            await self._send("\n  Farewell, adventurer. Safe travels.\n")
            return

        if self.state == State.NAVIGATION:
            if await self._try_recruit_response(text):
                return
        await super().handle_input(raw) if False else None
        # (Can't use super() in non-inherited class; re-dispatch below)
        if self.state == State.CONNECT:
            await self._handle_connect(text)
        elif self.state == State.CREATION:
            await self._handle_creation(text)
        elif self.state == State.NAVIGATION:
            await self._handle_navigation(text)
        elif self.state == State.CAMPFIRE:
            await self._handle_campfire(text)
        elif self.state == State.STRATEGY:
            await self._handle_strategy(text)
        elif self.state == State.COMBAT:
            await self._send("  Combat is in progress. Your strategies are running...\n")

    # ── Combat ────────────────────────────────────────────────────────────────

    async def _do_attack(self, args: str) -> None:
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        group_id = args.strip().upper() if args else None

        active = self.world.active_encounter_groups(self.current_room_id)
        if not active:
            await self._send("  There's no one left to fight here.\n")
            return

        # Lighting check — pitch black blocks player-initiated combat
        # unless the enemy group contains darkvision creatures (they can attack you)
        if self.clock:
            eff_light = self._effective_light()
            if eff_light < 0.05:
                # Gather potential enemies to check darkvision
                from server.engine.npc import spawn_npc, get_npc_template
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
                    await self._send(
                        "  It is pitch black — you cannot fight what you cannot see.\n"
                        "  Light a torch or find another source of light.\n"
                    )
                    return

        # Arena: player picks a group by letter
        if room.id == "test_arena":
            if not group_id:
                await self._send("  Specify a group: ATTACK A, ATTACK B, ATTACK C, or ATTACK D\n")
                return
            target_group = next((g for g in active if g.group == group_id), None)
            if not target_group:
                await self._send(
                    f"  Group '{group_id}' is defeated or doesn't exist.\n"
                )
                return
            self._arena_group = group_id
            await self._start_combat(target_group)
        else:
            # Normal room: attack first available group
            target_group = active[0]
            self._arena_group = None
            await self._start_combat(target_group)

    async def _start_combat(self, encounter_group) -> None:
        from server.engine.npc import spawn_npc
        enemy_npcs: list[NPC] = []
        for tid in encounter_group.members:
            npc = spawn_npc(tid, self.class_defs)
            if npc:
                enemy_npcs.append(npc)
        if not enemy_npcs:
            await self._send("  Could not spawn enemies.\n")
            return

        player_party = [self.player] + self.party
        self._current_encounter_group = encounter_group
        self.state = State.COMBAT

        async def on_combat_end(state: CombatState, summary: list[str]) -> None:
            await self._send("\n".join(summary))
            if state == CombatState.VICTORY:
                self._current_encounter_group.mark_defeated()
                self._combat.collect_rewards(player_party, self.class_defs)
                # Stream level-up messages
                for char in player_party:
                    xp_msg = char.gain_xp(0, 0, 0)  # already awarded in collect_rewards
                await self._end_combat_victory()
            else:
                await self._end_combat_defeat()
            self._combat = None

        self._combat = CombatSession(
            player_party=player_party,
            enemy_party=enemy_npcs,
            send=self._send,
            on_end=on_combat_end,
            lighting=self._effective_light(),
            survival_multiplier=self._apply_survival_penalties()[0],
        )
        self._combat.start()

    async def _end_combat_victory(self) -> None:
        self.state = State.NAVIGATION
        await self._do_look()

    async def _end_combat_defeat(self) -> None:
        if not DEBUG_NO_DEATH_PENALTY:
            xp_loss = round(self.player.xp * DEATH_XP_LOSS_PCT)
            gold_loss = round(self.player.gold * DEATH_GOLD_LOSS_PCT)
            self.player.xp = max(0, self.player.xp - xp_loss)
            self.player.gold = max(0, self.player.gold - gold_loss)
            await self._send(
                f"  You lost {xp_loss} XP and {gold_loss} gold.\n"
            )
        # Restore HP/MP and respawn
        self.player.hp = self.player.max_hp
        self.player.mp = self.player.max_mp
        for npc in self.party:
            npc.hp = npc.max_hp
            npc.mp = npc.max_mp
        respawn = DEBUG_RESPAWN_ROOM_ID if DEBUG_NO_DEATH_PENALTY else self.last_campfire_room_id
        self.current_room_id = respawn
        self.state = State.NAVIGATION
        await self._send(f"\n  You find yourself back at the Proving Grounds, wounds healed.\n")
        await self._do_look()

    # ═══════════════════════════════════════════════════════════════════
    # CAMPFIRE
    # ═══════════════════════════════════════════════════════════════════

    async def _enter_campfire(self) -> None:
        room = self.world.get_room(self.current_room_id)
        if not room:
            return
        # Check for campfire room or campfire_kit in inventory
        has_kit = "campfire_kit" in self.player.inventory
        if not room.is_campfire and not has_kit:
            await self._send(
                "  No campfire here. Find a campfire room or use a Campfire Kit.\n"
            )
            return
        if has_kit and not room.is_campfire:
            self.player.inventory.remove("campfire_kit")
        if room.is_campfire:
            self.last_campfire_room_id = self.current_room_id
        self.state = State.CAMPFIRE
        await self._send(
            _box("CAMPFIRE", [
                "  A warm fire crackles before you.",
                "",
                "  PARTY                — View party stats",
                "  FORMATION           — View / change battle positions",
                "  MANAGE <name>        — Edit that member's strategies",
                "  REST                 — Restore HP/MP and save",
                "  SKILLS               — View skill tree",
                "  LEARN <skill>        — Spend skill points",
                "  MODIFIERS / MODS     — View modifiers",
                "  UPGRADE <modifier>   — Spend modifier points",
                "  DISMISS <name>       — Remove companion",
                "  LEAVE                — Return to exploration",
            ])
        )

    async def _handle_campfire(self, text: str) -> None:
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("LEAVE", "EXIT", "BACK"):
            self.state = State.NAVIGATION
            await self._send("  You leave the campfire.\n")
            await self._do_look()
            return

        if cmd == "REST":
            self.player.hp = self.player.max_hp
            self.player.mp = self.player.max_mp
            self.player.stamina = self.player.max_stamina
            for npc in self.party:
                npc.hp = npc.max_hp
                npc.mp = npc.max_mp
                npc.stamina = npc.max_stamina
            self._save()
            await self._send("  You rest and recover fully. Game saved.\n")
            return

        if cmd == "PARTY":
            await self._do_show_party()
            return

        if cmd == "FORMATION":
            await self._do_formation(args)
            return

        if cmd == "MANAGE":
            await self._do_manage(args)
            return

        if cmd == "DISMISS":
            await self._do_dismiss(args)
            return

        if cmd == "SKILLS":
            await self._send(
                render_skill_tree(
                    self.player.class_type,
                    self.player.unlocked_skills,
                    self.player.skill_points,
                ) + "\n"
            )
            return

        if cmd == "LEARN":
            await self._do_learn(args.lower())
            return

        if cmd in ("MODIFIERS", "MODS"):
            await self._do_show_modifiers()
            return

        if cmd == "UPGRADE":
            await self._do_upgrade(args.lower())
            return

        if cmd == "SAVE":
            self._save()
            await self._send("  Game saved.\n")
            return

        if cmd == "HELP":
            await self._enter_campfire()
            return

        await self._send(f"  Unknown campfire command '{text}'. Type HELP.\n")

    async def _do_formation(self, args: str) -> None:
        """Show or change party battle formation.
        Usage:
          FORMATION            — show current grid
          FORMATION <name> FRONT <col>   — place member in front row, column 1-3
          FORMATION <name> BACK <col>    — place member in back row, column 1-3
          FORMATION <name> AUTO          — reset to auto-assign
        """
        from server.engine.combat import FRONT_ROW, BACK_ROW, MELEE_CLASSES

        all_members: list[Character | NPC] = [self.player] + self.party

        def _render_formation() -> str:
            grid: dict[tuple[int, int], str] = {}
            unplaced: list[str] = []
            for m in all_members:
                r, c = m.grid_row, m.grid_col
                if r in (FRONT_ROW, BACK_ROW) and 0 <= c <= 2:
                    grid[(r, c)] = m.name[:12]
                else:
                    unplaced.append(m.name)
            rows = ["  Party formation (2 rows x 3 columns):", ""]
            for row_idx, row_label in ((FRONT_ROW, "FRONT"), (BACK_ROW, "BACK ")):
                cells = []
                for col in range(3):
                    entry = grid.get((row_idx, col), "------")
                    cells.append(f"{entry:<12}")
                rows.append(f"  {row_label}  [ {' | '.join(cells)} ]")
                rows.append(f"           [ col 1       | col 2       | col 3       ]")
            if unplaced:
                rows.append(f"\n  Auto-assigned at combat start: {', '.join(unplaced)}")
            rows += [
                "",
                "  Commands:",
                "    FORMATION <name> FRONT <1-3>  — place in front row",
                "    FORMATION <name> BACK  <1-3>  — place in back row",
                "    FORMATION <name> AUTO         — reset to auto-assign",
                "",
                "  Note: front row = melee range; back row = ranged/magic only.",
                "  Back row is shielded while 2+ melee guards hold the front.",
            ]
            return "\n".join(rows)

        if not args:
            await self._send(_render_formation())
            return

        # Parse: <name> FRONT|BACK|AUTO [col]
        parts = args.split()
        if len(parts) < 2:
            await self._send("  Usage: FORMATION <name> FRONT|BACK <1-3>  or  FORMATION <name> AUTO\n")
            return

        # Find member — name may be multi-word, so consume until we hit a keyword
        ROW_KEYWORDS = {"FRONT", "BACK", "AUTO"}
        row_kw_idx = None
        for i, p in enumerate(parts):
            if p.upper() in ROW_KEYWORDS:
                row_kw_idx = i
                break
        if row_kw_idx is None or row_kw_idx == 0:
            await self._send("  Usage: FORMATION <name> FRONT|BACK <1-3>\n")
            return

        name_str = " ".join(parts[:row_kw_idx]).lower()
        row_kw = parts[row_kw_idx].upper()

        target: Character | NPC | None = None
        if name_str in (self.player.name.lower(), "me", "player"):
            target = self.player
        else:
            for npc in self.party:
                if name_str in npc.name.lower():
                    target = npc
                    break

        if target is None:
            await self._send(f"  '{name_str}' not found in your party.\n")
            return

        if row_kw == "AUTO":
            target.grid_row = -1
            target.grid_col = -1
            await self._send(f"  {target.name}'s position reset to auto-assign.\n")
            await self._send(_render_formation())
            return

        # Expect a column number after FRONT/BACK
        if row_kw_idx + 1 >= len(parts):
            await self._send(f"  Specify a column (1-3): FORMATION {target.name} {row_kw} <1-3>\n")
            return
        try:
            col_1based = int(parts[row_kw_idx + 1])
        except ValueError:
            await self._send("  Column must be a number 1-3.\n")
            return
        if col_1based not in (1, 2, 3):
            await self._send("  Column must be 1, 2, or 3.\n")
            return

        new_row = FRONT_ROW if row_kw == "FRONT" else BACK_ROW
        new_col = col_1based - 1  # convert to 0-indexed

        # Check if another member already occupies that cell
        for m in all_members:
            if m is target:
                continue
            if m.grid_row == new_row and m.grid_col == new_col:
                await self._send(
                    f"  {m.name} already occupies {row_kw} column {col_1based}. "
                    f"Move them first or choose another cell.\n"
                )
                return

        target.grid_row = new_row
        target.grid_col = new_col
        row_label = "FRONT" if new_row == FRONT_ROW else "BACK"
        await self._send(
            f"  {target.name} placed in {row_label} row, column {col_1based}.\n"
        )
        await self._send(_render_formation())

    async def _do_manage(self, name: str) -> None:
        nl = name.lower().strip()
        target: Character | NPC | None = None

        if nl == self.player.name.lower() or nl == "player" or nl == "me":
            target = self.player
        else:
            for npc in self.party:
                if nl in npc.name.lower():
                    target = npc
                    break

        if target is None:
            await self._send(
                f"  '{name}' not found. Try your own name or a companion's name.\n"
            )
            return

        self._strategy_target = target
        self._strategy_context = "campfire"
        self.state = State.STRATEGY

        # Build unlocked skills summary for the opening banner
        if target.unlocked_skills:
            skill_lines = ["  Unlocked skills:"]
            for sid in target.unlocked_skills:
                sk = get_skill(sid)
                if sk:
                    skill_lines.append(f"    {sid:<20} — {sk.name}  (MP:{sk.mp_cost})")
        else:
            skill_lines = ["  No skills unlocked yet."]

        await self._send(
            _box(
                f"Strategy Editor: {target.name}  [{target.class_type.capitalize()}]",
                [
                    *skill_lines,
                    "",
                    list_strategies(target),
                    "",
                    "  Commands: SKILLS | STRATEGY LIST | STRATEGY ADD | STRATEGY REMOVE | DONE",
                ],
            )
        )

    # ═══════════════════════════════════════════════════════════════════
    # SAVE / LOAD
    # ═══════════════════════════════════════════════════════════════════

    def _save(self) -> None:
        if not self.player:
            return
        data = {
            "character": self.player.to_dict(),
            "party": [npc.to_dict() for npc in self.party],
            "current_room_id": self.current_room_id,
            "last_campfire_room_id": self.last_campfire_room_id,
        }
        save_player(self.player.name, data)

    async def _load_save(self, save: dict) -> None:
        self.player = Character.from_dict(save["character"])
        self.party = []
        for nd in save.get("party", []):
            npc = NPC.from_dict(nd)
            self.party.append(npc)
        self.current_room_id = save.get("current_room_id", "town_square")
        self.last_campfire_room_id = save.get("last_campfire_room_id", "test_campfire")
        self.state = State.NAVIGATION

    # ═══════════════════════════════════════════════════════════════════
    # ENVIRONMENT COMMANDS
    # ═══════════════════════════════════════════════════════════════════

    async def _do_time(self) -> None:
        if not self.clock:
            await self._send("  (No world clock running.)\n")
            return
        c = self.clock
        await self._send(
            _box("TIME", [
                f"  It is {c.time_of_day_label()} ({c.time_string()}).",
                f"  Day {c.game_day + 1} — {c.moon_phase_name.capitalize()}.",
            ])
        )

    async def _do_weather(self) -> None:
        if not self.clock:
            await self._send("  (No world clock running.)\n")
            return
        room = self.world.get_room(self.current_room_id)
        if room and room.room_type == "underground":
            await self._send("  Deep underground, the weather of the surface world cannot reach you.\n")
            return
        c = self.clock
        temp_label = c.temperature_label(
            room.room_type if room else "outdoor",
            room.base_temp_f if room else 65.0,
        )
        await self._send(
            _box("WEATHER", [
                f"  Weather  : {c.current_weather.capitalize()}",
                f"  Temp     : {temp_label}",
            ])
        )

    async def _do_light(self) -> None:
        if not self.clock:
            await self._send("  (No world clock running.)\n")
            return
        room = self.world.get_room(self.current_room_id)
        rt = room.room_type if room else "outdoor"
        carried = self._carried_light()
        eff = self.clock.effective_light(rt, carried)
        ll = light_label(eff)
        lines = [f"  Lighting : {ll}"]
        if self._lit_sources:
            now = self.clock.total_minutes
            for item_id, expiry in self._lit_sources.items():
                item = get_item(item_id)
                iname = item.name if item else item_id
                remaining = max(0, expiry - now)
                if item and item.effect_params.get("fuel_minutes", 0) < 0:
                    # Lantern — fueled by oil, no numeric expiry shown
                    lines.append(f"  Source   : {iname} (burning)")
                elif remaining > 0:
                    lines.append(f"  Source   : {iname} ({remaining} min remaining)")
                else:
                    lines.append(f"  Source   : {iname} (burned out)")
        else:
            lines.append("  Source   : none (no lit light sources)")
        await self._send(_box("LIGHT", lines))

    async def _do_envdetails(self) -> None:
        """Show all environmental details with numeric values."""
        if not self.clock:
            await self._send("  (No world clock running.)\n")
            return
        c = self.clock
        room = self.world.get_room(self.current_room_id)
        rt = room.room_type if room else "outdoor"
        bt = room.base_temp_f if room else 65.0
        carried = self._carried_light()
        eff_light = c.effective_light(rt, carried)
        temp_f = c.temperature_f(rt, bt)
        lines = [
            f"  Time          : {c.time_string()}  (Day {c.game_day + 1})",
            f"  Period        : {c.time_of_day_label().capitalize()}",
            f"  Moon          : {c.moon_phase_name.capitalize()}  (night light: {round(c.moon_light * 100)}%)",
            f"  Weather       : {c.current_weather.capitalize()}",
            f"  Temperature   : {round(temp_f)}°F  ({c.temperature_label(rt, bt)})",
            f"  Ambient light : {round(c.ambient_light(rt) * 100)}%",
            f"  Carried light : {round(carried * 100)}%",
            f"  Effective     : {round(eff_light * 100)}%  ({light_label(eff_light)})",
            f"  Room type     : {rt.capitalize()}",
        ]
        await self._send(_box("ENVIRONMENT DETAILS", lines))

    async def _do_light_source(self, args: str, extinguish: bool) -> None:
        """Light or extinguish a carried light source (torch, lantern)."""
        if not self.clock:
            await self._send("  (No world clock running.)\n")
            return
        item_name = args.lower().strip()
        if not item_name:
            verb = "extinguish" if extinguish else "light"
            await self._send(f"  Usage: {verb.upper()} <item name>\n")
            return

        # Collect all party inventory
        all_inv: list[tuple[str, str]] = []  # (owner_name, item_id)
        if self.player:
            for iid in self.player.inventory:
                all_inv.append((self.player.name, iid))
        for npc in self.party:
            for iid in npc.inventory:
                all_inv.append((npc.name, iid))

        for owner, item_id in all_inv:
            item = get_item(item_id)
            if not item or item_name not in item.name.lower():
                continue
            if item.effect_type != "light_source":
                await self._send(f"  {item.name} is not a light source.\n")
                return
            if extinguish:
                if item_id in self._lit_sources:
                    del self._lit_sources[item_id]
                    await self._send(f"  You extinguish the {item.name}.\n")
                else:
                    await self._send(f"  {item.name} is not lit.\n")
                return
            else:
                # Lighting up
                if item_id in self._lit_sources:
                    await self._send(f"  {item.name} is already lit.\n")
                    return
                fuel_minutes = item.effect_params.get("fuel_minutes", 0)
                if fuel_minutes < 0:
                    # Lantern needs oil — check for oil flask in party inventory
                    oil_ids = [oid for _, oid in all_inv if oid == "oil_flask"]
                    if not oil_ids:
                        await self._send(
                            f"  The {item.name} is empty. You need an Oil Flask to fill it.\n"
                        )
                        return
                    # Consume one oil flask and grant 90 minutes of light
                    oil_id = oil_ids[0]
                    if self.player and oil_id in self.player.inventory:
                        self.player.inventory.remove(oil_id)
                    else:
                        for npc in self.party:
                            if oil_id in npc.inventory:
                                npc.inventory.remove(oil_id)
                                break
                    fuel_minutes = 90
                    await self._send(f"  You fill and light the {item.name} with oil.\n")
                else:
                    await self._send(f"  You light the {item.name}.\n")
                expiry = self.clock.total_minutes + fuel_minutes
                self._lit_sources[item_id] = expiry
                return
        await self._send(f"  No light source named '{args}' found in party inventory.\n")

    # ═══════════════════════════════════════════════════════════════════
    # HELP
    # ═══════════════════════════════════════════════════════════════════

    async def _send_help(self, topic: str = "") -> None:
        topic = topic.strip().upper()

        if topic == "TIME":
            await self._send(
                _box("HELP: TIME", [
                    "  Shows the current in-game time, day number, and moon phase.",
                    "  Usage: TIME",
                    "  The time of day affects outdoor visibility (dawn/day/dusk/night).",
                    "  Moon phase determines how bright it is on clear nights.",
                ])
            )
        elif topic == "WEATHER":
            await self._send(
                _box("HELP: WEATHER", [
                    "  Shows the current weather and temperature label.",
                    "  Usage: WEATHER",
                    "  Weather only affects outdoor and indoor rooms.",
                    "  Underground rooms are always the same temperature.",
                    "  Weather changes gradually \u2014 you will see a warning before it shifts.",
                ])
            )
        elif topic in ("LIGHT", "LIGHTING"):
            await self._send(
                _box("HELP: LIGHT", [
                    "  Shows current lighting conditions and active light sources.",
                    "  Usage: LIGHT",
                    "  Light levels affect combat: dim rooms reduce accuracy.",
                    "  Pitch black rooms forbid player-initiated combat.",
                    "  Use LIT <item> to light a torch or lantern.",
                    "  Use EXTINGUISH <item> to put one out.",
                ])
            )
        elif topic in ("LIT", "EXTINGUISH", "DOUSE"):
            await self._send(
                _box("HELP: LIT / EXTINGUISH", [
                    "  LIT <item>        \u2014 Light a torch or lantern from your inventory.",
                    "  EXTINGUISH <item> \u2014 Put out a light source.",
                    "  Examples:",
                    "    LIT TORCH",
                    "    LIT LANTERN",
                    "    EXTINGUISH TORCH",
                    "  Torches burn for 60 game-minutes then go out automatically.",
                    "  Lanterns require an Oil Flask to fill; they burn for 90 game-minutes.",
                    "  ENVDETAILS shows how much fuel is remaining.",
                ])
            )
        elif topic in ("ENVDETAILS", "ENV"):
            await self._send(
                _box("HELP: ENVDETAILS", [
                    "  Displays full numeric environmental information.",
                    "  Usage: ENVDETAILS  (or ENV)",
                    "  Shows exact temperature, light percentages, moon phase light, etc.",
                ])
            )
        elif topic == "ATTACK":
            await self._send(
                _box("HELP: ATTACK", [
                    "  Engage in combat with hostile creatures in the room.",
                    "  Usage: ATTACK [group]",
                    "  In the Gauntlet arena, specify a group letter: ATTACK A",
                    "  In normal rooms, ATTACK targets the first hostile group.",
                    "  Combat is automatic \u2014 your party fights using configured strategies.",
                    "  Type HELP COMBAT for more on the combat system.",
                    "  Note: Cannot attack in pitch black conditions.",
                ])
            )
        elif topic == "COMBAT":
            await self._send(
                _box("HELP: COMBAT", [
                    "  Combat is real-time and automatic. Your party acts on strategy rules.",
                    "  Configure strategies at any CAMPFIRE with MANAGE <name>.",
                    "  Lighting affects accuracy and dodge chance:",
                    "    Well-lit (80-100%) \u2014 no penalty",
                    "    Good light (60-80%) \u2014 slight penalty",
                    "    Dim (40-60%)        \u2014 moderate penalty",
                    "    Dark (20-40%)       \u2014 heavy penalty",
                    "    Very dark (5-20%)   \u2014 severe penalty",
                    "    Pitch black (<5%)   \u2014 combat forbidden (player side)",
                    "  Use LIT TORCH or LIT LANTERN to provide light before fighting.",
                    "  Some creatures (undead, predators) have Darkvision and ignore",
                    "  lighting penalties \u2014 they can attack you even in total darkness.",
                ])
            )
        else:
            await self._send(
                _box("COMMANDS", [
                    "  Movement    : N, S, E, W, U, D  or  GO <dir>",
                    "  Look        : LOOK, EXAMINE <thing>",
                    "  Inventory   : INVENTORY, EQUIP <item>, UNEQUIP <slot>",
                    "                DROP <item>, PICK UP <item>",
                    "  Character   : STATS, GOLD, SKILLS, LEARN <skill>",
                    "                MODIFIERS, UPGRADE <modifier>",
                    "  Party       : PARTY, TALK <npc>, DISMISS <npc>",
                    "  Campfire    : CAMPFIRE or REST",
                    "  Combat      : ATTACK [group]",
                    "  Environment : TIME, WEATHER, LIGHT, ENVDETAILS",
                    "                LIT <item>, EXTINGUISH <item>",
                    "  Other       : SAVE, HELP [topic]",
                    "",
                    "  Type HELP <topic> for details, e.g. HELP COMBAT or HELP LIGHT",
                ])
            )
