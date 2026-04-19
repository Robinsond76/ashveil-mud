# Procedural Recruit Generation System

**Date:** 2026-04-18
**Status:** Planning — not yet implemented

## Problem

NPC recruits (Gareth, Lyria, Sable, etc.) are defined as static named characters in `recruitables.json`. Two bugs result from this:

1. **All stats are base 10** — `Character.from_dict()` reads flat keys (`"STR"`, `"DEX"`, etc.) from the root of the data dict, but the JSON nests them under `"stats": { ... }`. The fallback default is 10 for every stat, making every recruit identical stat-wise.
2. **No variety** — Every player who recruits Lyria gets the exact same Lyria with the exact same name, dialogue, and stats.

## Solution

Replace the static recruit system with a **procedural generation system** that creates unique recruits each time, with class-appropriate random stats, names, equipment, and dialogue.

---

## Design Decisions

### Stats
- **Class archetype-based**: Use `suggested_stats` from `classes.json` as the baseline
- **Conservative variation**: ±2 per stat per roll
- **Exceptional recruits**: 2% chance (1 in 50). Wider variation (±3) with positive bias (50% chance of `abs(roll)`)
- **Bounds**: All stats clamped to `[MIN_STAT, MAX_STAT]` = `[3, 18]`

### Names
- **First names**: Pre-approved lists per class (warrior names sound martial, mage names sound arcane, etc.)
- **Last titles**: Pre-approved epithets per class ("the Iron Guard", "the Frostweaver", etc.)
- **Generated on recruit creation**: A recruit's name is not revealed until the player talks to them

### TALK system
- **By number**: `TALK 1`, `TALK 2`, etc. (always works)
- **By class alias**: `TALK WARRIOR`, `TALK MAGE` (works only if exactly one of that class is present)
- **Before talking**: Recruits are shown as anonymous descriptions ("A broad-shouldered warrior in chainmail polishing a sword")
- **After talking**: The recruit introduces themselves with their generated name and class-appropriate dialogue

### Recruitment cost
- **Progressive**: `(level - 1)² × 5` gold
  - Level 2 = 5g
  - Level 3 = 20g
  - Level 4 = 45g
  - Level 5 = 80g
- Deducted from player gold on YES confirmation
- Displayed during the recruitment dialogue

### Equipment
- **Level-appropriate**: Gear is assigned based on class and level bracket
  - Level 1-2: Basic gear (rusty_sword, leather_armor, etc.)
  - Level 3-4: Improved gear (iron_sword, chainmail, etc.)
  - Level 5+: Quality gear (steel_sword, plate_armor, etc.)
- **Class-specific**: Mages get staves and cloth, thieves get daggers and leather, etc.

### Room configuration
- **New field**: `recruit_spawn_config` replaces `recruitable_npc_ids` in room JSON
- **Format**:
  ```json
  "recruit_spawn_config": {
    "pool": { "warrior": 2, "mage": 2, "thief": 1, "cleric": 1 },
    "level_range": [2, 3],
    "randomize_pool": true
  }
  ```
- **`randomize_pool: true`**: Slot counts are treated as weights; the actual spawn may vary (e.g., 3 warriors, 0 mages)
- **`randomize_pool: false`**: Exact class counts are enforced
- **Fallback**: Rooms with `recruitable_npc_ids` but no `recruit_spawn_config` will use the old system (backward compatible)

---

## Architecture

### New file: `server/engine/recruit_generator.py`

All procedural generation logic lives here.

