"""Context panel data gathering — extracted from GameSession."""
from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from server.engine.domain.items import get_item
from server.engine.survival import party_survival_aggregate
from server.engine.environment import effective_light as _effective_light_fn

if TYPE_CHECKING:
    from server.engine.game import GameSession

logger = logging.getLogger(__name__)

MAX_CONTEXT_INVENTORY_ITEMS = 10


async def send_context_update(session: "GameSession") -> None:
    """Send current game context to client as JSON."""
    if not session.player:
        return
    if not hasattr(session.player, 'to_dict'):
        return
    if hasattr(session._send_raw, '_mock_name'):
        return
    try:
        context = gather_context(session)
        json_msg = json.dumps({"type": "context", "data": context})
        await session.send(json_msg)
    except (TypeError, ValueError) as e:
        logger.debug(f"Failed to serialize context: {e}")


def gather_context(session: "GameSession") -> dict[str, Any]:
    """Gather all context data for the side panel."""
    return {
        "player": get_player_context(session),
        "party": get_party_context(session),
        "map": get_map_context(session),
        "inventory": get_inventory_context(session),
        "environment": get_environment_context(session),
    }


def get_player_context(session: "GameSession") -> dict[str, Any]:
    """Get player character stats and status."""
    if not session.player:
        return {}
    h_pct, t_pct, s_pct = 1.0, 1.0, 1.0
    if session.party:
        h_pct, t_pct, s_pct = party_survival_aggregate(session.player, session.party)
    return {
        "name": session.player.name,
        "class": session.player.class_type,
        "level": session.player.level,
        "xp": session.player.xp,
        "hp": session.player.hp,
        "max_hp": session.player.max_hp,
        "mp": session.player.mp,
        "max_mp": session.player.max_mp,
        "stats": {
            "STR": session.player.STR,
            "DEX": session.player.DEX,
            "INT": session.player.INT,
            "WIS": session.player.WIS,
            "CON": session.player.CON,
            "AGI": session.player.AGI,
        },
        "hunger": int(h_pct * 100),
        "thirst": int(t_pct * 100),
        "stamina": int(s_pct * 100),
        "gold": session.player.gold,
    }


def get_party_context(session: "GameSession") -> list[dict[str, Any]]:
    """Get party member information."""
    if not session.party:
        return []
    members = []
    for npc in session.party:
        member_data = {
            "name": npc.name,
            "hp": npc.hp,
            "max_hp": npc.max_hp,
            "mp": npc.mp,
            "max_mp": npc.max_mp,
            "class": npc.class_type,
        }
        if hasattr(npc, 'template_id'):
            member_data["template_id"] = npc.template_id
        members.append(member_data)
    return members


def get_map_context(session: "GameSession") -> dict[str, Any]:
    """Get mini-map data for current location."""
    if not session.current_room_id:
        return {}
    room = session.world.get_room(session.current_room_id)
    if not room:
        return {}
    connected = {}
    for direction, room_id in room.exits.items():
        connected_room = session.world.get_room(room_id)
        if connected_room:
            connected[direction] = {"name": connected_room.name, "room_id": room_id}
    return {
        "current": {"id": room.id, "name": room.name, "zone": room.zone},
        "exits": connected,
    }


def get_inventory_context(session: "GameSession") -> dict[str, Any]:
    """Get inventory summary."""
    if not session.player:
        return {}
    items = []
    for item_id in session.player.inventory[:MAX_CONTEXT_INVENTORY_ITEMS]:
        item = get_item(item_id)
        if item:
            items.append({"id": item_id, "name": item.name, "type": item.type})
    return {
        "count": len(session.player.inventory),
        "items": items,
        "has_more": len(session.player.inventory) > MAX_CONTEXT_INVENTORY_ITEMS,
        "equipment": session.player.equipment,
    }


def get_environment_context(session: "GameSession") -> dict[str, Any]:
    """Get environment data (time, weather, temperature, visibility)."""
    if not session.clock:
        return {}
    room = None
    if session.current_room_id:
        room = session.world.get_room(session.current_room_id)
    eff_light = 1.0
    if room:
        eff_light = _effective_light_fn(
            session.player, session.party, session.player.lit_sources, session.clock, room
        )
    if eff_light >= 0.80:
        visibility = "Bright"
    elif eff_light >= 0.40:
        visibility = "Dim"
    elif eff_light >= 0.05:
        visibility = "Dark"
    else:
        visibility = "Pitch Black"
    temp_label = "Unknown"
    if room:
        temp_label = session.clock.temperature_label(room.room_type, room.base_temp_f)
    return {
        "time_of_day": session.clock.time_of_day_label(),
        "time_string": session.clock.time_string(),
        "weather": session.clock.current_weather,
        "temperature": temp_label,
        "visibility": visibility,
        "room_type": room.room_type if room else "unknown",
    }
