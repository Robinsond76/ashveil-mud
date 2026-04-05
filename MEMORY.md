# Ashveil MUD — Project Memory

## Phases Overview

| # | Phase | Status |
|---|-------|--------|
| 1 | World Clock & Environment | ✅ COMPLETED |
| 2 | Survival Stats | ✅ COMPLETED |
| 3 | Utility Skills & Mana Rework | ✅ COMPLETED |
| 4 | Food & Consumables | ✅ COMPLETED |
| 5 | Inventory & Weight Overhaul | ✅ COMPLETED |
| 6 | Horses & Mounts | ✅ COMPLETED |
| 7 | Wizard & Spell Overhaul | ✅ COMPLETED |
| 8 | Help System Overhaul | ✅ COMPLETED |
| 9 | Multiplayer Foundations | 🔲 NOT STARTED |

---

## Key Architecture Decisions (All Phases)

| Decision | Rationale |
|----------|-----------|
| JSON data files | Easy to edit content without touching code |
| Single asyncio event loop | Avoids threading complexity; WebSocket + combat + clock all cooperative |
| `WorldClock` subscribers | Decouples weather broadcast from session polling |
| Per-session `CombatSession` | Keeps combat isolated; multiplayer combat joins are future work |
| Darkvision on NPC not race | Simpler; monsters drive the rule, not player metadata |
| `room_type` over `is_outdoor` flag | Three-way distinction needed (outdoor/indoor/underground) |
| Effect flags on session | `_fortify_active`, `_bless_camp_active`, etc. as dynamic attrs — no dataclass field needed |
| Utility skills NOT in class skill_tree | Exist only in skill JSON files; unlocked via `unlocked_skills` dict |
| Stamina multiplier (mounts) | `ratio = min(1.0, horses/party_size)` → `multiplier = 1.0 - 0.60 * ratio` |