```python
# Pseudocode outline

# ── Name Data ──────────────────────────────────────────────────────────────
FIRST_NAMES: dict[str, list[str]] = {
    "warrior": ["Gareth", "Brom", "Thorgar", "Kara", "Vlad", "Sigrid", ...],
    "mage":    ["Lyria", "Vex", "Thaddeus", "Orion", "Selene", "Maren", ...],
    "thief":   ["Sable", "Kael", "Raven", "Silas", "Nyx", "Zara", ...],
    "cleric":  ["Aldric", "Ophelia", "Beatrix", "Cedric", "Fiona", "Elara", ...],
}

LAST_TITLES: dict[str, list[str]] = {
    "warrior": ["the Iron Guard", "Shieldborn", "the Strong", "Axehammer", ...],
    "mage":    ["the Frostweaver", "the Ember Witch", "Arcane", "Spellweaver", ...],
    "thief":   ["the Shadow", "the Swift", "Nightwalker", "the Unseen", ...],
    "cleric":  ["the Devoted", "Lightbringer", "the Healer", "the Pious", ...],
}

# ── Room Descriptions (pre-talk, class-appropriate, detailed) ──────────────
ROOM_DESCRIPTIONS: dict[str, list[str]] = {
    "warrior": [
        "A broad-shouldered warrior in chainmail, polishing a well-worn sword.",
        "A scarred fighter leaning against the wall, checking the edge of a blade.",
        ...
    ],
    "mage": [
        "A robed figure surrounded by floating sparks, muttering to themselves.",
        "A slight figure tracing glowing runes in the air with practiced fingers.",
        ...
    ],
    "thief": [
        "A lean figure in dark leathers watching the room from the shadows.",
        "A hooded figure flipping a coin with unnerving precision.",
        ...
    ],
    "cleric": [
        "A serene figure in priestly robes tending to a small traveling shrine.",
        "A quiet healer with a mace at their hip, offering a reassuring nod.",
        ...
    ],
}

# ── Introduction Dialogue (post-talk, class-appropriate) ──────────────────
INTRO_DIALOGUES: dict[str, list[str]] = {
    "warrior": [
        "{name} sizes you up with a weathered eye.\n\"I've been looking for steady work. My sword arm's strong and I don't run from a fight.\"\n\"Want me to join your party? Recruitment fee: {cost} gold. (YES/NO)\"",
        ...
    ],
    "mage": [
        "{name} looks up from a worn grimoire, firelight dancing in their eyes.\n\"You seem capable enough. I need someone to stand between me and sharp objects while I work.\"\n\"Join your party? Fee: {cost} gold. (YES/NO)\"",
        ...
    ],
    "thief": [
        "You almost don't notice {name} until they speak.\n\"Didn't see me coming, did you? That's the point.\"\n\"I work for a fair split. You want my blades at your back? {cost} gold. (YES/NO)\"",
        ...
    ],
    "cleric": [
        "{name} clasps their hands and regards you with calm, searching eyes.\n\"The wounded follow you like a shadow. I have the gift of healing.\"\n\"If you would have me walk this road with you, I will not turn away. {cost} gold for my services. (YES/NO)\"",
        ...
    ],
}

# ── Equipment Templates ───────────────────────────────────────────────────
EQUIPMENT_BY_CLASS_AND_LEVEL: dict[str, dict[int, dict]] = {
    "warrior": {
        1: {"weapon": "rusty_sword", "body": "leather_armor"},
        2: {"weapon": "iron_sword", "body": "leather_armor", "offhand": "wooden_shield"},
        3: {"weapon": "iron_sword", "body": "chainmail", "head": "iron_helm", "offhand": "wooden_shield"},
        4: {"weapon": "iron_sword", "body": "chainmail", "head": "iron_helm", "offhand": "iron_shield"},
        5: {"weapon": "steel_sword", "body": "plate_armor", "head": "iron_helm", "offhand": "iron_shield", "hands": "iron_gauntlets", "feet": "iron_boots"},
    },
    "mage": { ... },
    "thief": { ... },
    "cleric": { ... },
}

# ── Skill Unlock Templates ────────────────────────────────────────────────
SKILLS_BY_CLASS_AND_LEVEL: dict[str, dict[int, list[str]]] = {
    "warrior": {
        1: ["power_strike"],
        2: ["power_strike"],
        3: ["power_strike", "taunt"],
        ...
    },
    ...
}

# ── Modifier Templates ────────────────────────────────────────────────────
MODIFIERS_BY_CLASS_AND_LEVEL: dict[str, dict[int, dict[str, int]]] = {
    "warrior": {
        1: {"sword_prof": 1},
        2: {"sword_prof": 1},
        3: {"sword_prof": 1, "shield_prof": 1},
        ...
    },
    ...
}

# ── Stat Generation ──────────────────────────────────────────────────────

EXCEPTIONAL_CHANCE = 0.02  # 1 in 50

def generate_stats(class_type: str, exceptional: bool = False) -> dict[str, int]:
    """Generate random stats appropriate for the given class."""
    from server.config import MIN_STAT, MAX_STAT
    base = CLASS_SUGGESTED_STATS[class_type]  # from classes.json
    variation = 3 if exceptional else 2

    stats = {}
    for stat, value in base.items():
        roll = random.randint(-variation, variation)
        if exceptional and random.random() < 0.5:
            roll = abs(roll)
        stats[stat] = max(MIN_STAT, min(MAX_STAT, value + roll))
    return stats


def roll_exceptional() -> bool:
    """2% chance of exceptional recruit."""
    return random.random() < EXCEPTIONAL_CHANCE


# ── Cost Calculation ─────────────────────────────────────────────────────

def get_recruitment_cost(level: int) -> int:
    """Progressive recruitment cost: (level - 1)^2 * 5"""
    return (level - 1) ** 2 * 5


# ── Name Generation ─────────────────────────────────────────────────────

def generate_name(class_type: str) -> str:
    """Generate a random first name + title for the class."""
    first = random.choice(FIRST_NAMES[class_type])
    title = random.choice(LAST_TITLES[class_type])
    return f"{first} {title}"


# ── Main Generator ───────────────────────────────────────────────────────

def generate_recruit(class_type: str, level: int, class_defs: dict) -> NPC:
    """Generate a complete procedural recruit."""
    exceptional = roll_exceptional()
    stats = generate_stats(class_type, exceptional)
    name = generate_name(class_type)
    equipment = EQUIPMENT_BY_CLASS_AND_LEVEL[class_type].get(level, ...)
    skills = SKILLS_BY_CLASS_AND_LEVEL[class_type].get(level, ...)
    modifiers = MODIFIERS_BY_CLASS_AND_LEVEL[class_type].get(level, ...)

    # Build NPC data dict similar to spawn_npc
    data = {
        "id": f"_recruit_{class_type}_{random_hex()}",
        "name": name,
        "class_type": class_type,
        "level": level,
        **stats,  # flat keys for Character.from_dict
        "equipment": equipment,
        "inventory": [...],
        "unlocked_skills": skills,
        "modifiers": modifiers,
        "is_recruitable": True,
        "recruit_dialogue": format_dialogue(class_type, name, cost),
        "room_flavor": format_room_description(class_type),
        "default_strategies": class_defs[class_type].get("default_strategies", []),
        # ... HP/MP computed from class_defs
    }
    return NPC.from_dict(data)


# ── Recruit Pool Manager ─────────────────────────────────────────────────

class RecruitPool:
    """Manages procedurally generated recruits for a room."""
    def __init__(self, room_id: str, config: dict, class_defs: dict):
        self.room_id = room_id
        self.recruits: list[NPC] = []
        self._generate(config, class_defs)

    def _generate(self, config, class_defs):
        """Fill the pool based on spawn config."""
        ...

    def get_by_index(self, index: int) -> NPC | None: ...
    def get_by_class(self, class_type: str) -> NPC | None: ...
    def remove(self, npc: NPC) -> None: ...
    def get_flavor_lines(self) -> list[str]: ...


# ── Room Description Renderer ────────────────────────────────────────────

def render_recruit_descriptions(pool: RecruitPool) -> list[str]:
    """Return numbered flavor lines for room display."""
    lines = []
    for i, npc in enumerate(pool.recruits, 1):
        desc = npc.room_flavor
        lines.append(f"  [{i}] {desc}")
    if lines:
        lines.append("\n  Type TALK <number> to approach someone, or EXAMINE <number> for details.")
    return lines
```

