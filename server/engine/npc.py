"""
NPC dataclass and world entity model.

NPCs share the Character base but also carry:
  - is_recruitable flag
  - recruit_dialogue text
  - room_flavor text (shown in room descriptions)
  - loot_table for drop resolution
  - xp_reward / gold_range for combat rewards
  - template_id reference

The NPC registry is loaded from data/npcs/*.json at startup.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from typing import Any

from server.engine.character import Character
from server.engine.items import EQUIPMENT_SLOTS


@dataclass
class NPC(Character):
    template_id: str = ""
    is_recruitable: bool = False
    recruit_dialogue: str = ""
    room_flavor: str = ""
    loot_table: list[dict] = field(default_factory=list)
    xp_reward: int = 0
    gold_range: tuple[int, int] = (0, 0)
    # Status effects active during combat: name → ticks_remaining
    status_effects: dict[str, int] = field(default_factory=dict)
    # Can see in darkness without penalty
    darkvision: bool = False

    def roll_loot(self) -> list[str]:
        """Return list of item_ids dropped based on loot_table chances."""
        drops: list[str] = []
        for entry in self.loot_table:
            if random.randint(1, 100) <= entry.get("chance", 0):
                drops.append(entry["item_id"])
        return drops

    def roll_gold(self) -> int:
        lo, hi = self.gold_range
        return random.randint(lo, hi)

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "template_id": self.template_id,
            "is_recruitable": self.is_recruitable,
            "recruit_dialogue": self.recruit_dialogue,
            "room_flavor": self.room_flavor,
            "loot_table": self.loot_table,
            "xp_reward": self.xp_reward,
            "gold_range": list(self.gold_range),
            "status_effects": self.status_effects,
            "darkvision": self.darkvision,
        })
        return base

    @classmethod
    def from_dict(cls, data: dict) -> "NPC":
        npc = cls(name=data["name"], class_type=data["class_type"])
        # Load Character fields
        char = Character.from_dict(data)
        npc.__dict__.update(char.__dict__)
        # NPC-specific
        npc.template_id = data.get("template_id", data.get("id", ""))
        npc.is_recruitable = data.get("is_recruitable", False)
        npc.recruit_dialogue = data.get("recruit_dialogue", "")
        npc.room_flavor = data.get("room_flavor", "")
        npc.loot_table = data.get("loot_table", [])
        npc.xp_reward = data.get("xp_reward", 0)
        gr = data.get("gold_range", [0, 0])
        npc.gold_range = (gr[0], gr[1])
        npc.status_effects = data.get("status_effects", {})
        npc.darkvision = data.get("darkvision", False)
        return npc


# ── NPC Registry ─────────────────────────────────────────────────────────────

_NPC_TEMPLATES: dict[str, dict] = {}  # template_id → raw dict


def load_npcs(data_dir: str) -> None:
    npcs_dir = os.path.join(data_dir, "npcs")
    for fname in os.listdir(npcs_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(npcs_dir, fname), encoding="utf-8") as f:
            raw_list = json.load(f)
        for raw in raw_list:
            _NPC_TEMPLATES[raw["id"]] = raw


def spawn_npc(template_id: str, class_defs: dict) -> NPC | None:
    """
    Instantiate a fresh NPC from a template.
    class_defs is the loaded classes.json dict.
    """
    raw = _NPC_TEMPLATES.get(template_id)
    if raw is None:
        return None

    import copy
    data = copy.deepcopy(raw)
    data["template_id"] = data["id"]

    # Build equipment slots map (template may provide partial dict)
    equip_raw = data.get("equipment", {})
    equipment: dict[str, str | None] = {s: None for s in EQUIPMENT_SLOTS}
    equipment.update(equip_raw)
    data["equipment"] = equipment

    # Compute HP/MP from class definition
    class_type = data.get("class_type", "warrior")
    class_def = class_defs.get(class_type, {})
    level = data.get("level", 1)
    base_hp = class_def.get("base_hp", 30)
    hp_per_level = class_def.get("hp_per_level", 6)
    base_mp = class_def.get("base_mp", 10)
    mp_per_level = class_def.get("mp_per_level", 4)
    max_hp = base_hp + hp_per_level * (level - 1)
    max_mp = base_mp + mp_per_level * (level - 1)
    data["max_hp"] = max_hp
    data["hp"] = max_hp
    data["max_mp"] = max_mp
    data["mp"] = max_mp

    npc = NPC.from_dict(data)
    return npc


def get_npc_template(template_id: str) -> dict | None:
    return _NPC_TEMPLATES.get(template_id)


def all_templates() -> dict[str, dict]:
    return _NPC_TEMPLATES
