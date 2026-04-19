"""
Character dataclass — shared base for both the player character and NPCs.

Key design rules (per spec):
  - Stats (STR, DEX, INT, WIS, CON, AGI) are assigned at creation and NEVER change.
  - Level-ups grant skill_points (+1) and modifier_points (+2).
  - Modifier levels affect hit chance (weapon proficiencies) and
    damage/healing multipliers (spell intensifiers).
  - effective_speed = AGI - floor(total_equipped_weight / WEIGHT_DIVISOR), min 1.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from server.config import (
    MODIFIER_BONUS_PER_LEVEL,
    WEIGHT_DIVISOR,
    BASE_ATTACK_SPEED,
    MIN_ATTACK_INTERVAL,
    MAX_ATTACK_INTERVAL,
    XP_TABLE,
)
from server.engine.items import (
    EQUIPMENT_SLOTS,
    total_equipped_weight,
    total_equipped_defense,
    equipped_weapon,
    weapon_damage_range,
    get_item,
)


# ── XP thresholds — imported from config.py ──────────────────────────────────
# See server/config.py: XP_TABLE[level] = total XP needed to reach that level


# ── Modifier catalogue ───────────────────────────────────────────────────────
# Maps modifier_id → human label and what it affects
MODIFIER_CATALOGUE: dict[str, dict[str, str]] = {
    # Weapon proficiencies
    "sword_prof":    {"label": "Sword Proficiency",    "type": "weapon_hit", "weapon_type": "sword"},
    "axe_prof":      {"label": "Axe Proficiency",      "type": "weapon_hit", "weapon_type": "axe"},
    "mace_prof":     {"label": "Mace Proficiency",     "type": "weapon_hit", "weapon_type": "mace"},
    "dagger_prof":   {"label": "Dagger Proficiency",   "type": "weapon_hit", "weapon_type": "dagger"},
    "bow_prof":      {"label": "Bow Proficiency",      "type": "weapon_hit", "weapon_type": "bow"},
    "staff_prof":    {"label": "Staff Proficiency",    "type": "weapon_hit", "weapon_type": "staff"},
    "shield_prof":   {"label": "Shield Proficiency",   "type": "block_bonus", "weapon_type": None},
    "dodge_mastery": {"label": "Dodge Mastery",        "type": "dodge_bonus", "weapon_type": None},
    # Spell intensifiers
    "fire_intensity":      {"label": "Fire Intensity",      "type": "spell_intensity", "school": "fire"},
    "frost_intensity":     {"label": "Frost Intensity",     "type": "spell_intensity", "school": "frost"},
    "lightning_intensity": {"label": "Lightning Intensity", "type": "spell_intensity", "school": "lightning"},
    "heal_power":          {"label": "Heal Power",          "type": "spell_intensity", "school": "heal"},
    "curse_intensity":     {"label": "Curse Intensity",     "type": "spell_intensity", "school": "curse"},
    "holy_power":          {"label": "Holy Power",          "type": "spell_intensity", "school": "holy"},
}

# Thirst drain multipliers keyed by temperature label from WorldClock
_THIRST_MULTIPLIERS: dict[str, float] = {
    "Freezing":   1.0,
    "Bitter Cold": 1.0,
    "Cold":        1.0,
    "Cool":        1.0,
    "Comfortable": 1.0,
    "Hot":         1.5,
    "Scorching":   2.0,
}


@dataclass
class Character:
    # Identity
    name: str
    class_type: str   # warrior | mage | thief | cleric

    # Progression
    level: int = 1
    xp: int = 0
    skill_points: int = 0
    modifier_points: int = 0

    # Display preferences
    look_mode: str = "FULL"      # "FULL" or "QUICK"
    battle_look: bool = True     # Show quick look after combat

    # Base stats — LOCKED at creation
    STR: int = 10
    DEX: int = 10
    INT: int = 10
    WIS: int = 10
    CON: int = 10
    AGI: int = 10

    # Derived HP/MP (set on creation from class base + CON/WIS)
    max_hp: int = 30
    max_mp: int = 10
    hp: int = 30
    mp: int = 10

    gold: int = 50

    # Survival stats
    hunger: float = 100.0
    max_hunger: float = 100.0
    thirst: float = 100.0
    max_thirst: float = 100.0
    stamina: float = 100.0
    max_stamina: float = 100.0

    # Equipment: slot → item_id or None
    equipment: dict[str, str | None] = field(default_factory=lambda: {
        s: None for s in EQUIPMENT_SLOTS
    })

    # Inventory: list of item_ids (duplicates allowed)
    inventory: list[str] = field(default_factory=list)

    # Modifiers: modifier_id → level (int)
    modifiers: dict[str, int] = field(default_factory=dict)

    # Unlocked skills: skill_id → level
    unlocked_skills: dict[str, int] = field(default_factory=dict)

    # Strategies (list of raw dicts, serialised/deserialised by strategy.py)
    strategies: list[dict] = field(default_factory=list)
    # Formation position — persisted so campfire positions survive into combat
    # -1 means "auto-assign based on class"
    grid_row: int = -1
    grid_col: int = -1

    # Multiplayer ownership — which player session controls this character/NPC
    # Empty string means unowned (safe to mutate by any session)
    owner: str = ""

    # Active food buffs: buff_name → expiry game-minute (clock.total_minutes)
    active_buffs: dict[str, int] = field(default_factory=dict)

    # Lit light sources: item_id → expiry in absolute game-minutes
    lit_sources: dict[str, int] = field(default_factory=dict)
    # ── Derived properties ───────────────────────────────────────────────────

    @property
    def carry_slots(self) -> int:
        base = 5
        back_id = self.equipment.get("back")
        if back_id:
            item = get_item(back_id)
            if item:
                base += item.stats.get("slot_bonus", 0)
        return base

    @property
    def carry_weight_cap(self) -> int:
        if self.class_type == "mage":
            return int(self.INT * 1.5)
        base = 20
        back_id = self.equipment.get("back")
        if back_id:
            item = get_item(back_id)
            if item:
                base += item.stats.get("weight_bonus", 0)
        return base

    @property
    def effective_speed(self) -> int:
        equipped_w = total_equipped_weight(self.equipment)
        carried_w = sum(
            (get_item(iid).weight if get_item(iid) else 0)
            for iid in self.inventory
        )
        speed = self.AGI - math.floor((equipped_w + carried_w) / WEIGHT_DIVISOR)
        return max(1, speed)

    @property
    def action_interval(self) -> float:
        """Seconds between attacks for this character.

        Formula: BASE_ATTACK_SPEED / effective_speed, clamped to [MIN, MAX].
        AGI 16, no gear → 3.0 s  |  AGI 12, 20 lb gear → 4.8 s
        """
        raw = BASE_ATTACK_SPEED / self.effective_speed
        return max(MIN_ATTACK_INTERVAL, min(MAX_ATTACK_INTERVAL, raw))

    @property
    def defense(self) -> int:
        return total_equipped_defense(self.equipment)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    # ── Modifier helpers ─────────────────────────────────────────────────────

    def weapon_hit_bonus(self) -> float:
        """Additive hit chance bonus from proficiency with equipped weapon."""
        w = equipped_weapon(self.equipment)
        if not w or not w.weapon_type:
            return 0.0
        prof_key = f"{w.weapon_type}_prof"
        level = self.modifiers.get(prof_key, 0)
        return level * MODIFIER_BONUS_PER_LEVEL

    def spell_intensity_bonus(self, school: str, clock=None) -> float:
        """Multiplicative bonus (e.g. 0.10 = +10%) for a spell school."""
        key = f"{school}_intensity"
        level = self.modifiers.get(key, 0)
        # heal_power maps to heal school
        if key not in MODIFIER_CATALOGUE:
            key = f"{school}_power"
        level = self.modifiers.get(key, level)
        base = level * MODIFIER_BONUS_PER_LEVEL
        if clock is not None and "focused" in self.get_active_buffs(clock):
            base += 0.1
        return base

    def dodge_bonus(self, clock=None) -> float:
        base = self.modifiers.get("dodge_mastery", 0) * MODIFIER_BONUS_PER_LEVEL
        if clock is not None and "alertness" in self.get_active_buffs(clock):
            base += 0.15
        return base

    def block_bonus(self) -> float:
        base = 0.0
        offhand_id = self.equipment.get("offhand")
        if offhand_id:
            item = get_item(offhand_id)
            if item:
                base = item.stats.get("block_chance", 0) / 100.0
        extra = self.modifiers.get("shield_prof", 0) * MODIFIER_BONUS_PER_LEVEL
        return base + extra

    # ── Combat helpers ───────────────────────────────────────────────────────

    def roll_damage(self, multiplier: float = 1.0) -> int:
        if self.class_type == "mage":
            w = equipped_weapon(self.equipment)
            if w is None or w.weapon_type != "staff":
                return 1
        dmg_min, dmg_max = weapon_damage_range(self.equipment)
        str_bonus = max(0, (self.STR - 10) // 2)
        base = random.randint(dmg_min, dmg_max) + str_bonus
        return max(1, round(base * multiplier))

    def spell_power_modifier(self) -> float:
        if self.class_type != "mage":
            return 1.0
        _ARMOR_TYPE_MODIFIERS = {
            "cloth": 1.0,
            "robe": 1.0,
            "leather": 0.9,
            "chain": 0.7,
            "plate": 0.0,
        }
        body_id = self.equipment.get("body")
        base = 1.0
        if body_id:
            body_item = get_item(body_id)
            if body_item and body_item.armor_type:
                base = _ARMOR_TYPE_MODIFIERS.get(body_item.armor_type, 1.0)
        # Plate = cannot cast; skip additive bonuses
        if base == 0.0:
            return 0.0
        # Add staff spell_power_bonus
        weapon = equipped_weapon(self.equipment)
        if weapon and weapon.weapon_type == "staff":
            base += weapon.spell_power_bonus / 100
        # Add spellbook spell_power_bonus from inventory
        for item_id in self.inventory:
            item = get_item(item_id)
            if item and item.effect_type == "spellbook":
                base += item.spell_power_bonus / 100
        return base

    def roll_hit(self, target: "Character", hit_penalty: float = 0.0) -> bool:
        """
        Returns True if this character's attack hits target.
        base hit 70% + weapon proficiency bonus - target dodge bonus.
        hit_penalty: additional subtracted fraction (e.g. from darkness).
        """
        base_hit = 0.70
        hit_chance = base_hit + self.weapon_hit_bonus() - target.dodge_bonus() - hit_penalty
        hit_chance = max(0.05, min(0.99, hit_chance))
        return random.random() < hit_chance

    def take_damage(self, amount: int) -> int:
        """Apply damage after defense reduction. Returns actual damage taken."""
        # Each point of defense reduces damage by ~1, min reduction 0
        reduced = max(1, amount - self.defense // 3)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def heal(self, amount: int) -> int:
        """Restore HP. Returns actual amount healed."""
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    # ── Survival drain helpers ───────────────────────────────────────────────

    def hunger_drain_rate(self, clock=None) -> float:
        """Base hunger drain per game-minute tick."""
        base = 0.1
        if clock is not None and "satiated" in self.get_active_buffs(clock):
            base *= 0.6
        return base

    def thirst_drain_rate(self, temp_label: str, clock=None) -> float:
        """Thirst drain per game-minute tick, scaled by temperature label."""
        base = 0.15 * _THIRST_MULTIPLIERS.get(temp_label, 1.0)
        if clock is not None and "quenched" in self.get_active_buffs(clock):
            base *= 0.6
        return base

    # ── Food buff helpers ────────────────────────────────────────────────────

    def apply_food_buff(self, buff_name: str, duration_minutes: int, clock) -> None:
        """Set or replace buff expiry. New buff overwrites old of same type."""
        self.active_buffs[buff_name] = clock.total_minutes + duration_minutes

    def get_active_buffs(self, clock) -> list[str]:
        """Return list of buff names whose expiry is strictly greater than clock.total_minutes."""
        now = clock.total_minutes
        return [name for name, expiry in self.active_buffs.items() if expiry > now]

    def restore_mp(self, amount: int) -> int:
        before = self.mp
        self.mp = min(self.max_mp, self.mp + amount)
        return self.mp - before

    # ── Leveling ─────────────────────────────────────────────────────────────

    def gain_xp(self, amount: int, hp_per_level: int, mp_per_level: int) -> list[str]:
        """
        Add XP. Returns a list of messages (level-up announcements if any).
        hp_per_level and mp_per_level come from the class definition.
        """
        self.xp += amount
        messages: list[str] = []
        while (
            self.level < len(XP_TABLE)
            and self.xp >= XP_TABLE[self.level]
        ):
            self.level += 1
            self.skill_points += 1
            self.modifier_points += 2
            self.max_hp += hp_per_level
            self.max_mp += mp_per_level
            self.hp = self.max_hp   # full heal on level-up
            self.mp = self.max_mp
            messages.append(
                f"  *** LEVEL UP! You are now level {self.level}! ***\n"
                f"      +{hp_per_level} Max HP, +{mp_per_level} Max MP\n"
                f"      +1 Skill Point, +2 Modifier Points"
            )
        return messages

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "class_type": self.class_type,
            "level": self.level,
            "xp": self.xp,
            "skill_points": self.skill_points,
            "modifier_points": self.modifier_points,
            "STR": self.STR, "DEX": self.DEX, "INT": self.INT,
            "WIS": self.WIS, "CON": self.CON, "AGI": self.AGI,
            "max_hp": self.max_hp, "max_mp": self.max_mp,
            "hp": self.hp, "mp": self.mp,
            "gold": self.gold,
            "hunger": self.hunger, "max_hunger": self.max_hunger,
            "thirst": self.thirst, "max_thirst": self.max_thirst,
            "stamina": self.stamina, "max_stamina": self.max_stamina,
            "equipment": self.equipment,
            "inventory": self.inventory,
            "modifiers": self.modifiers,
            "unlocked_skills": self.unlocked_skills,
            "strategies": self.strategies,
            "grid_row": self.grid_row,
            "grid_col": self.grid_col,
            "owner": self.owner,
            "active_buffs": self.active_buffs,
            "lit_sources": dict(self.lit_sources),
            "look_mode": self.look_mode,
            "battle_look": self.battle_look,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        c = cls(name=data["name"], class_type=data["class_type"])
        c.level = data.get("level", 1)
        c.xp = data.get("xp", 0)
        c.skill_points = data.get("skill_points", 0)
        c.modifier_points = data.get("modifier_points", 0)
        c.STR = data.get("STR", 10)
        c.DEX = data.get("DEX", 10)
        c.INT = data.get("INT", 10)
        c.WIS = data.get("WIS", 10)
        c.CON = data.get("CON", 10)
        c.AGI = data.get("AGI", 10)
        c.max_hp = data.get("max_hp", 30)
        c.max_mp = data.get("max_mp", 10)
        c.hp = data.get("hp", c.max_hp)
        c.mp = data.get("mp", c.max_mp)
        c.gold = data.get("gold", 50)
        c.hunger  = data.get("hunger",  100.0)
        c.max_hunger = data.get("max_hunger", 100.0)
        c.thirst  = data.get("thirst",  100.0)
        c.max_thirst = data.get("max_thirst", 100.0)
        c.stamina = data.get("stamina", 100.0)
        c.max_stamina = data.get("max_stamina", 100.0)
        c.equipment = data.get("equipment", {s: None for s in EQUIPMENT_SLOTS})
        c.inventory = data.get("inventory", [])
        c.modifiers = data.get("modifiers", {})
        c.unlocked_skills = data.get("unlocked_skills", {})
        c.strategies = data.get("strategies", [])
        c.grid_row = data.get("grid_row", -1)
        c.grid_col = data.get("grid_col", -1)
        c.owner = data.get("owner", "")
        c.active_buffs = data.get("active_buffs", {})
        c.lit_sources = data.get("lit_sources", {})
        c.look_mode = data.get("look_mode", "FULL")
        c.battle_look = data.get("battle_look", True)
        return c

    def stats_summary(self) -> str:
        w = equipped_weapon(self.equipment)
        weapon_name = w.name if w else "Unarmed"
        lines = [
            f"  Name   : {self.name}  ({self.class_type.capitalize()} Lv.{self.level})",
            f"  HP     : {self.hp}/{self.max_hp}   MP: {self.mp}/{self.max_mp}",
            f"  XP     : {self.xp}",
            f"  Gold   : {self.gold}g",
            f"  STR {self.STR:2d}  DEX {self.DEX:2d}  CON {self.CON:2d}",
            f"  INT {self.INT:2d}  WIS {self.WIS:2d}  AGI {self.AGI:2d}",
            f"  Speed  : {self.effective_speed}  →  {self.action_interval:.1f}s/attack  (AGI {self.AGI} - wt penalty {math.floor(total_equipped_weight(self.equipment)/WEIGHT_DIVISOR)})",
            f"  Defense: {self.defense}",
            f"  Weapon : {weapon_name}",
        ]
        return "\n".join(lines)