### Modified file: `server/engine/states/navigation.py`

**Changes:**

1. **`_do_look`**: Replace `recruitable_npc_ids` iteration with `RecruitPool` descriptions
   - Show numbered anonymous descriptions instead of named NPC flavor lines
   - Add hint text: "Type TALK <number> to approach someone"

2. **`_do_talk`**: Support both number and class alias
   - Parse `TALK 1` (by index) and `TALK WARRIOR` (by class, only if unique)
   - Look up recruit from `session._room_recruit_pools[room_id]`
   - Check if already in party
   - Check party size limit (4 companions)
   - Show class-appropriate intro dialogue with name reveal and cost
   - Store pending recruit in `session._pending_recruit` (NPC object + cost)

3. **`_do_examine`**: Support examining by number
   - `EXAMINE 1` shows class, level, and room description (not stats — those are revealed after recruitment)

4. **`_try_recruit_response`**: Handle YES/NO with gold check
   - Parse YES/NO response
   - On YES: Check if player has enough gold, deduct cost, add NPC to party
   - On NO: Decline message
   - Remove recruited NPC from the `RecruitPool`

5. **`_enter_room`**: Populate `RecruitPool` on room entry
   - If room has `recruit_spawn_config`, generate or retrieve pool for this room
   - Pool persists in `session._room_recruit_pools` so recruits don't change on re-entry

