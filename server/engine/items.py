"""
Item model and equipment management.
Items are loaded once at startup from data/items/*.json
and stored in a global registry.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Item:
    id: str
    name: str
    description: str
    type: str                        # "weapon" | "armor" | "consumable"
    stats: dict[str, Any]           # damage_min/max, defense, etc.
    weight: int
    value: int
    weapon_type: str | None = None   # sword, axe, bow, staff, dagger, mace
    slot: str | None = None          # head, body, hands, feet, weapon, offhand
    effect_type: str | None = None   # for consumables
    effect_params: dict[str, Any] = field(default_factory=dict)

    def short_desc(self) -> str:
        parts = [self.name]
        if self.type == "weapon":
            d = self.stats
            parts.append(f"[DMG {d.get('damage_min',0)}-{d.get('damage_max',0)}]")
        elif self.type == "armor":
            parts.append(f"[DEF {self.stats.get('defense',0)}]")
        parts.append(f"(wt:{self.weight})")
        return " ".join(parts)


# ── Registry ────────────────────────────────────────────────────────────────

_ITEM_REGISTRY: dict[str, Item] = {}


def load_items(data_dir: str) -> None:
    """Load all item JSON files from data_dir/items/ into the global registry."""
    items_dir = os.path.join(data_dir, "items")
    for fname in os.listdir(items_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(items_dir, fname), encoding="utf-8") as f:
            raw_list = json.load(f)
        for raw in raw_list:
            item = Item(
                id=raw["id"],
                name=raw["name"],
                description=raw.get("description", ""),
                type=raw["type"],
                stats=raw.get("stats", {}),
                weight=raw.get("weight", 0),
                value=raw.get("value", 0),
                weapon_type=raw.get("weapon_type"),
                slot=raw.get("slot"),
                effect_type=raw.get("effect_type"),
                effect_params=raw.get("effect_params", {}),
            )
            _ITEM_REGISTRY[item.id] = item


def get_item(item_id: str) -> Item | None:
    return _ITEM_REGISTRY.get(item_id)


def all_items() -> dict[str, Item]:
    return _ITEM_REGISTRY


# ── Equipment helpers ────────────────────────────────────────────────────────

EQUIPMENT_SLOTS = ("weapon", "offhand", "head", "body", "hands", "feet", "back")


def total_equipped_weight(equipment: dict[str, str | None]) -> int:
    """Return total weight of all equipped items."""
    total = 0
    for slot in EQUIPMENT_SLOTS:
        item_id = equipment.get(slot)
        if item_id:
            item = get_item(item_id)
            if item:
                total += item.weight
    return total


def total_equipped_defense(equipment: dict[str, str | None]) -> int:
    total = 0
    for slot in EQUIPMENT_SLOTS:
        item_id = equipment.get(slot)
        if item_id:
            item = get_item(item_id)
            if item:
                total += item.stats.get("defense", 0)
    return total


def equipped_weapon(equipment: dict[str, str | None]) -> Item | None:
    wid = equipment.get("weapon")
    return get_item(wid) if wid else None


def weapon_damage_range(equipment: dict[str, str | None]) -> tuple[int, int]:
    """Return (min, max) damage from equipped weapon, or (1, 3) fists."""
    w = equipped_weapon(equipment)
    if w:
        return w.stats.get("damage_min", 1), w.stats.get("damage_max", 3)
    return 1, 3
