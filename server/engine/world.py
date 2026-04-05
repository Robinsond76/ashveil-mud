"""
World map — rooms, encounters, zones.
Rooms are loaded from data/rooms/*.json at startup.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EncounterGroup:
    group: str                  # group identifier (e.g. "A", "wolves_small")
    members: list[str]          # list of NPC template IDs
    respawn_ticks: int          # ticks until this group respawns after defeat
    label: str = ""             # display label (used in arena)
    # Runtime state
    defeated: bool = False
    respawn_countdown: int = 0  # counts down from respawn_ticks after defeat

    def reset(self) -> None:
        self.defeated = False
        self.respawn_countdown = 0

    def mark_defeated(self) -> None:
        self.defeated = True
        self.respawn_countdown = self.respawn_ticks


@dataclass
class Room:
    id: str
    name: str
    description: str
    exits: dict[str, str]          # direction → room_id
    item_ids: list[str]             # items present on the floor
    encounter_groups: list[EncounterGroup]
    recruitable_npc_ids: list[str]  # NPC template IDs present for recruitment
    is_campfire: bool = False
    zone: str = ""
    # Environment
    room_type: str = "outdoor"     # "outdoor" | "indoor" | "underground"
    base_temp_f: float = 65.0      # base temperature in °F (modified by weather)

    def render(
        self,
        item_names: dict[str, str],      # item_id → display name
        npcs_present: list[str],          # flavor lines for recruitable NPCs
        encounter_summary: list[str],     # hostile group summaries
        env_footer: str = "",            # one-line environment status from WorldClock
    ) -> str:
        lines = [
            f"\n{'═' * 60}",
            f"  {self.name.upper()}",
            f"{'─' * 60}",
            f"  {self.description}",
        ]

        # Exits
        exit_parts = [f"{d.upper()}" for d in sorted(self.exits.keys())]
        lines.append(f"\n  Exits: {', '.join(exit_parts) if exit_parts else 'none'}")

        # Items on floor
        if self.item_ids:
            item_list = ", ".join(
                item_names.get(i, i) for i in self.item_ids
            )
            lines.append(f"  Items: {item_list}")

        # Recruitable NPCs
        for flavor in npcs_present:
            lines.append(f"\n  {flavor}")

        # Hostiles
        for line in encounter_summary:
            lines.append(f"\n  {line}")

        if self.is_campfire:
            lines.append("\n  [This is a campfire location — type CAMPFIRE to rest and manage your party]")

        if env_footer:
            lines.append(f"\n{env_footer}")

        lines.append(f"{'═' * 60}")
        return "\n".join(lines)


# ── World Map ─────────────────────────────────────────────────────────────────

class WorldMap:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}

    def load(self, data_dir: str) -> None:
        rooms_dir = os.path.join(data_dir, "rooms")
        for fname in os.listdir(rooms_dir):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(rooms_dir, fname), encoding="utf-8") as f:
                raw_list = json.load(f)
            for raw in raw_list:
                encounter_groups = []
                for eg in raw.get("encounter_ids", []):
                    encounter_groups.append(EncounterGroup(
                        group=eg["group"],
                        members=eg["members"],
                        respawn_ticks=eg.get("respawn_ticks", 20),
                        label=eg.get("label", ""),
                    ))
                room = Room(
                    id=raw["id"],
                    name=raw["name"],
                    description=raw["description"],
                    exits=raw.get("exits", {}),
                    item_ids=raw.get("item_ids", []),
                    encounter_groups=encounter_groups,
                    recruitable_npc_ids=raw.get("recruitable_npc_ids", []),
                    is_campfire=raw.get("is_campfire", False),
                    zone=raw.get("zone", ""),
                    room_type=raw.get("room_type", "outdoor"),
                    base_temp_f=float(raw.get("base_temp_f", 65.0)),
                )
                self._rooms[room.id] = room

    def get_room(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)

    def all_rooms(self) -> dict[str, Room]:
        return self._rooms

    def tick_respawns(self) -> None:
        """Call once per combat tick to advance respawn countdowns."""
        for room in self._rooms.values():
            for eg in room.encounter_groups:
                if eg.defeated and eg.respawn_countdown > 0:
                    eg.respawn_countdown -= 1
                    if eg.respawn_countdown <= 0:
                        eg.reset()

    def active_encounter_groups(self, room_id: str) -> list[EncounterGroup]:
        room = self.get_room(room_id)
        if not room:
            return []
        return [eg for eg in room.encounter_groups if not eg.defeated]
