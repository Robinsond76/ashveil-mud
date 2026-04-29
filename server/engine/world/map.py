"""
World map — rooms, encounters, zones.
Rooms are loaded from data/rooms/*.json at startup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


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

    def render_quick(
        self,
        item_names: dict[str, str],
        npcs_present: list[str],
        encounter_summary: list[str],
        other_players: list[str],
    ) -> str:
        """
        Compact room summary with color-coded highlights.
        
        Colors:
          - Red (\\x1b[31m): Enemies/hostiles
          - Green (\\x1b[32m): Items
          - Yellow (\\x1b[33m): Recruitable NPCs
          - Blue (\\x1b[34m): Other players
          - Reset (\\x1b[0m): Return to default
        """
        width = 60
        exit_parts = [d.upper() for d in sorted(self.exits.keys())]
        exit_str = ", ".join(exit_parts) if exit_parts else "none"
        name_padded = self.name.upper().ljust(40)

        lines = [
            f"\n{'═' * width}",
            f"  {name_padded}[Exits: {exit_str}]",
            f"{'─' * width}",
        ]

        if self.item_ids:
            item_list = ", ".join(
                f"\x1b[32m{item_names.get(i, i)}\x1b[0m" for i in self.item_ids
            )
            lines.append(f"  Items: {item_list}")

        if encounter_summary:
            hostile_text = " | ".join(encounter_summary)
            lines.append(f"  \x1b[31mHostiles: {hostile_text}\x1b[0m")

        for flavor in npcs_present:
            lines.append(f"  \x1b[33m{flavor}\x1b[0m")

        if other_players:
            players_text = ", ".join(f"\x1b[34m{p}\x1b[0m" for p in other_players)
            lines.append(f"  Also here: {players_text}")

        if not any([self.item_ids, encounter_summary, npcs_present, other_players]):
            lines.append("  (nothing of note)")

        lines.append(f"{'═' * width}")
        return "\n".join(lines)


# ── World Map ─────────────────────────────────────────────────────────────────

class WorldMap:
    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self.room_occupants: dict[str, list[str]] = {}
        self._occupants_lock: asyncio.Lock = asyncio.Lock()

    async def enter_room(self, player_name: str, room_id: str) -> None:
        if not hasattr(self, '_occupants_lock'):
            self._occupants_lock = asyncio.Lock()
        if not hasattr(self, 'room_occupants'):
            self.room_occupants = {}
        async with self._occupants_lock:
            if room_id not in self.room_occupants:
                self.room_occupants[room_id] = []
            if player_name not in self.room_occupants[room_id]:
                self.room_occupants[room_id].append(player_name)

    async def leave_room(self, player_name: str, room_id: str) -> None:
        if not hasattr(self, '_occupants_lock'):
            self._occupants_lock = asyncio.Lock()
        if not hasattr(self, 'room_occupants'):
            return
        async with self._occupants_lock:
            if room_id in self.room_occupants:
                try:
                    self.room_occupants[room_id].remove(player_name)
                except ValueError:
                    pass

    async def players_in_room(self, room_id: str) -> list[str]:
        if not hasattr(self, '_occupants_lock'):
            self._occupants_lock = asyncio.Lock()
        if not hasattr(self, 'room_occupants'):
            return []
        async with self._occupants_lock:
            return list(self.room_occupants.get(room_id, []))

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

        # Validate referential integrity after all rooms are loaded
        raw_for_validation = {
            r.id: {"exits": r.exits} for r in self._rooms.values()
        }
        errors = validate_room_data(raw_for_validation)
        for err in errors:
            logger.warning("Room validation: %s", err)

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


def validate_room_data(rooms_dict: dict) -> list[str]:
    """Validate room data for referential integrity.

    Checks:
    - All room IDs are non-empty strings
    - All exit targets point to existing room IDs

    Parameters:
        rooms_dict: dict[str, dict] — raw room data keyed by room_id

    Returns:
        list[str] — list of error messages (empty if valid)
    """
    errors: list[str] = []
    all_room_ids = set(rooms_dict.keys())

    for room_id, room_data in rooms_dict.items():
        if not room_id:
            errors.append("Found room with empty ID")
            continue

        exits = room_data.get("exits", {})
        for direction, target_id in exits.items():
            if target_id not in all_room_ids:
                errors.append(
                    f"Room '{room_id}' exit '{direction}' points to "
                    f"non-existent room '{target_id}'"
                )

    return errors