### Modified file: `server/engine/game.py`

**Changes:**

1. Add `_room_recruit_pools: dict[str, RecruitPool]` to `GameSession.__init__`
2. Remove backward-compatible `_do_talk` and `_try_recruit_response` methods (moved to navigation handler)

### Modified file: `server/engine/npc.py`

**Changes:**

1. **`spawn_npc()`**: Add support for procedural recruit generation
   - Keep existing template-based spawning for monsters
   - Remove the `stats` flattening that would be needed for old `recruitables.json` (no longer relevant)
2. Keep `default_strategies` → `strategies` key mapping (still needed for monsters)

### Modified file: `server/engine/world.py`

**Changes:**

1. **`Room` dataclass**: Add `recruit_spawn_config: dict | None = None` field
2. **`_load_rooms()`**: Parse `recruit_spawn_config` from room JSON (optional field)
3. Keep `recruitable_npc_ids` for backward compatibility

### Modified file: `server/data/rooms/testing_grounds.json`

**Changes:**

Update `test_recruit_hall` room:
```json
{
  "id": "test_recruit_hall",
  "name": "The Wanderers' Hall",
  "description": "A long hall where adventurers between jobs wait, trade stories, and look for work. Mismatched chairs and tables are scattered about. The guild board on the wall is covered in request notices.\n\nSeveral capable-looking individuals occupy the room.\n\nType TALK <number> to approach someone, or EXAMINE <number> for details.",
  "exits": { "west": "test_entrance" },
  "item_ids": [],
  "encounter_ids": [],
  "recruitable_npc_ids": [],
  "recruit_spawn_config": {
    "pool": { "warrior": 2, "mage": 2, "thief": 1, "cleric": 1 },
    "level_range": [2, 3],
    "randomize_pool": true
  },
  "is_campfire": false,
  "room_type": "indoor",
  "base_temp_f": 65.0,
  "zone": "testing_grounds"
}
```

### Deleted file: `server/data/npcs/recruitables.json`

Remove entirely. The procedural system replaces it.

The introduction dialogues from the old file will be preserved as class-appropriate templates in `recruit_generator.py` (see `INTRO_DIALOGUES` above).

---

## Data Flow

