"""Survival system — extracted from GameSession."""
from __future__ import annotations


def _box(title: str, lines: list[str]) -> str:
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


def party_survival_aggregate(player, party) -> tuple[float, float, float]:
    """Return (hunger_pct, thirst_pct, stamina_pct) averaged across the whole party."""
    members = [player] + list(party)
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


def apply_survival_penalties(player, party) -> tuple[float, bool]:
    """Return (combat_stat_multiplier, movement_blocked) based on party aggregate."""
    hunger_pct, thirst_pct, stamina_pct = party_survival_aggregate(player, party)
    multiplier = 1.0
    blocked = False

    if stamina_pct <= 0.10:
        blocked = True
    elif stamina_pct <= 0.30:
        multiplier *= 0.85

    ht_avg = (hunger_pct + thirst_pct) / 2.0
    if ht_avg < 0.20:
        multiplier *= 0.75
    elif ht_avg < 0.40:
        multiplier *= 0.90

    return multiplier, blocked


def drain_survival_tick(player, party, clock, temp_label: str) -> None:
    """Decrement hunger and thirst for every party member by one game-minute's drain."""
    members = [player] + list(party)
    for m in members:
        hunger_drain = m.hunger_drain_rate(clock)
        thirst_drain = m.thirst_drain_rate(temp_label, clock)
        m.hunger = max(0.0, m.hunger - hunger_drain)
        m.thirst = max(0.0, m.thirst - thirst_drain)


def sitting_stamina_tick(player, party, clock, is_sitting: bool) -> None:
    """Restore stamina per game-minute while sitting (out of combat)."""
    if not is_sitting:
        return
    members = [player] + list(party)
    for m in members:
        recovery = 1.5 if (clock and "energised" in m.get_active_buffs(clock)) else 1.0
        m.stamina = min(m.max_stamina, m.stamina + recovery)


async def do_survival_status(send_fn, player, party) -> None:
    h_pct, t_pct, s_pct = party_survival_aggregate(player, party)
    lines = [
        f"  Stamina : {s_pct * 100:.0f}%",
        f"  Hunger  : {h_pct * 100:.0f}%",
        f"  Thirst  : {t_pct * 100:.0f}%",
    ]
    await send_fn(_box("SURVIVAL STATUS", lines))


async def do_eat(send_fn, player, party, clock, args: str) -> None:
    from server.engine.items import get_item
    item_name = args.lower().strip()
    if not item_name:
        await send_fn("  Eat what? Usage: EAT <item>\n")
        return
    members = [player] + list(party)
    for carrier in members:
        for item_id in list(carrier.inventory):
            item = get_item(item_id)
            if not item:
                continue
            if item_name in item.name.lower() or item_name == item_id.lower():
                if item.effect_type != "food":
                    await send_fn(f"  You can't eat {item.name}.\n")
                    return
                carrier.inventory.remove(item_id)
                hunger_gain = item.effect_params.get("hunger", 0)
                thirst_gain = item.effect_params.get("thirst", 0)
                carrier.hunger = min(carrier.max_hunger, carrier.hunger + hunger_gain)
                carrier.thirst = min(carrier.max_thirst, carrier.thirst + thirst_gain)
                buff = item.effect_params.get("buff")
                if buff and clock:
                    duration = item.effect_params.get("buff_duration", 0)
                    for m in members:
                        m.apply_food_buff(buff, duration, clock)
                msg = f"  You eat the {item.name}."
                if hunger_gain:
                    msg += f" (Hunger +{hunger_gain})"
                if thirst_gain:
                    msg += f" (Thirst +{thirst_gain})"
                if buff:
                    msg += f" [{buff} buff applied!]"
                await send_fn(msg + "\n")
                return
    await send_fn(f"  You don't have '{item_name}' in your inventory.\n")


async def do_drink(send_fn, player, party, clock, args: str) -> None:
    from server.engine.items import get_item
    item_name = args.lower().strip()
    if not item_name:
        await send_fn("  Drink what? Usage: DRINK <item>\n")
        return
    members = [player] + list(party)
    for carrier in members:
        for item_id in list(carrier.inventory):
            item = get_item(item_id)
            if not item:
                continue
            if item_name in item.name.lower() or item_name == item_id.lower():
                if item.effect_type != "food":
                    await send_fn(f"  You can't drink {item.name}.\n")
                    return
                thirst_gain = item.effect_params.get("thirst", 0)
                if thirst_gain == 0:
                    await send_fn(f"  {item.name} doesn't restore thirst.\n")
                    return
                carrier.inventory.remove(item_id)
                hunger_gain = item.effect_params.get("hunger", 0)
                carrier.thirst = min(carrier.max_thirst, carrier.thirst + thirst_gain)
                if hunger_gain:
                    carrier.hunger = min(carrier.max_hunger, carrier.hunger + hunger_gain)
                buff = item.effect_params.get("buff")
                if buff and clock:
                    duration = item.effect_params.get("buff_duration", 0)
                    for m in members:
                        m.apply_food_buff(buff, duration, clock)
                msg = f"  You drink the {item.name}. (Thirst +{thirst_gain})"
                if buff:
                    msg += f" [{buff} buff applied!]"
                await send_fn(msg + "\n")
                return
    await send_fn(f"  You don't have '{item_name}' in your inventory.\n")


async def do_buffs(send_fn, player, party, clock) -> None:
    if not clock:
        await send_fn("  No active buffs.\n")
        return
    members = [player] + list(party)
    lines: list[str] = []
    for m in members:
        active = m.get_active_buffs(clock)
        for buff_name in active:
            remaining = m.active_buffs[buff_name] - clock.total_minutes
            lines.append(f"  {m.name}: {buff_name} ({remaining} min remaining)")
    if not lines:
        await send_fn("  No active buffs.\n")
    else:
        await send_fn(_box("ACTIVE BUFFS", lines))
