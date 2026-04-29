"""
Combat engine.

CombatSession manages a real-time tick-based battle between two parties.
Each combatant has an action_cooldown that counts down each tick.
When cooldown reaches 0, the combatant's strategy is evaluated and
the resulting action is resolved.

Speed determines how fast the cooldown resets:
  initial_cooldown = BASE_COOLDOWN_TICKS / effective_speed

`combat_tick()` is scheduled as an asyncio task by GameSession.
Results are streamed to the player via an async send callback.
"""
from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable

from server.config import (
    BASE_COOLDOWN_TICKS,
    COMBAT_INITIAL_DELAY,
    COMBAT_MIN_SLEEP,
    COMBAT_TICK_INTERVAL,
    CRITICAL_DAMAGE_MULTIPLIER,
    CRITICAL_HIT_CHANCE,
    DEBUG_NO_DEATH_PENALTY,
    DEBUG_RESPAWN_ROOM_ID,
    DEATH_GOLD_LOSS_PCT,
    DEATH_XP_LOSS_PCT,
    FLEE_SUCCESS_RATE,
    STAMINA_DRAIN_FLEE,
)
from server.engine.character import Character
from server.engine.domain.items import equipped_weapon
from server.engine.npc import NPC
from server.engine.domain.skills import get_skill
from server.engine.strategy import evaluate_strategy
from server.engine.actions import Attack, Defend, Flee, UseSkill, UseItem, CombatResult
from server.engine.world_clock import lighting_combat_penalties


# ── Position grid ─────────────────────────────────────────────────────────────
# Grid is 2 rows x 3 cols.  Row 0 = FRONT, Row 1 = BACK.
# Melee classes: warrior, thief  → auto-placed FRONT
# Ranged/caster classes: mage, cleric  → auto-placed BACK
FRONT_ROW = 0
BACK_ROW = 1
MELEE_CLASSES = {"warrior", "thief"}
RANGED_WEAPON_TYPES = {"bow", "staff"}

# Basic attack spell per caster class — tried before melee when an expensive spell fails MP check.
CASTER_BASIC_SPELLS: dict[str, str] = {
    "mage": "arcane_bolt",
    "cleric": "smite",
}


def _is_ranged_attacker(char: "Character | NPC") -> bool:
    """True if the character's equipped weapon is ranged/magical, or they are a caster class."""
    w = equipped_weapon(getattr(char, "equipment", {}))
    if w and w.weapon_type in RANGED_WEAPON_TYPES:
        return True
    return char.class_type in {"mage", "cleric"}


# ── Flavour text pools ────────────────────────────────────────────────────────

_ATTACK_VERBS: dict[str, list[str]] = {
    "sword":  ["slashes", "cleaves", "drives a blade into", "cuts across", "lunges at"],
    "axe":    ["hacks into", "buries an axe in", "cleaves", "chops at", "swings wildly at"],
    "dagger": ["stabs", "plunges a dagger into", "rakes", "slips a blade past", "jabs at"],
    "mace":   ["bludgeons", "smashes", "hammers", "cracks a mace across", "clubs"],
    "staff":  ["strikes", "cracks a staff into", "jabs", "whacks", "beats"],
    "bow":    ["looses an arrow at", "fires at", "shoots", "draws and releases on", "peppers"],
    "fist":   ["punches", "headbutts", "shoves", "clouts", "whacks"],
}
_MISS_LINES: dict[str, list[str]] = {
    "sword":  ["{a} swings wide — the blade whistles past {t} (missed)",
               "{t} sidesteps {a}'s slash (missed)"],
    "axe":    ["{a} over-swings — the axe thuds into the dirt (missed)",
               "{t} ducks under {a}'s overhead chop (missed)"],
    "dagger": ["{a}'s dagger scrapes off {t}'s armour (missed)",
               "{t} twists away from {a}'s stab (missed)"],
    "mace":   ["{a} swings but {t} sways back out of reach (missed)",
               "{t} steps inside {a}'s arc and the blow glances off (missed)"],
    "staff":  ["{a}'s staff beats empty air (missed)",
               "{t} knocks {a}'s staff aside (missed)"],
    "bow":    ["{a}'s arrow skips off the ground near {t} (missed)",
               "{t} dives clear of {a}'s shot (missed)"],
    "fist":   ["{a} swings a wild punch — {t} ducks it (missed)",
               "{a}'s haymaker misses entirely (missed)"],
}
_BLOCK_LINES = [
    "{t} raises their shield — {a}'s blow rings off the iron rim (blocked)",
    "{t} interposes their shield — the force travels harmlessly down their arm (blocked)",
    "{t} catches the blow squarely on their buckler (blocked)",
    "{t} braces and stops {a}'s attack cold (blocked)",
]
_CRIT_LINES = [
    "A critical strike!",
    "A devastating blow!",
    "Perfectly placed!",
    "Right through the guard!",
]


