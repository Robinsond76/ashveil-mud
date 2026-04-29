"""Environment display commands — extracted from GameSession."""
from __future__ import annotations

import asyncio

from server.engine.domain.items import get_item
from server.engine.world.clock import light_label
from server.engine.display.formatting import box as _box


def carried_light(player, party, lit_sources: dict, clock, send_fn) -> float:
    """Return the highest light level from all lit party light sources.
    Expired sources are removed from lit_sources dict in place and
    a fire-and-forget notification is queued via send_fn.
    """
    if not lit_sources or not clock:
        return 0.0
    now = clock.total_minutes
    expired = [k for k, exp in lit_sources.items() if exp <= now]
    for k in expired:
        del lit_sources[k]
        item = get_item(k)
        iname = item.name if item else k
        asyncio.get_event_loop().create_task(
            send_fn(f"\n  Your {iname} has burned out.\n")
        )
    if not lit_sources:
        return 0.0
    all_inv: list[str] = list(player.inventory) if player else []
    for npc in party:
        all_inv.extend(npc.inventory)
    best = 0.0
    for item_id in list(lit_sources):
        if item_id in all_inv:
            item = get_item(item_id)
            if item:
                best = max(best, item.effect_params.get("light_level", 0.0))
    return best


def effective_light(player, party, lit_sources: dict, clock, room) -> float:
    """Effective light level [0,1] in the current room (read-only; no expiry)."""
    if not clock:
        return 1.0
    if not room:
        return 1.0
    # Read-only version: don't expire here to avoid side effects in property access
    if not lit_sources:
        carried = 0.0
    else:
        now = clock.total_minutes
        all_inv: list[str] = list(player.inventory) if player else []
        for npc in party:
            all_inv.extend(npc.inventory)
        carried = 0.0
        for item_id, expiry in lit_sources.items():
            if expiry > now and item_id in all_inv:
                item = get_item(item_id)
                if item:
                    carried = max(carried, item.effect_params.get("light_level", 0.0))
    return clock.effective_light(room.room_type, carried)


async def do_time(send_fn, clock) -> None:
    if not clock:
        await send_fn("  (No world clock running.)\n")
        return
    c = clock
    await send_fn(
        _box("TIME", [
            f"  It is {c.time_of_day_label()} ({c.time_string()}).",
            f"  Day {c.game_day + 1} — {c.moon_phase_name.capitalize()}.",
        ])
    )


async def do_weather(send_fn, clock, room) -> None:
    if not clock:
        await send_fn("  (No world clock running.)\n")
        return
    if room and room.room_type == "underground":
        await send_fn("  Deep underground, the weather of the surface world cannot reach you.\n")
        return
    c = clock
    temp_label = c.temperature_label(
        room.room_type if room else "outdoor",
        room.base_temp_f if room else 65.0,
    )
    await send_fn(
        _box("WEATHER", [
            f"  Weather  : {c.current_weather.capitalize()}",
            f"  Temp     : {temp_label}",
        ])
    )


async def do_light(send_fn, clock, room, lit_sources: dict, carried_fn) -> None:
    if not clock:
        await send_fn("  (No world clock running.)\n")
        return
    rt = room.room_type if room else "outdoor"
    carried = carried_fn()
    eff = clock.effective_light(rt, carried)
    ll = light_label(eff)
    lines = [f"  Lighting : {ll}"]
    if lit_sources:
        now = clock.total_minutes
        for item_id, expiry in lit_sources.items():
            item = get_item(item_id)
            iname = item.name if item else item_id
            remaining = max(0, expiry - now)
            if item and item.effect_params.get("fuel_minutes", 0) < 0:
                lines.append(f"  Source   : {iname} (burning)")
            elif remaining > 0:
                lines.append(f"  Source   : {iname} ({remaining} min remaining)")
            else:
                lines.append(f"  Source   : {iname} (burned out)")
    else:
        lines.append("  Source   : none (no lit light sources)")
    await send_fn(_box("LIGHT", lines))


async def do_envdetails(send_fn, clock, room, carried_fn) -> None:
    if not clock:
        await send_fn("  (No world clock running.)\n")
        return
    c = clock
    rt = room.room_type if room else "outdoor"
    bt = room.base_temp_f if room else 65.0
    carried = carried_fn()
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
    await send_fn(_box("ENVIRONMENT DETAILS", lines))


async def do_light_source(send_fn, player, party, lit_sources: dict, clock, args: str, extinguish: bool) -> None:
    """Light or extinguish a carried light source (torch, lantern)."""
    if not clock:
        await send_fn("  (No world clock running.)\n")
        return
    item_name = args.lower().strip()
    if not item_name:
        verb = "extinguish" if extinguish else "light"
        await send_fn(f"  Usage: {verb.upper()} <item name>\n")
        return

    all_inv: list[tuple[str, str]] = []
    if player:
        for iid in player.inventory:
            all_inv.append((player.name, iid))
    for npc in party:
        for iid in npc.inventory:
            all_inv.append((npc.name, iid))

    for owner, item_id in all_inv:
        item = get_item(item_id)
        if not item or item_name not in item.name.lower():
            continue
        if item.effect_type != "light_source":
            await send_fn(f"  {item.name} is not a light source.\n")
            return
        if extinguish:
            if item_id in lit_sources:
                del lit_sources[item_id]
                await send_fn(f"  You extinguish the {item.name}.\n")
            else:
                await send_fn(f"  {item.name} is not lit.\n")
            return
        else:
            if item_id in lit_sources:
                await send_fn(f"  {item.name} is already lit.\n")
                return
            fuel_minutes = item.effect_params.get("fuel_minutes", 0)
            if fuel_minutes < 0:
                oil_ids = [oid for _, oid in all_inv if oid == "oil_flask"]
                if not oil_ids:
                    await send_fn(
                        f"  The {item.name} is empty. You need an Oil Flask to fill it.\n"
                    )
                    return
                oil_id = oil_ids[0]
                if player and oil_id in player.inventory:
                    player.inventory.remove(oil_id)
                else:
                    for npc in party:
                        if oil_id in npc.inventory:
                            npc.inventory.remove(oil_id)
                            break
                fuel_minutes = 90
                await send_fn(f"  You fill and light the {item.name} with oil.\n")
            else:
                await send_fn(f"  You light the {item.name}.\n")
            expiry = clock.total_minutes + fuel_minutes
            lit_sources[item_id] = expiry
            return
    await send_fn(f"  No light source named '{args}' found in party inventory.\n")
