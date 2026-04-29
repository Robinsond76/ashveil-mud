"""Campfire commands — extracted from GameSession."""
from __future__ import annotations

from server.engine.combat.grid import FRONT_ROW, BACK_ROW


def _box(title: str, lines: list[str]) -> str:
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


async def do_formation(send_fn, player, party, args: str) -> None:
    """Show or change party battle formation."""
    all_members = [player] + list(party)

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
        await send_fn(_render_formation())
        return

    parts = args.split()
    if len(parts) < 2:
        await send_fn("  Usage: FORMATION <name> FRONT|BACK <1-3>  or  FORMATION <name> AUTO\n")
        return

    ROW_KEYWORDS = {"FRONT", "BACK", "AUTO"}
    row_kw_idx = None
    for i, p in enumerate(parts):
        if p.upper() in ROW_KEYWORDS:
            row_kw_idx = i
            break
    if row_kw_idx is None or row_kw_idx == 0:
        await send_fn("  Usage: FORMATION <name> FRONT|BACK <1-3>\n")
        return

    name_str = " ".join(parts[:row_kw_idx]).lower()
    row_kw = parts[row_kw_idx].upper()

    target = None
    if name_str in (player.name.lower(), "me", "player"):
        target = player
    else:
        for npc in party:
            if name_str in npc.name.lower():
                target = npc
                break

    if target is None:
        await send_fn(f"  '{name_str}' not found in your party.\n")
        return

    if row_kw == "AUTO":
        target.grid_row = -1
        target.grid_col = -1
        await send_fn(f"  {target.name}'s position reset to auto-assign.\n")
        await send_fn(_render_formation())
        return

    if row_kw_idx + 1 >= len(parts):
        await send_fn(f"  Specify a column (1-3): FORMATION {target.name} {row_kw} <1-3>\n")
        return
    try:
        col_1based = int(parts[row_kw_idx + 1])
    except ValueError:
        await send_fn("  Column must be a number 1-3.\n")
        return
    if col_1based not in (1, 2, 3):
        await send_fn("  Column must be 1, 2, or 3.\n")
        return

    new_row = FRONT_ROW if row_kw == "FRONT" else BACK_ROW
    new_col = col_1based - 1

    for m in all_members:
        if m is target:
            continue
        if m.grid_row == new_row and m.grid_col == new_col:
            await send_fn(
                f"  {m.name} already occupies {row_kw} column {col_1based}. "
                f"Move them first or choose another cell.\n"
            )
            return

    target.grid_row = new_row
    target.grid_col = new_col
    row_label = "FRONT" if new_row == FRONT_ROW else "BACK"
    await send_fn(
        f"  {target.name} placed in {row_label} row, column {col_1based}.\n"
    )
    await send_fn(_render_formation())


async def do_manage(send_fn, player, party, name: str, get_skill_fn, list_strategies_fn):
    """Enter strategy editing for a party member.
    Returns the target Character/NPC to manage, or None if not found.
    Caller is responsible for setting state to STRATEGY.
    """
    nl = name.lower().strip()
    target = None

    if nl == player.name.lower() or nl == "player" or nl == "me":
        target = player
    else:
        for npc in party:
            if nl in npc.name.lower():
                target = npc
                break

    if target is None:
        await send_fn(
            f"  '{name}' not found. Try your own name or a companion's name.\n"
        )
        return None

    if target.unlocked_skills:
        skill_lines = ["  Unlocked skills:"]
        for sid in target.unlocked_skills:
            sk = get_skill_fn(sid)
            if sk:
                skill_lines.append(f"    {sid:<20} — {sk.name}  (MP:{sk.mp_cost})")
    else:
        skill_lines = ["  No skills unlocked yet."]

    await send_fn(
        _box(
            f"Strategy Editor: {target.name}  [{target.class_type.capitalize()}]",
            [
                *skill_lines,
                "",
                list_strategies_fn(target),
                "",
                "  Commands: SKILLS | STRATEGY LIST | STRATEGY ADD | STRATEGY REMOVE | DONE",
            ],
        )
    )
    return target