### Before (current, broken)
```
recruitables.json → load_npcs() → _NPC_TEMPLATES → spawn_npc() → NPC.from_dict()
                                                                     ↑ reads flat keys "STR", but data has nested "stats": {"STR": ...}
                                                                     → all stats default to 10
```

### After (procedural)
```
room JSON: recruit_spawn_config → RecruitPool.__init__() → generate_recruit()
                                                              ├── roll_exceptional() (2% chance)
                                                              ├── generate_stats(class, exceptional)
                                                              ├── generate_name(class)
                                                              ├── generate_equipment(class, level)
                                                              ├── generate_skills(class, level)
                                                              └── build NPC with flat stat keys → NPC.from_dict()
                                                                       ↑ now receives "STR": 16 directly
                                                                       → stats are correct

NavigationHandler._enter_room() → session._room_recruit_pools[room_id] = RecruitPool(...)
NavigationHandler._do_look()     → pool.get_flavor_lines()
NavigationHandler._do_talk()     → pool.get_by_index() or pool.get_by_class()
NavigationHandler._try_recruit_response() → check gold, deduct, add to party, remove from pool
```

---

## Test Plan

**New file:** `tests/test_procedural_recruits.py`

| # | Test | What it verifies |
|---|------|------------------|
| 1 | `test_stats_follow_archetype` | Warrior has STR > 12, Mage has INT > 14, etc. |
| 2 | `test_stats_randomized` | 10 warriors don't all have identical stats |
| 3 | `test_stats_within_bounds` | All stats in [MIN_STAT, MAX_STAT] |
| 4 | `test_exceptional_recruit_rare` | ~2% of 1000 recruits are exceptional |
| 5 | `test_exceptional_stats_higher` | Exceptional recruits have higher total stats on average |
| 6 | `test_equipment_by_level` | Lv3+ warriors have better gear than Lv2 |
| 7 | `test_cost_progressive` | Lv2=5g, Lv3=20g, Lv4=45g, Lv5=80g |
| 8 | `test_name_generation_unique` | Names are randomly selected from class lists |
| 9 | `test_recruit_pool_persistence` | Same room, same recruits across multiple visits |
| 10 | `test_talk_by_index` | TALK 1/2/3 resolves to correct recruit |
| 11 | `test_talk_by_class_unique` | TALK WARRIOR works when only one warrior present |
| 12 | `test_talk_by_class_ambiguous` | TALK WARRIOR fails when two warriors present |
| 13 | `test_gold_deducted_on_recruit` | Player gold decreases by recruit cost |
| 14 | `test_gold_insufficient` | Player can't recruit if they lack gold |
| 15 | `test_recruit_removed_from_pool` | Recruited NPC no longer appears in room |

---

## Existing Tests Impact

- **All 613 existing tests must continue to pass.** The procedural recruit system is additive; it doesn't change monster spawning, combat, or character mechanics.
- **`test_caster_spell_preference.py`**: Uses `spawn_npc()` for monsters (goblin_shaman, dungeon_mage). These still use template-based spawning, so they're unaffected.
- **Any test that references `recruitables.json` template IDs** (like `recruit_gareth`, `recruit_lyria`): These tests need updating to use the new procedural system or be removed if they tested static recruit data.

---

## Implementation Order

1. Create `server/engine/recruit_generator.py` with all generation logic (stats, names, equipment, skills, modifiers, descriptions, dialogues, cost)
2. Create `tests/test_procedural_recruits.py` with stat/generation tests (tests 1-9)
3. Update `server/engine/world.py` to parse `recruit_spawn_config`
4. Update `server/engine/game.py` to add `_room_recruit_pools` to session
5. Update `server/engine/states/navigation.py` with new TALK/LOOK/EXAMINE logic
6. Create integration tests (tests 10-15)
7. Update `server/data/rooms/testing_grounds.json` with spawn config
8. Delete `server/data/npcs/recruitables.json`
9. Run all 613+ tests and verify nothing breaks