def _weapon_type(char: "Character | NPC") -> str:
    w = equipped_weapon(getattr(char, "equipment", {}))
    return w.weapon_type if (w and w.weapon_type) else "fist"


def _attack_verb(wtype: str) -> str:
    return random.choice(_ATTACK_VERBS.get(wtype, _ATTACK_VERBS["fist"]))


def _miss_line(wtype: str, attacker_name: str, target_name: str) -> str:
    pool = _MISS_LINES.get(wtype, _MISS_LINES["fist"])
    return random.choice(pool).format(a=attacker_name, t=target_name)


def _block_line(attacker_name: str, target_name: str) -> str:
    return random.choice(_BLOCK_LINES).format(a=attacker_name, t=target_name)


class CombatState(Enum):
    ACTIVE = "active"
    VICTORY = "victory"
    DEFEAT = "defeat"


@dataclass
class Combatant:
    character: Character | NPC
    cooldown: float = 0.0         # initial delay before first action (seconds)
    is_player_side: bool = True
    row: int = 0                  # 0 = FRONT, 1 = BACK
    col: int = 0                  # 0-2 column in the grid
    _next_action_bonus: float = 0.0  # seconds shaved off next sleep (battle_cry etc.)
    _channeling: asyncio.Task | None = field(default=None)  # in-progress channeling task
    _channeling_spell_mp: int = 0    # mana cost of spell being channeled (for refund)

    def reset_cooldown(self) -> None:
        self.cooldown = self.character.action_interval

    @property
    def name(self) -> str:
        return self.character.name

    @property
    def is_alive(self) -> bool:
        return self.character.is_alive

    @property
    def is_melee(self) -> bool:
        return self.character.class_type in MELEE_CLASSES


class CombatSession:
    MAX_PARTY = 5
    MAX_ENEMIES = 6

    def __init__(
        self,
        player_party: list[Character | NPC],   # player + companions
        enemy_party: list[NPC],
        send: Callable[[str], Awaitable[None]],
        lighting: float = 1.0,   # effective light level [0.0, 1.0] at combat start
        survival_multiplier: float = 1.0,  # from GameSession._apply_survival_penalties()
    ) -> None:
        self.player_combatants: list[Combatant] = self._assign_positions(
            [Combatant(c, cooldown=c.action_interval, is_player_side=True) for c in player_party]
        )
        self.enemy_combatants: list[Combatant] = self._assign_positions(
            [Combatant(c, cooldown=c.action_interval, is_player_side=False) for c in enemy_party]
        )
        self.state = CombatState.ACTIVE
        self.tick_counter = 0
        self._send = send
        self._lighting = lighting
        self._hit_penalty, self._dodge_penalty = lighting_combat_penalties(lighting)
        self.survival_multiplier: float = survival_multiplier
        self._task: asyncio.Task | None = None
        self.result: CombatResult | None = None  # set after run_and_get_result() completes
        self._ended = asyncio.Event()  # set atomically when combat reaches terminal state

    @staticmethod
    def _assign_positions(combatants: list["Combatant"]) -> list["Combatant"]:
        """Fill grid positions.
        Characters with stored grid_row/grid_col (-1 = auto) keep their saved spot.
        The rest are auto-placed: melee → FRONT, casters → BACK.
        Conflicts (two chars want the same cell) are resolved by bumping the
        auto-assigned one to the next free cell.
        """
        MAX_GRID_SLOTS = 6  # 2 rows × 3 columns
        if len(combatants) > MAX_GRID_SLOTS:
            raise ValueError(
                f"Party of {len(combatants)} exceeds grid capacity ({MAX_GRID_SLOTS} slots)."
            )
        occupied: set[tuple[int, int]] = set()
        auto_queue: list[Combatant] = []

        # First pass: apply stored positions
        for c in combatants:
            r = c.character.grid_row
            col = c.character.grid_col
            if r in (FRONT_ROW, BACK_ROW) and 0 <= col <= 2:
                cell = (r, col)
                if cell not in occupied:
                    c.row, c.col = r, col
                    occupied.add(cell)
                    continue
            # No valid stored position — will be auto-assigned
            auto_queue.append(c)

        # Second pass: auto-assign remaining characters
        front_col = 0
        back_col = 0
        for c in auto_queue:
            if c.character.class_type in MELEE_CLASSES:
                # Find next free front cell
                while front_col < 3 and (FRONT_ROW, front_col) in occupied:
                    front_col += 1
                if front_col < 3:
                    c.row, c.col = FRONT_ROW, front_col
                    occupied.add((FRONT_ROW, front_col))
                    front_col += 1
                else:
                    # Front full — spill to back
                    while back_col < 3 and (BACK_ROW, back_col) in occupied:
                        back_col += 1
                    c.row, c.col = BACK_ROW, min(back_col, 2)
                    occupied.add((BACK_ROW, min(back_col, 2)))
                    back_col += 1
            else:
                while back_col < 3 and (BACK_ROW, back_col) in occupied:
                    back_col += 1
                if back_col < 3:
                    c.row, c.col = BACK_ROW, back_col
                    occupied.add((BACK_ROW, back_col))
                    back_col += 1
                else:
                    while front_col < 3 and (FRONT_ROW, front_col) in occupied:
                        front_col += 1
                    c.row, c.col = FRONT_ROW, min(front_col, 2)
                    occupied.add((FRONT_ROW, min(front_col, 2)))
                    front_col += 1
        return combatants

    # ── Position / protection helpers ─────────────────────────────────────────

    def _front_guards(self, side: list[Combatant]) -> list[Combatant]:
        """Return alive front-row melee combatants on this side."""
        return [c for c in side if c.is_alive and c.row == FRONT_ROW and c.is_melee]

    def _is_melee_protected(
        self,
        target: Combatant,
        attacker_side: list[Combatant],  # the ATTACKER's side (unused here)
        defender_side: list[Combatant],
    ) -> bool:
        """
        A back-row character is protected from melee when:
          - They are in the back row AND
          - Either the front combatant in their column is alive,
            OR there are still 2+ melee guards in the front row overall.
        A front-row character is always reachable.
        """
        if target.row == FRONT_ROW:
            return False
        guards = self._front_guards(defender_side)
        if not guards:
            return False
        # Column guard: character directly in front is alive
        same_col_guard = any(
            g for g in guards if g.col == target.col
        )
        if same_col_guard:
            return True
        # Line guard: 2+ front-row melee form an unbroken screen
        if len(guards) >= 2:
            return True
        return False

    def _reachable_enemies(
        self, actor: Combatant, enemy_side: list[Combatant]
    ) -> list[Combatant]:
        """Return alive enemies reachable by this actor considering protection."""
        alive = [c for c in enemy_side if c.is_alive]
        if _is_ranged_attacker(actor.character):
            return alive  # ranged/magic always reaches everyone
        # Melee: filter out protected back-row targets
        defender_side = enemy_side
        reachable = [c for c in alive if not self._is_melee_protected(c, [], defender_side)]
        # If somehow every enemy is protected (shouldn't happen), fall back to front row only
        if not reachable:
            front = [c for c in alive if c.row == FRONT_ROW]
            return front if front else alive
        return reachable

    # ── AoE grid targeting ────────────────────────────────────────────────────

    @staticmethod
    def _resolve_aoe_targets(
        target_type: str,
        row: int,
        col: int,
        combatants: list["Combatant"],
        name: str | None = None,
    ) -> list["Combatant"]:
        alive = [c for c in combatants if c.is_alive]
        if target_type == "all_enemies":
            return alive
        if target_type == "single":
            if name:
                return [c for c in alive if c.name.lower() == name.lower()]
            return alive[:1]
        if target_type == "grid_1x1":
            return [c for c in alive if c.row == row and c.col == col]
        if target_type == "grid_1x2":
            return [c for c in alive if c.row == row and col <= c.col <= col + 1]
        if target_type == "grid_2x2":
            return [c for c in alive if row <= c.row <= row + 1 and col <= c.col <= col + 1]
        return alive

    # ── Damage application (with concentration check) ─────────────────────────

    def _apply_damage(
        self,
        target: "Combatant",
        amount: int,
        log: list[str],
    ) -> int:
        actual = target.character.take_damage(amount)
        if target._channeling is not None and not target._channeling.done():
            int_val = getattr(target.character, "INT", 10)
            int_modifier = (int_val - 10) // 2
            roll = random.randint(1, 20) + int_modifier
            if roll < 12:
                target._channeling.cancel()
                target._channeling = None
                refund = target._channeling_spell_mp // 2
                target.character.mp = min(
                    target.character.max_mp,
                    target.character.mp + refund,
                )
                target._channeling_spell_mp = 0
                log.append(
                    f"  {target.name}'s concentration breaks! ({refund} MP refunded)"
                )
        return actual

    # ── Zero-mana mage action ─────────────────────────────────────────────────

    def _do_action_mage_zero_mp(self, actor: "Combatant", log: list[str]) -> None:
        char = actor.character
        if not getattr(char, "_zero_mp_message_shown", True):
            log.append(
                f"  {actor.name} reaches for the arcane but finds nothing."
                f" They can only brace themselves."
            )
            char._zero_mp_message_shown = True  # type: ignore[attr-defined]
        if not hasattr(char, "status_effects"):
            char.status_effects = {}  # type: ignore[attr-defined]
        char.status_effects["defending"] = 1  # type: ignore[attr-defined]
        log.append(
            f"  {actor.name} braces — no mana to cast, moving to dodge."
        )

    # ── Main loop ─────────────────────────────────────────────────────────────

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(self._run())

    async def run_and_get_result(self) -> CombatResult:
        """Run combat to completion and return CombatResult."""
        await self._run()
        return self.result  # type: ignore[return-value]  # always set by _run()

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ── Main loop — one asyncio task per combatant ────────────────────────────

    async def _run(self) -> None:
        await self._send(self._combat_start_banner())
        all_combatants = self.player_combatants + self.enemy_combatants
        combatant_tasks = [
            asyncio.get_event_loop().create_task(self._combatant_loop(c))
            for c in all_combatants
        ]
        try:
            # Poll until combat ends; each combatant loop calls _check_combat_end()
            while self.state == CombatState.ACTIVE:
                await asyncio.sleep(COMBAT_INITIAL_DELAY)
        except asyncio.CancelledError:
            pass
        # Cancel all running combatant tasks
        for t in combatant_tasks:
            t.cancel()
        await asyncio.gather(*combatant_tasks, return_exceptions=True)
        if self.state != CombatState.ACTIVE:
            summary = self._build_end_summary()
            self.result = CombatResult(
                state=self.state.value,
                summary=summary,
            )

    async def _combatant_loop(self, actor: Combatant) -> None:
        """Independent action loop for one combatant.
        Sleeps for the character's action interval between acts,
        producing a continuous real-time stream of individual messages.
        """
        # Stagger first action by the pre-set initial cooldown (already in seconds)
        initial_delay = actor.cooldown
        try:
            await asyncio.sleep(initial_delay)
            while self.state == CombatState.ACTIVE and not self._ended.is_set() and actor.is_alive:
                # Tick status effects for this combatant
                log: list[str] = []
                stunned = self._tick_status_effects(actor, log)
                if log:
                    await self._send("\n".join(log) + "\n")
                self._check_combat_end()
                if self.state != CombatState.ACTIVE or not actor.is_alive:
                    break

                if not stunned:
                    log = []
                    self._do_action(actor, log)
                    if log:
                        await self._send("\n".join(log) + "\n")
                    self._check_combat_end()
                    if self.state != CombatState.ACTIVE:
                        break

                # Sleep until next action, honouring any speed-up bonus
                interval = actor.character.action_interval
                bonus = actor._next_action_bonus
                actor._next_action_bonus = 0.0
                await asyncio.sleep(max(COMBAT_MIN_SLEEP, interval - bonus))
        except asyncio.CancelledError:
            pass

    def _check_combat_end(self) -> None:
        if self.state != CombatState.ACTIVE:
            return
        if self._ended.is_set():
            return  # Already transitioning — prevent double-fire
        if not any(c.is_alive for c in self.enemy_combatants):
            self.state = CombatState.VICTORY
            self._ended.set()
        elif not any(c.is_alive for c in self.player_combatants):
            self.state = CombatState.DEFEAT
            self._ended.set()

    # ── Action dispatcher ─────────────────────────────────────────────────────

    def _do_action(self, actor: Combatant, log: list[str]) -> None:
        if actor.is_player_side:
            ally_combatants = self.player_combatants
            enemy_combatants = self.enemy_combatants
        else:
            ally_combatants = self.enemy_combatants
            enemy_combatants = self.player_combatants

        allies = [c.character for c in ally_combatants if c.is_alive]
        # Respect protection — only pass reachable enemies to the strategy
        reachable = self._reachable_enemies(actor, enemy_combatants)
        enemies = [c.character for c in reachable]

        if not enemies:
            # All enemies protected — announce it and wait
            log.append(f"  {actor.name} looks for an opening but the enemy line holds.")
            return

        action, target_char = evaluate_strategy(actor.character, allies, enemies)

        # --- DEFEND ---
        if isinstance(action, Defend):
            if not hasattr(actor.character, "status_effects"):
                actor.character.status_effects = {}  # type: ignore[attr-defined]
            actor.character.status_effects["defending"] = 1  # type: ignore[attr-defined]
            log.append(
                random.choice([
                    f"  {actor.name} hunkers behind their guard, steeling for the next blow.",
                    f"  {actor.name} raises their weapon and shields their vitals.",
                    f"  {actor.name} plants their feet and takes a defensive stance.",
                ])
            )
            return

        # --- FLEE ---
        if isinstance(action, Flee):
            # Fleeing costs stamina (player-side characters only)
            if actor.is_player_side and hasattr(actor.character, "stamina"):
                actor.character.stamina = max(0.0, actor.character.stamina - STAMINA_DRAIN_FLEE)
            if random.random() < FLEE_SUCCESS_RATE:
                log.append(
                    random.choice([
                        f"  {actor.name} breaks from the line and flees into the darkness!",
                        f"  {actor.name} turns and sprints away \u2014 gone!",
                    ])
                )
                actor.character.hp = 0
            else:
                log.append(
                    random.choice([
                        f"  {actor.name} tries to flee but the enemy cuts off the escape route!",
                        f"  {actor.name} stumbles trying to run \u2014 hemmed in on all sides!",
                    ])
                )
            return

        # --- USE_SKILL ---
        if isinstance(action, UseSkill):
            self._resolve_skill(actor, action.skill_id, target_char, allies, enemies, log)
            return

        # --- USE_ITEM ---
        if isinstance(action, UseItem):
            self._resolve_item(actor, action.item_id, target_char, log)
            return

        # --- ATTACK (default — Attack instance or anything unrecognised) ---
        self._resolve_attack(actor.character, target_char, log,
                             is_player_side=actor.is_player_side)

    # ── Attack resolution ─────────────────────────────────────────────────────

    def _resolve_attack(
        self,
        attacker: Character | NPC,
        target: Character | NPC | None,
        log: list[str],
        is_player_side: bool = True,
    ) -> None:
        if target is None or not target.is_alive:
            log.append(f"  {attacker.name} looks for a target but finds none.")
            return

        wtype = _weapon_type(attacker)

        # Darkvision: enemy NPCs with darkvision ignore lighting penalty
        has_darkvision = not is_player_side and getattr(attacker, "darkvision", False)
        atk_hit_penalty   = 0.0 if has_darkvision else self._hit_penalty
        atk_dodge_penalty = 0.0 if has_darkvision else self._dodge_penalty

        if not attacker.roll_hit(target, hit_penalty=atk_hit_penalty):
            log.append(f"  {_miss_line(wtype, attacker.name, target.name)}")
            return

        # Dodge chance — reduced by darkness (target can't see to dodge)
        base_dodge = getattr(target, "dodge_bonus", lambda: 0.0)()
        effective_dodge = max(0.0, base_dodge - atk_dodge_penalty)
        if random.random() < effective_dodge:
            log.append(
                f"  {target.name} slips out of {attacker.name}'s reach (dodged)"
            )
            return

        # Block chance
        block_chance = getattr(target, "block_bonus", lambda: 0.0)()
        if random.random() < block_chance:
            log.append(f"  {_block_line(attacker.name, target.name)}")
            return

        # Apply survival penalty multiplier to player-side damage rolls
        survival_mult = self.survival_multiplier if is_player_side else 1.0
        dmg = attacker.roll_damage(multiplier=survival_mult)

        # Critical hit
        crit = random.random() < CRITICAL_HIT_CHANCE
        if crit:
            dmg = round(dmg * CRITICAL_DAMAGE_MULTIPLIER)

        # Berserker rage bonus
        if "berserker" in getattr(attacker, "status_effects", {}):
            dmg = round(dmg * CRITICAL_DAMAGE_MULTIPLIER)

        actual = target.take_damage(dmg)
        verb = _attack_verb(wtype)
        dead_tag = " [DEAD]" if not target.is_alive else ""
        dmg_tag = f"({actual} dmg — critical)" if crit else f"({actual} dmg)"

        log.append(f"  {attacker.name} {verb} {target.name} {dmg_tag}{dead_tag}")

        # Poison blade proc
        if "poison_blade" in getattr(attacker, "status_effects", {}):
            if not hasattr(target, "status_effects"):
                target.status_effects = {}  # type: ignore[attr-defined]
            target.status_effects["poison"] = 4  # type: ignore[attr-defined]
            del attacker.status_effects["poison_blade"]  # type: ignore[attr-defined]
            log.append(f"  The blade was poisoned — {target.name} feels the venom spreading")

    # ── Skill resolution ─────────────────────────────────────────────────────

    def _resolve_skill(
        self,
        actor: Combatant,
        skill_id: str,
        target: Character | NPC | None,
        allies: list[Character | NPC],
        enemies: list[Character | NPC],
        log: list[str],
    ) -> None:
        char = actor.character
        skill = get_skill(skill_id)

        if skill is None:
            log.append(f"  {char.name} tries to use unknown skill '{skill_id}'.")
            return
        if skill_id not in char.unlocked_skills:
            log.append(f"  {char.name} doesn't know '{skill.name}'.")
            return
        if char.mp < skill.mp_cost:
            # Cascade: try the class's basic spell before falling to melee.
            # Guard: don't cascade if the failing spell IS the basic spell (prevents infinite loop).
            basic_spell_id = CASTER_BASIC_SPELLS.get(char.class_type)
            if (
                basic_spell_id
                and basic_spell_id != skill_id
                and basic_spell_id in char.unlocked_skills
            ):
                basic_skill = get_skill(basic_spell_id)
                if basic_skill and char.mp >= basic_skill.mp_cost:
                    log.append(
                        f"  {char.name} is low on MP — casting {basic_skill.name}"
                        f" instead of {skill.name}."
                    )
                    self._resolve_skill(actor, basic_spell_id, target, allies, enemies, log)
                    return
            log.append(f"  {char.name} has insufficient MP for {skill.name}. Attacking instead.")
            self._resolve_attack(char, target, log)
            return

        char.mp -= skill.mp_cost
        et = skill.effect_type
        ep = skill.effect_params

        # Damage school → apply spell intensity
        damage_type = ep.get("damage_type", "")
        intensity_bonus = char.spell_intensity_bonus(damage_type)

        # --- damage ---
        if et == "damage":
            if target is None or not target.is_alive:
                log.append(f"  {char.name} has no target for {skill.name}.")
                return
            if "multiplier" in ep:
                raw_dmg = char.roll_damage(ep["multiplier"])
            else:
                raw_dmg = ep.get("base_damage", 10)
                str_bonus = max(0, (char.STR - 10) // 2)
                raw_dmg += str_bonus
            raw_dmg = round(raw_dmg * (1 + intensity_bonus))
            # Undead bonus (smite)
            if ep.get("undead_bonus") and getattr(target, "template_id", "").startswith("skeleton"):
                raw_dmg = round(raw_dmg * ep["undead_bonus"])
            # Assassinate poison bonus
            if ep.get("poison_bonus_multiplier") and "poison" in getattr(target, "status_effects", {}):
                raw_dmg = round(raw_dmg * ep["poison_bonus_multiplier"])
            actual = target.take_damage(raw_dmg)
            status = " [DEAD]" if not target.is_alive else ""
            log.append(f"  {char.name} uses {skill.name} on {target.name} for {actual} {damage_type} damage!{status}")

        # --- damage_aoe ---
        elif et in ("damage_aoe",):
            raw_base = ep.get("base_damage", 10)
            raw_base = round(raw_base * (1 + intensity_bonus))
            for t in list(enemies if actor.is_player_side else allies):
                if not t.is_alive:
                    continue
                dmg = max(1, random.randint(round(raw_base * 0.8), round(raw_base * 1.2)))
                actual = t.take_damage(dmg)
                log.append(f"    {t.name}: {actual} {damage_type} dmg.")
                if "status" in ep and hasattr(t, "status_effects"):
                    t.status_effects[ep["status"]] = ep.get("duration_ticks", 2)  # type: ignore[index]
            log.insert(-1 if log else 0, f"  {char.name} unleashes {skill.name}!")

        # --- damage_chain ---
        elif et == "damage_chain":
            chain_count = ep.get("chain_count", 3)
            targets_hit = (enemies if actor.is_player_side else allies)[:chain_count]
            raw_base = ep.get("base_damage", 10)
            raw_base = round(raw_base * (1 + intensity_bonus))
            log.append(f"  {char.name} unleashes {skill.name}!")
            for t in targets_hit:
                if not t.is_alive:
                    continue
                dmg = random.randint(round(raw_base * 0.8), round(raw_base * 1.2))
                actual = t.take_damage(dmg)
                log.append(f"    → {t.name}: {actual} {damage_type} dmg.")

        # --- damage_status ---
        elif et == "damage_status":
            if target is None or not target.is_alive:
                log.append(f"  {char.name} has no target for {skill.name}.")
                return
            raw = ep.get("base_damage", 10)
            raw = round(raw * (1 + intensity_bonus))
            actual = target.take_damage(raw)
            log.append(f"  {char.name} hits {target.name} with {skill.name} for {actual} {damage_type} damage!")
            if "status" in ep and hasattr(target, "status_effects"):
                status_name = ep["status"]
                duration = ep.get("duration_ticks", 2)
                # Only show "is now <status>" message if status wasn't already present
                if status_name not in target.status_effects:
                    log.append(f"    {target.name} is now {status_name}!")
                target.status_effects[status_name] = duration  # type: ignore[index]

        # --- heal ---
        elif et == "heal":
            t = target if target and target.is_alive else char
            raw = ep.get("base_heal", 20)
            bonus = char.spell_intensity_bonus("heal")
            raw = round(raw * (1 + bonus))
            healed = t.heal(raw)
            log.append(f"  {char.name} heals {t.name} for {healed} HP. ({t.hp}/{t.max_hp})")

        # --- heal_aoe ---
        elif et == "heal_aoe":
            raw = ep.get("base_heal", 20)
            bonus = char.spell_intensity_bonus("heal")
            raw = round(raw * (1 + bonus))
            heal_targets = allies if actor.is_player_side else (
                [c.character for c in self.enemy_combatants if c.is_alive]
            )
            log.append(f"  {char.name} casts {skill.name}!")
            for t in heal_targets:
                healed = t.heal(raw)
                log.append(f"    {t.name}: +{healed} HP ({t.hp}/{t.max_hp})")

        # --- status_apply ---
        elif et == "status_apply":
            scope = ep.get("target_scope", "self")
            status_name = ep.get("status", "")
            duration = ep.get("duration_ticks", 2)
            apply_targets: list[Character | NPC] = []
            if scope == "self":
                apply_targets = [char]
            elif scope == "all_enemies":
                apply_targets = list(enemies if actor.is_player_side else allies)
            elif scope == "single_ally":
                apply_targets = [target] if target else [char]
            else:
                apply_targets = [char]
            for t in apply_targets:
                if hasattr(t, "status_effects"):
                    t.status_effects[status_name] = duration  # type: ignore[index]
            names = ", ".join(t.name for t in apply_targets)
            log.append(f"  {char.name} uses {skill.name}! {names} → {status_name} ({duration}t)")

        # --- status_remove ---
        elif et == "status_remove":
            t = target if target else char
            status_to_remove = ep.get("status", "")
            if hasattr(t, "status_effects") and status_to_remove in t.status_effects:  # type: ignore[operator]
                del t.status_effects[status_to_remove]  # type: ignore[operator]
                log.append(f"  {char.name} cures {t.name} of {status_to_remove}!")
            else:
                log.append(f"  {char.name} uses {skill.name} but {t.name} isn't affected.")

        # --- cooldown_reduce_allies ---
        elif et == "cooldown_reduce_allies":
            reduction_secs = ep.get("ticks", 2) * COMBAT_TICK_INTERVAL
            side = self.player_combatants if actor.is_player_side else self.enemy_combatants
            log.append(f"  {char.name} rallies the party with {skill.name}")
            for combo in side:
                if combo.is_alive and combo is not actor:
                    combo._next_action_bonus = reduction_secs
                    log.append(f"    {combo.name} readies faster")

        else:
            log.append(f"  {char.name} uses {skill.name}.")

    # ── Item use in combat ────────────────────────────────────────────────────

    def _resolve_item(
        self,
        actor: Combatant,
        item_id: str,
        target: Character | NPC | None,
        log: list[str],
    ) -> None:
        from server.engine.domain.items import get_item
        from server.engine.item_effects import parse_item_effect, HealEffect, RestoreMPEffect, StatusRemoveEffect
        char = actor.character
        if item_id not in char.inventory:
            log.append(f"  {char.name} reaches for {item_id} but doesn't have it.")
            self._resolve_attack(char, target, log)
            return
        item = get_item(item_id)
        if item is None:
            log.append(f"  {char.name} tries to use unknown item '{item_id}'.")
            return
        char.inventory.remove(item_id)
        t = target if target else char
        effect = parse_item_effect(item.effect_type, item.effect_params)
        if isinstance(effect, HealEffect):
            healed = t.heal(effect.amount)
            log.append(f"  {char.name} uses {item.name} on {t.name}: +{healed} HP.")
        elif isinstance(effect, RestoreMPEffect):
            restored = char.restore_mp(effect.amount)
            log.append(f"  {char.name} uses {item.name}: +{restored} MP.")
        elif isinstance(effect, StatusRemoveEffect):
            if hasattr(t, "status_effects") and effect.status_id in t.status_effects:  # type: ignore[operator]
                del t.status_effects[effect.status_id]  # type: ignore[operator]
                log.append(f"  {char.name} uses {item.name} on {t.name}: {effect.status_id} cured!")
        else:
            log.append(f"  {char.name} uses {item.name}.")

    # ── Status effect tick ────────────────────────────────────────────────────

    def _tick_status_effects(self, c: Combatant, log: list[str]) -> bool:
        """Tick status effects; returns True if the combatant is stunned this turn."""
        se: dict[str, int] = getattr(c.character, "status_effects", {})
        expired = []
        stunned = False
        for status, ticks in list(se.items()):
            if status == "poison":
                dmg = random.randint(3, 7)
                actual = c.character.take_damage(dmg)
                log.append(
                    random.choice([
                        f"  Poison courses through {c.name}'s veins ({actual} dmg)",
                        f"  {c.name} winces as venom burns inside them ({actual} dmg)",
                    ])
                )
            elif status == "burn":
                dmg = random.randint(4, 9)
                actual = c.character.take_damage(dmg)
                log.append(
                    random.choice([
                        f"  Flames lick at {c.name} ({actual} dmg)",
                        f"  {c.name} is scorched ({actual} dmg)",
                    ])
                )
            elif status == "stun":
                stunned = True
                log.append(
                    random.choice([
                        f"  {c.name} is stunned — they stagger and lose their action",
                        f"  {c.name} shakes their head, dazed — can't act this turn",
                    ])
                )
            elif status == "slow":
                pass
            se[status] = ticks - 1
            if se[status] <= 0:
                expired.append(status)
        for s in expired:
            del se[s]
            log.append(f"  {c.name} shakes off {s}")
        return stunned

    # ── Display helpers ───────────────────────────────────────────────────────

    def _combat_start_banner(self) -> str:
        lines = ["\n" + "═" * 60, "  \u2694  COMBAT BEGINS", "\u2500" * 60]

        def _render_grid(combatants: list[Combatant], label: str) -> list[str]:
            grid: dict[tuple[int, int], str] = {}
            for c in combatants:
                grid[(c.row, c.col)] = c.name[:12]
            rows = []
            for r, row_label in ((FRONT_ROW, "FRONT"), (BACK_ROW, "BACK ")):
                cells = []
                for col in range(3):
                    name = grid.get((r, col), "      ")
                    cells.append(f"{name:<12}")
                rows.append(f"  {row_label}  [ {' | '.join(cells)} ]")
            return [f"  {label}"] + rows

        lines += _render_grid(self.player_combatants, "Your party:")
        lines += [""]
        lines += _render_grid(self.enemy_combatants, "Enemies:")
        lines += [
            "",
            "  FRONT row: melee range only  |  BACK row: ranged/magic only",
            "  (Back row is shielded while 2+ melee guards hold the front line)",
            "\u2550" * 60,
        ]
        return "\n".join(lines)

    def _build_end_summary(self) -> list[str]:
        if self.state == CombatState.VICTORY:
            lines = ["\n" + "═" * 60, "  ✦  VICTORY!", "─" * 60]
            for c in self.player_combatants:
                lines.append(
                    f"  {c.name}: {c.character.hp}/{c.character.max_hp} HP"
                )
            # Calculate XP / loot
            total_xp = sum(
                getattr(c.character, "xp_reward", 0)
                for c in self.enemy_combatants
            )
            total_gold = sum(
                getattr(c.character, "roll_gold", lambda: 0)()
                for c in self.enemy_combatants
            )
            loot: list[str] = []
            for c in self.enemy_combatants:
                loot.extend(getattr(c.character, "roll_loot", lambda: [])())
            lines.append(f"\n  Total XP earned : {total_xp}")
            lines.append(f"  Gold found      : {total_gold}g")
            if loot:
                lines.append(f"  Items looted    : {', '.join(loot)}")
            lines.append("═" * 60)
            return lines
        else:
            lines = ["\n" + "═" * 60, "  ✖  DEFEAT", "─" * 60]
            if DEBUG_NO_DEATH_PENALTY:
                lines.append("  [Debug mode] No penalties. Respawning at proving grounds...")
            else:
                lines.append(
                    f"  You lost {int(DEATH_XP_LOSS_PCT * 100)}% XP "
                    f"and {int(DEATH_GOLD_LOSS_PCT * 100)}% gold."
                )
            lines.append("═" * 60)
            return lines

    def collect_rewards(
        self,
        player_party: list[Character | NPC],
        class_defs: dict,
    ) -> tuple[int, int, list[str]]:
        """
        Called after VICTORY to apply XP, gold, and loot to the player's party.
        Returns (total_xp, total_gold, loot_items).
        """
        if self.state != CombatState.VICTORY:
            return 0, 0, []

        total_xp = sum(
            getattr(c.character, "xp_reward", 0)
            for c in self.enemy_combatants
        )
        total_gold = sum(
            getattr(c.character, "roll_gold", lambda: 0)()
            for c in self.enemy_combatants
        )
        loot: list[str] = []
        for c in self.enemy_combatants:
            loot.extend(getattr(c.character, "roll_loot", lambda: [])())

        # Distribute XP among survivors
        survivors = [p for p in player_party if p.is_alive]
        if survivors:
            xp_each = max(1, total_xp // len(survivors))
            for p in survivors:
                class_def = class_defs.get(p.class_type, {})
                p.gain_xp(
                    xp_each,
                    class_def.get("hp_per_level", 6),
                    class_def.get("mp_per_level", 4),
                )

        # Gold to player character (first in list)
        if player_party:
            player_party[0].gold += total_gold

        # Loot to player character inventory
        if player_party:
            player_party[0].inventory.extend(loot)

        return total_xp, total_gold, loot
