# GameSession Decomposition — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose the 1,667-line `GameSession` class into state-specific handlers, reducing game.py to ~250 lines of coordinator code.

**Architecture:** Stateless handler singletons using O(1) command dict dispatch. Each handler encapsulates one game state (CONNECT, CREATION, NAVIGATION, CAMPFIRE, STRATEGY, COMBAT). State-specific data stored in TypedDict contexts.

**Tech Stack:** Python 3.11+, FastAPI WebSocket, pytest, TypedDict for state contexts.

---

## File Structure

**New Files (7):**
- `server/engine/states/__init__.py` — State enum, HANDLER_REGISTRY
- `server/engine/states/base.py` — StateHandler protocol
- `server/engine/states/contexts.py` — TypedDict state contexts
- `server/engine/states/connect.py` — Login/authentication handler (~40 lines)
- `server/engine/states/creation.py` — Character creation wizard (~120 lines)
- `server/engine/states/navigation.py` — Exploration handler (~350 lines)
- `server/engine/states/campfire.py` — Rest & party management (~100 lines)
- `server/engine/states/strategy.py` — Strategy editor (~80 lines)
- `server/engine/states/combat.py` — Combat orchestration (~140 lines)

**Modified Files (2):**
- `server/engine/game.py` — Reduced from 1,667 to ~250 lines
- `tests/` — Existing tests should continue passing (behavior unchanged)

---

## Phase 1: Foundation — State Infrastructure

### Task 1: Create State Enum and Handler Registry

**Files:**
- Create: `server/engine/states/__init__.py`

- [ ] **Step 1: Write the enum and registry**

```python
"""State management for Ashveil MUD.

This module provides the State enum and handler registry for the
decomposed GameSession architecture. Handlers are singletons for
memory efficiency and thread safety.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.engine.states.base import StateHandler


class State(Enum):
    """Game session states."""

    CONNECT = "connect"
    CREATION = "creation"
    NAVIGATION = "navigation"
    CAMPFIRE = "campfire"
    STRATEGY = "strategy"
    COMBAT = "combat"


def _get_handlers() -> dict[State, StateHandler]:
    """Lazy-load handlers to avoid circular imports."""
    from server.engine.states.connect import ConnectHandler
    from server.engine.states.creation import CreationHandler
    from server.engine.states.navigation import NavigationHandler
    from server.engine.states.campfire import CampfireHandler
    from server.engine.states.strategy import StrategyHandler
    from server.engine.states.combat import CombatHandler

    return {
        State.CONNECT: ConnectHandler(),
        State.CREATION: CreationHandler(),
        State.NAVIGATION: NavigationHandler(),
        State.CAMPFIRE: CampfireHandler(),
        State.STRATEGY: StrategyHandler(),
        State.COMBAT: CombatHandler(),
    }


# Singleton handlers - loaded once on first access
HANDLER_REGISTRY: dict[State, StateHandler] = _get_handlers()
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from server.engine.states import State, HANDLER_REGISTRY; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/__init__.py
git commit -m "feat(states): add State enum and HANDLER_REGISTRY"
```

---

### Task 2: Create StateHandler Protocol

**Files:**
- Create: `server/engine/states/base.py`

- [ ] **Step 1: Write the protocol**

```python
"""Base protocol for state handlers.

State handlers encapsulate all behavior for a specific game state.
They are stateless singletons - all mutable state lives in GameSession.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

if TYPE_CHECKING:
    from server.engine.game import GameSession


@runtime_checkable
class StateHandler(Protocol):
    """Handler for a specific game state.

    Implementations must be stateless - all data lives in the session.
    """

    async def on_enter(self, session: GameSession) -> None:
        """Called when transitioning INTO this state.

        Use this to set up subscriptions, display initial output, etc.
        """
        ...

    async def on_exit(self, session: GameSession) -> None:
        """Called when transitioning OUT of this state.

        Use this to clean up subscriptions, save state, etc.
        """
        ...

    async def handle(self, session: GameSession, text: str) -> None:
        """Process input text for this state.

        This is the main entry point for player commands while in this state.

        Args:
            session: The game session (provides player, world, send, etc.)
            text: Raw input text from the player
        """
        ...
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from server.engine.states.base import StateHandler; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/base.py
git commit -m "feat(states): add StateHandler protocol"
```

---

### Task 3: Create State Context TypedDicts

**Files:**
- Create: `server/engine/states/contexts.py`

- [ ] **Step 1: Write the context definitions**

```python
"""State-specific context data structures.

Each state can store transient data in session._state_data using these
TypedDict definitions for type safety and documentation.
"""
from __future__ import annotations

from typing import TypedDict, NotRequired
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.engine.character import Character
    from server.engine.npc import NPC


class ConnectContext(TypedDict):
    """No additional context needed for connect state."""

    pass


class CreationContext(TypedDict):
    """Context for character creation wizard.

    Tracks the multi-step creation process: class selection -> stat assignment -> strategy setup.
    """

    step: str  # "class" | "stats" | "strategy"
    pending_name: str
    pending_class: NotRequired[str]
    pending_stats: NotRequired[dict[str, int]]
    stat_points_remaining: NotRequired[int]


class StrategyContext(TypedDict):
    """Context for strategy editor.

    Used in both creation (setting up initial strategies) and campfire (editing companion strategies).
    """

    target: Character | NPC  # Who we're editing strategies for
    context: str  # "creation" | "campfire"


class CombatContext(TypedDict):
    """Context for combat state."""

    encounter_group: object  # EncounterGroup from world.py
    arena_group: str | None  # For arena fights: "A", "B", "C", "D"


# Union type for session._state_data field
StateContext = ConnectContext | CreationContext | StrategyContext | CombatContext | None
```

- [ ] **Step 2: Verify no syntax errors**

Run: `python -c "from server.engine.states.contexts import StateContext; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/contexts.py
git commit -m "feat(states): add StateContext TypedDicts"
```

---

## Phase 2: Core State Handlers

### Task 4: Create ConnectHandler

**Files:**
- Create: `server/engine/states/connect.py`
- Test: Run existing tests after implementation

- [ ] **Step 1: Write ConnectHandler**

```python
"""Connect state handler — login and authentication."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.persistence import load_player
from server.engine.states import State

if TYPE_CHECKING:
    from server.engine.game import GameSession


class ConnectHandler:
    """Handles player login and account creation flow."""

    async def on_enter(self, session: GameSession) -> None:
        """Display welcome message and prompt for name."""
        await session.send(
            "\n" + "═" * 60 + "\n"
            "  Welcome to ASHVEIL MUD\n"
            "  A text-based fantasy world\n" +
            "═" * 60 + "\n"
            "\nEnter your character name (new or existing):\n> "
        )

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed for connect state."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process login name."""
        name = text.strip()

        if name.upper() in ("HELP", "?"):
            await session._send_help("")
            return

        if not name.isalpha() or len(name) < 2 or len(name) > 20:
            await session.send("  Name must be 2–20 letters only. Try again:\n> ")
            return

        # Try to load existing save
        save = load_player(name)
        if save:
            await session._load_save(save)
            session._subscribe_clock()
            await session.send(f"\n  Welcome back, {session.player.name}!\n")
            await session.transition_to(State.NAVIGATION)
        else:
            # New character - go to creation wizard
            await session.transition_to(
                State.CREATION,
                step="class",
                pending_name=name
            )
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_phase02_commands.py -v -k "connect or login" 2>&1 | head -50`
Expected: Tests pass (existing connection logic still works)

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/connect.py
git commit -m "feat(states): add ConnectHandler"
```

---

### Task 5: Create CreationHandler

**Files:**
- Create: `server/engine/states/creation.py`
- Modify: `server/engine/game.py:450-511` (will extract `_finalize_character_stats` logic)

- [ ] **Step 1: Write CreationHandler**

```python
"""Character creation wizard state handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import MIN_STAT, MAX_STAT, STAT_POINT_BUY_BUDGET
from server.engine.character import Character
from server.engine.npc import NPC, spawn_npc
from server.engine.states import State
from server.engine.strategy import list_strategies
from server.engine.skills import get_skill

if TYPE_CHECKING:
    from server.engine.game import GameSession


def _box(title: str, lines: list[str]) -> str:
    """Format a boxed display."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class CreationHandler:
    """Multi-step character creation: class -> stats -> strategy -> done."""

    async def on_enter(self, session: GameSession) -> None:
        """Display class selection prompt."""
        await self._send_class_prompt(session)

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Route to appropriate step handler."""
        upper = text.strip().upper()

        if upper in ("HELP", "?"):
            await session._send_help("")
            return

        ctx = session._state_data
        step = ctx.get("step", "class")

        if step == "class":
            await self._handle_class_step(session, text)
        elif step == "stats":
            await self._handle_stats_step(session, text)
        elif step == "strategy":
            # Delegate to StrategyHandler but with creation context
            from server.engine.states.strategy import StrategyHandler
            handler = StrategyHandler()
            await handler.handle(session, text)

    async def _send_class_prompt(self, session: GameSession) -> None:
        """Display class selection options."""
        ctx = session._state_data
        lines = [f"  Creating character: {ctx['pending_name']}", ""]

        for key, cd in session.class_defs.items():
            lines.append(f"  {key.upper():<10} — {cd['description']}")
        lines.append("")
        lines.append("  Type WARRIOR, MAGE, THIEF, or CLERIC:")

        await session.send(_box("CHARACTER CREATION — Choose Class", lines[1:]))

    async def _handle_class_step(self, session: GameSession, text: str) -> None:
        """Process class selection."""
        cls = text.strip().lower()

        if cls not in session.class_defs:
            await session.send(f"  Unknown class '{text}'. Choose: warrior, mage, thief, cleric\n> ")
            return

        # Initialize creation context for stats step
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]
        ctx = session._state_data
        ctx["pending_class"] = cls
        ctx["step"] = "stats"
        ctx["pending_stats"] = {s: MIN_STAT for s in stats_list}
        ctx["stat_points_remaining"] = STAT_POINT_BUY_BUDGET

        await self._send_stat_prompt(session)

    async def _send_stat_prompt(self, session: GameSession) -> None:
        """Display stat assignment UI."""
        ctx = session._state_data
        cd = session.class_defs[ctx["pending_class"]]
        suggested = cd["suggested_stats"]
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]

        spent = sum(ctx["pending_stats"].values()) - MIN_STAT * 6
        remaining = STAT_POINT_BUY_BUDGET - spent

        lines = [
            f"  Class: {cd['display_name']}",
            f"  Points remaining: {remaining}  (budget: {STAT_POINT_BUY_BUDGET})",
            f"  Stats range: {MIN_STAT}–{MAX_STAT}",
            "",
            "  Current / Suggested:",
        ]
        for stat in stats_list:
            cur = ctx["pending_stats"].get(stat, MIN_STAT)
            sug = suggested.get(stat, MIN_STAT)
            lines.append(f"    {stat}: {cur:<4}  (suggested {sug})")

        lines += [
            "",
            "  Commands: SET STR 15 | SUGGEST | STATS | DONE | HELP",
        ]

        await session.send(_box("CHARACTER CREATION — Assign Stats", lines))

    async def _handle_stats_step(self, session: GameSession, text: str) -> None:
        """Process stat assignment commands."""
        upper = text.strip().upper()
        stats_list = ["STR", "DEX", "INT", "WIS", "CON", "AGI"]
        ctx = session._state_data

        if upper in ("HELP", "?"):
            await session.send(
                "  Commands during stat assignment:\n"
                "    SET <stat> <value>  — assign a stat\n"
                "    STATS               — show current assignments\n"
                "    SUGGEST             — apply recommended spread\n"
                "    DONE                — confirm and continue\n"
                "    QUIT                — exit the game\n"
            )
            return

        if upper == "STATS":
            spent = sum(ctx["pending_stats"].values()) - MIN_STAT * 6
            remain = STAT_POINT_BUY_BUDGET - spent
            lines = [f"  Points remaining: {remain}"]
            for s in stats_list:
                lines.append(f"    {s}: {ctx['pending_stats'].get(s, MIN_STAT)}")
            await session.send("\n".join(lines) + "\n")
            return

        if upper == "SUGGEST":
            cd = session.class_defs[ctx["pending_class"]]
            ctx["pending_stats"] = dict(cd["suggested_stats"])
            await session.send("  Suggested stats applied. Type DONE to confirm.\n")
            return

        if upper == "DONE":
            total = sum(ctx["pending_stats"].values()) - (MIN_STAT * 6)
            if total > STAT_POINT_BUY_BUDGET:
                await session.send(f"  You've spent {total} points but only have {STAT_POINT_BUY_BUDGET}.\n> ")
                return

            await self._finalize_character(session)
            return

        # SET <stat> <value>
        parts = upper.split()
        if len(parts) == 3 and parts[0] == "SET" and parts[1] in stats_list:
            try:
                val = int(parts[2])
            except ValueError:
                await session.send("  Usage: SET STR 15\n> ")
                return

            if val < MIN_STAT or val > MAX_STAT:
                await session.send(f"  Stat must be between {MIN_STAT} and {MAX_STAT}.\n> ")
                return

            old = ctx["pending_stats"].get(parts[1], MIN_STAT)
            new_spent = sum(ctx["pending_stats"].values()) - (MIN_STAT * 6) - old + val

            if new_spent > STAT_POINT_BUY_BUDGET:
                current_remain = STAT_POINT_BUY_BUDGET - (sum(ctx["pending_stats"].values()) - MIN_STAT * 6)
                await session.send(
                    f"  Not enough points. You have {current_remain} remaining but need {val - old} more.\n> "
                )
                return

            ctx["pending_stats"][parts[1]] = val
            remain = STAT_POINT_BUY_BUDGET - new_spent
            await session.send(f"  {parts[1]} set to {val}. Points remaining: {remain}\n> ")
        else:
            await session.send("  Usage: SET STR 15 | SUGGEST | STATS | DONE | HELP\n> ")

    async def _finalize_character(self, session: GameSession) -> None:
        """Create the character and transition to strategy setup."""
        ctx = session._state_data
        cd = session.class_defs[ctx["pending_class"]]
        s = ctx["pending_stats"]

        max_hp = cd["base_hp"] + max(0, (s.get("CON", 10) - 10))
        max_mp = cd["base_mp"] + max(0, (s.get("WIS", 10) - 10) * 2)

        session.player = Character(
            name=ctx["pending_name"],
            class_type=ctx["pending_class"],
            STR=s["STR"], DEX=s["DEX"], INT=s["INT"],
            WIS=s["WIS"], CON=s["CON"], AGI=s["AGI"],
            max_hp=max_hp, hp=max_hp,
            max_mp=max_mp, mp=max_mp,
        )

        # Give starting equipment
        starter_equipment = {
            "warrior": {"weapon": "rusty_sword", "body": "leather_armor"},
            "mage":    {"weapon": "oak_staff",   "body": "cloth_robe"},
            "thief":   {"weapon": "iron_dagger", "body": "leather_armor"},
            "cleric":  {"weapon": "wooden_mace", "body": "leather_armor"},
        }
        for slot, item_id in starter_equipment.get(ctx["pending_class"], {}).items():
            session.player.equipment[slot] = item_id
        session.player.inventory = ["health_potion", "health_potion", "campfire_kit"]

        # Default starting strategies
        for i, strat_raw in enumerate(cd.get("default_strategies", []), start=1):
            session.player.strategies.append({
                "priority": i,
                "condition": strat_raw["condition"],
                "action": strat_raw["action"],
                "target": strat_raw["target"],
            })

        # Unlock starter skills
        for skill_id in cd.get("starter_skills", []):
            session.player.unlocked_skills[skill_id] = 1

        session.current_room_id = "town_square"
        session.last_campfire_room_id = "test_campfire"
        session.player.owner = session.player.name

        await session.send(
            _box(f"CHARACTER CREATED: {session.player.name}", [
                session.player.stats_summary(),
                "",
                "  Your starting strategies:",
                list_strategies(session.player),
                "",
                "  You may now customize your strategies before entering the world.",
                "  Commands: STRATEGY LIST, STRATEGY ADD <n> IF <cond> DO <act> ON <tgt>",
                "             STRATEGY REMOVE <n>, STRATEGY CLEAR",
                "",
                "  When ready, type:  START",
            ])
        )

        # Transition to strategy editor
        await session.transition_to(
            State.STRATEGY,
            target=session.player,
            context="creation"
        )
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_phase02_character.py -v 2>&1 | tail -20`
Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/creation.py
git commit -m "feat(states): add CreationHandler with multi-step wizard"
```

---

### Task 6: Create StrategyHandler

**Files:**
- Create: `server/engine/states/strategy.py`

- [ ] **Step 1: Write StrategyHandler**

```python
"""Strategy editor state handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.states import State
from server.engine.strategy import (
    add_strategy, clear_strategies, list_strategies, remove_strategy
)
from server.engine.skills import get_skill

if TYPE_CHECKING:
    from server.engine.game import GameSession


def _box(title: str, lines: list[str]) -> str:
    """Format a boxed display."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class StrategyHandler:
    """Handles strategy editing for characters and companions."""

    async def on_enter(self, session: GameSession) -> None:
        """No special entry behavior - prompt comes from previous state."""
        pass

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process strategy editor commands."""
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)
        cmd = parts[0] if parts else ""

        ctx = session._state_data
        char = ctx.get("target")

        # Help
        if cmd in ("HELP", "?"):
            topic = parts[1] if len(parts) > 1 else ""
            await session._send_help(topic)
            return

        # Exit strategy editor
        if upper in ("DONE", "BACK", "EXIT", "START"):
            await self._exit_editor(session)
            return

        if upper == "STRATEGY LIST" or upper == "LIST":
            await session.send(_box(f"Strategies: {char.name}", [list_strategies(char)]))
            return

        if upper == "SKILLS":
            await self._show_skills(session, char)
            return

        if upper.startswith("STRATEGY ADD"):
            await self._parse_strategy_add(session, char, text)
            return

        if upper.startswith("STRATEGY REMOVE"):
            await self._handle_remove(session, char, upper)
            return

        if upper == "STRATEGY CLEAR":
            msg = clear_strategies(char)
            await session.send(f"  {msg}\n")
            return

        # Unknown command - show help
        await self._send_editor_help(session)

    async def _exit_editor(self, session: GameSession) -> None:
        """Exit back to appropriate state based on context."""
        ctx = session._state_data

        if ctx.get("context") == "creation":
            # First time entering world
            await session.transition_to(State.NAVIGATION)
            await session.send("\n  Entering the world of Ashveil...\n")
            # Trigger look via navigation handler
            from server.engine.states.navigation import NavigationHandler
            nav = NavigationHandler()
            await nav._do_look(session)
        else:
            # From campfire - go back
            await session.transition_to(State.CAMPFIRE)
            target_name = ctx.get("target", {}).name if ctx.get("target") else "companion"
            await session.send(
                f"  Strategy for {target_name} saved.\n"
                "  Back at campfire. Type HELP for available commands.\n"
            )

    async def _show_skills(self, session: GameSession, char) -> None:
        """Display character's unlocked skills."""
        if not char.unlocked_skills:
            await session.send(f"  {char.name} has no skills unlocked yet.\n")
            return

        lines = [f"  Unlocked skills for {char.name} ({char.class_type.capitalize()}):"]
        for skill_id in char.unlocked_skills:
            skill = get_skill(skill_id)
            if skill:
                lines.append(
                    f"    {skill_id:<20} — {skill.name}  (MP:{skill.mp_cost})  {skill.description}"
                )
            else:
                lines.append(f"    {skill_id}")

        lines.append("")
        lines.append("  Use the skill ID in a strategy:  DO USE_SKILL <id>")
        await session.send("\n".join(lines) + "\n")

    async def _parse_strategy_add(self, session: GameSession, char, text: str) -> None:
        """Parse STRATEGY ADD command."""
        try:
            upper = text.strip().upper()
            after_add = upper[len("STRATEGY ADD"):].strip()

            # Split on IF, DO, ON
            if_idx = after_add.index(" IF ")
            do_idx = after_add.index(" DO ")
            on_idx = after_add.index(" ON ")

            priority_str = after_add[:if_idx].strip()
            condition = after_add[if_idx + 4:do_idx].strip()
            action = after_add[do_idx + 4:on_idx].strip()
            target = after_add[on_idx + 4:].strip()
            priority = int(priority_str)
        except (ValueError, AttributeError):
            await session.send(
                "  Usage: STRATEGY ADD <number> IF <condition> DO <action> ON <target>\n"
                "  Example: STRATEGY ADD 1 IF HP_SELF < 30% DO DEFEND ON SELF\n"
            )
            return

        msg = add_strategy(char, priority, condition, action, target)
        await session.send(f"  {msg}\n")
        await session.send(list_strategies(char) + "\n")

    async def _handle_remove(self, session: GameSession, char, upper: str) -> None:
        """Handle STRATEGY REMOVE command."""
        parts = upper.split()
        if len(parts) >= 3:
            try:
                n = int(parts[2])
                msg = remove_strategy(char, n)
                await session.send(f"  {msg}\n")
            except ValueError:
                await session.send("  Usage: STRATEGY REMOVE <number>\n")

    async def _send_editor_help(self, session: GameSession) -> None:
        """Display strategy editor help text."""
        await session.send(
            "  Strategy editor commands:\n"
            "    STRATEGY LIST                          — show current rules\n"
            "    SKILLS                                 — list unlocked skills\n"
            "    STRATEGY ADD <n> IF <cond> DO <act> ON <tgt>\n"
            "    STRATEGY REMOVE <n>\n"
            "    STRATEGY CLEAR\n"
            "    DONE  (save and exit editor)\n"
            "\n"
            "  Conditions: ALWAYS | HP_SELF < X% | HP_ALLY < X% | MP_SELF < X%\n"
            "              ENEMY_COUNT > N | HAS_STATUS <s> | ENEMY_HAS_STATUS <s>\n"
            "  Actions:    ATTACK | DEFEND | FLEE | USE_SKILL <id> | USE_ITEM <id>\n"
            "  Targets:    NEAREST_ENEMY | WEAKEST_ENEMY | STRONGEST_ENEMY\n"
            "              LOWEST_HP_ALLY | LOWEST_HP_ENEMY | SELF | RANDOM_ENEMY\n"
        )
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v -k "strategy" 2>&1 | tail -20`
Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/strategy.py
git commit -m "feat(states): add StrategyHandler"
```

---

### Task 7: Create CampfireHandler

**Files:**
- Create: `server/engine/states/campfire.py`

- [ ] **Step 1: Write CampfireHandler**

```python
"""Campfire state handler — rest, party management, skills."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.engine.states import State
from server.engine.skills import render_skill_tree

if TYPE_CHECKING:
    from server.engine.game import GameSession


def _box(title: str, lines: list[str]) -> str:
    """Format a boxed display."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class CampfireHandler:
    """Handles campfire rest state commands."""

    async def on_enter(self, session: GameSession) -> None:
        """Display campfire menu and options."""
        await session.send(
            _box("CAMPFIRE", [
                "  A warm fire crackles before you.",
                "",
                "  PARTY                — View party stats",
                "  FORMATION           — View / change battle positions",
                "  MANAGE <name>        — Edit that member's strategies",
                "  REST                 — Restore HP/MP and save",
                "  SKILLS               — View skill tree",
                "  LEARN <skill>        — Spend skill points",
                "  MODIFIERS / MODS     — View modifiers",
                "  UPGRADE <modifier>   — Spend modifier points",
                "  DISMISS <name>       — Remove companion",
                "  LEAVE                — Return to exploration",
            ])
        )

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Process campfire commands."""
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("LEAVE", "EXIT", "BACK"):
            await session.transition_to(State.NAVIGATION)
            await session.send("  You leave the campfire.\n")
            # Trigger look
            from server.engine.states.navigation import NavigationHandler
            nav = NavigationHandler()
            await nav._do_look(session)
            return

        if cmd == "REST":
            await self._do_rest(session)
            return

        if cmd == "PARTY":
            await session._do_show_party()
            return

        if cmd == "FORMATION":
            await session._do_formation(args)
            return

        if cmd == "MANAGE":
            await session._do_manage(args)
            return

        if cmd == "DISMISS":
            await session._do_dismiss(args)
            return

        if cmd == "SKILLS":
            await session.send(
                render_skill_tree(
                    session.player.class_type,
                    session.player.unlocked_skills,
                    session.player.skill_points,
                ) + "\n"
            )
            return

        if cmd == "LEARN":
            await session._do_learn(args.lower())
            return

        if cmd in ("MODIFIERS", "MODS"):
            await session._do_show_modifiers()
            return

        if cmd == "UPGRADE":
            await session._do_upgrade(args.lower())
            return

        if cmd == "SAVE":
            session.save()
            await session.send("  Game saved.\n")
            return

        if cmd == "HELP":
            await session._send_help(args)
            return

        if cmd == "USE":
            await session.send("  You can only use utility skills while exploring (NAVIGATION).\n")
            return

        await session.send(f"  Unknown campfire command. Type HELP.\n")

    async def _do_rest(self, session: GameSession) -> None:
        """Restore all stats and save."""
        # Restore player
        session.player.hp = session.player.max_hp
        session.player.mp = session.player.max_mp
        session.player.stamina = session.player.max_stamina

        # Restore party
        for npc in session.party:
            npc.hp = npc.max_hp
            npc.mp = npc.max_mp
            npc.stamina = npc.max_stamina

        session.save()
        await session.send("  You rest and recover fully. Game saved.\n")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v -k "campfire or rest" 2>&1 | tail -20`
Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/campfire.py
git commit -m "feat(states): add CampfireHandler"
```

---

## Phase 3: Complex State Handlers

### Task 8: Create CombatHandler

**Files:**
- Create: `server/engine/states/combat.py`
- Modify: `server/engine/game.py:1257-1380` (extract combat orchestration)

- [ ] **Step 1: Write CombatHandler**

```python
"""Combat state handler — orchestrates CombatSession."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.config import DEBUG_NO_DEATH_PENALTY, DEATH_XP_LOSS_PCT, DEATH_GOLD_LOSS_PCT, DEBUG_RESPAWN_ROOM_ID
from server.engine.combat import CombatSession
from server.engine.npc import spawn_npc
from server.engine.states import State

if TYPE_CHECKING:
    from server.engine.game import GameSession


class CombatHandler:
    """Handles combat state — delegates to CombatSession."""

    async def on_enter(self, session: GameSession) -> None:
        """Setup and run combat to completion."""
        ctx = session._state_data
        encounter_group = ctx.get("encounter_group")
        arena_group = ctx.get("arena_group")

        # Spawn enemies
        enemy_npcs = []
        for tid in encounter_group.members:
            npc = spawn_npc(tid, session.class_defs)
            if npc:
                enemy_npcs.append(npc)

        if not enemy_npcs:
            await session.send("  Could not spawn enemies.\n")
            await session.transition_to(State.NAVIGATION)
            return

        # Auto-dismount
        if session._mounted:
            session._was_mounted = True
            session._mounted = False
            await session.send("  The party dismounts as combat begins.\n")

        # Create combat session
        player_party = [session.player] + session.party

        from server.engine.environment import effective_light
        from server.engine.survival import apply_survival_penalties

        room = session.world.get_room(session.current_room_id)
        lighting = effective_light(
            session.player, session.party,
            session.player.lit_sources, session.clock, room
        )
        survival_mult, _ = apply_survival_penalties(session.player, session.party)

        combat = CombatSession(
            player_party=player_party,
            enemy_party=enemy_npcs,
            send=session.send,
            lighting=lighting,
            survival_multiplier=survival_mult,
        )

        session._combat = combat

        # Run combat
        result = await combat.run_and_get_result()

        # Process results
        await session.send("\n".join(result.summary))

        if result.state == "victory":
            encounter_group.mark_defeated()
            combat.collect_rewards(player_party, session.class_defs)
            await self._handle_victory(session)
        else:
            await self._handle_defeat(session)

        session._combat = None

    async def on_exit(self, session: GameSession) -> None:
        """Cleanup combat state."""
        session._combat = None

    async def handle(self, session: GameSession, text: str) -> None:
        """Process minimal combat commands (only HELP is really useful)."""
        upper = text.strip().upper()
        parts = upper.split(maxsplit=1)

        if parts and parts[0] == "HELP":
            topic = parts[1] if len(parts) > 1 else ""
            await session._send_help(topic)
            return

        if parts and parts[0] == "USE":
            await session.send("  You cannot use utility skills while in combat.\n")
            return

        await session.send("  Combat is in progress. Your strategies are running...\n")

    async def _handle_victory(self, session: GameSession) -> None:
        """Handle victory transition."""
        # Auto-remount after victory if in outdoor room
        if session._was_mounted:
            room = session.world.get_room(session.current_room_id)
            if room and room.room_type == "outdoor":
                session._mounted = True
                await session.send("  The party remounts and continues on.\n")
            session._was_mounted = False

        await session.transition_to(State.NAVIGATION)

        # Trigger look
        from server.engine.states.navigation import NavigationHandler
        nav = NavigationHandler()
        await nav._do_look(session)

    async def _handle_defeat(self, session: GameSession) -> None:
        """Handle defeat transition."""
        if not DEBUG_NO_DEATH_PENALTY:
            xp_loss = round(session.player.xp * DEATH_XP_LOSS_PCT)
            gold_loss = round(session.player.gold * DEATH_GOLD_LOSS_PCT)
            session.player.xp = max(0, session.player.xp - xp_loss)
            session.player.gold = max(0, session.player.gold - gold_loss)
            await session.send(f"  You lost {xp_loss} XP and {gold_loss} gold.\n")

        # Restore HP/MP
        session.player.hp = session.player.max_hp
        session.player.mp = session.player.max_mp
        for npc in session.party:
            npc.hp = npc.max_hp
            npc.mp = npc.max_mp

        # Respawn
        respawn = DEBUG_RESPAWN_ROOM_ID if DEBUG_NO_DEATH_PENALTY else session.last_campfire_room_id
        session.current_room_id = respawn

        await session.transition_to(State.NAVIGATION)
        await session.send("\n  You find yourself back at the Proving Grounds, wounds healed.\n")

        # Trigger look
        from server.engine.states.navigation import NavigationHandler
        nav = NavigationHandler()
        await nav._do_look(session)
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v -k "combat" 2>&1 | tail -30`
Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/combat.py
git commit -m "feat(states): add CombatHandler"
```

---

### Task 9: Create NavigationHandler

**Files:**
- Create: `server/engine/states/navigation.py`
- Modify: `server/engine/game.py:637-820` (extract navigation commands)

- [ ] **Step 1: Write NavigationHandler**

```python
"""Navigation state handler — exploration and main gameplay."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from server.engine.states import State
from server.engine.inventory_ops import (
    do_inventory, do_equip, do_unequip, do_drop, do_pick_up,
    do_give, do_load_cart, do_unload_cart
)
from server.engine.chat import do_say, do_emote, do_shout
from server.engine.environment import (
    do_time, do_weather, do_light, do_envdetails, do_light_source,
    carried_light, effective_light
)
from server.engine.survival import (
    do_survival_status, do_eat, do_drink, do_buffs
)

if TYPE_CHECKING:
    from server.engine.game import GameSession


def _box(title: str, lines: list[str]) -> str:
    """Format a boxed display."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class NavigationHandler:
    """Handles navigation state — the main exploration gameplay."""

    # Movement direction aliases
    DIR_ALIASES = {
        "n": "north", "s": "south", "e": "east", "w": "west",
        "u": "up", "d": "down",
        "north": "north", "south": "south", "east": "east",
        "west": "west", "up": "up", "down": "down",
    }

    # O(1) command dispatch table
    def __init__(self):
        self.commands: dict[str, Callable] = {
            # Look / examine
            "look": self._do_look,
            "examine": self._do_examine,

            # Inventory
            "inventory": self._do_inventory,
            "inv": self._do_inventory,
            "i": self._do_inventory,
            "equip": self._do_equip,
            "unequip": self._do_unequip,
            "drop": self._do_drop,
            "pick": self._do_pick_up,
            "take": self._do_pick_up,
            "get": self._do_pick_up,
            "give": self._do_give,
            "load": self._do_load_cart,
            "stash": self._do_stash,
            "unload": self._do_unload_cart,

            # Character
            "stats": self._do_stats,
            "stat": self._do_stats,
            "gold": self._do_gold,
            "skills": self._do_skills,
            "learn": self._do_learn,
            "modifiers": self._do_modifiers,
            "mods": self._do_modifiers,
            "upgrade": self._do_upgrade,

            # Party
            "party": self._do_party,
            "talk": self._do_talk,
            "dismiss": self._do_dismiss,

            # Campfire
            "campfire": self._do_campfire,
            "rest": self._do_campfire,

            # Survival
            "status": self._do_status,
            "sit": self._do_sit,
            "stand": self._do_stand,
            "eat": self._do_eat,
            "drink": self._do_drink,
            "buffs": self._do_buffs,

            # Combat
            "attack": self._do_attack,

            # Utility skills
            "use": self._do_use,

            # Environment
            "save": self._do_save,
            "time": self._do_time,
            "weather": self._do_weather,
            "light": self._do_light,
            "lighting": self._do_light,
            "envdetails": self._do_envdetails,
            "env": self._do_envdetails,
            "lit": self._do_lit,
            "extinguish": self._do_extinguish,
            "douse": self._do_extinguish,

            # Mounts
            "ride": self._do_ride,
            "dismount": self._do_dismount,
            "horses": self._do_horses,

            # Chat
            "say": self._do_say,
            "emote": self._do_emote,
            "me": self._do_emote,
            "shout": self._do_shout,
            "ooc": self._do_shout,

            # Help
            "help": self._do_help,
        }

    async def on_enter(self, session: GameSession) -> None:
        """Subscribe to clock and show current room."""
        session._subscribe_clock()
        await self._do_look(session)

    async def on_exit(self, session: GameSession) -> None:
        """No cleanup needed."""
        pass

    async def handle(self, session: GameSession, text: str) -> None:
        """Main command dispatch with O(1) lookup."""
        text_stripped = text.strip()
        if not text_stripped:
            return

        # Check for pending recruit response (from TALK command)
        if await self._try_recruit_response(session, text_stripped):
            return

        # Parse command
        parts = text_stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        raw_parts = text_stripped.split(maxsplit=1)
        raw_args = raw_parts[1] if len(raw_parts) > 1 else ""

        # Handle movement (not in commands dict)
        if cmd in self.DIR_ALIASES:
            await self._do_move(session, self.DIR_ALIASES[cmd])
            return

        if cmd == "go" and args:
            await self._do_move(session, args.lower())
            return

        # Regular command dispatch
        if handler := self.commands.get(cmd):
            await handler(session, args, raw_args)
        else:
            await session.send(f"  Unknown command '{cmd}'. Type HELP for a list.\n")

    # ────────────────────────────────────────────────────────────────────────
    # Command implementations
    # ────────────────────────────────────────────────────────────────────────

    async def _do_look(self, session: GameSession, *args) -> None:
        """Look at current room."""
        from server.engine.items import get_item
        from server.engine.npc import get_npc_template

        room = session.world.get_room(session.current_room_id)
        if room is None:
            await session.send("  Error: current room not found.\n")
            return

        # Item names for display
        item_names = {i: get_item(i).name for i in room.item_ids if get_item(i)}

        # Recruitable NPCs
        npc_flavors = []
        if room.recruitable_npc_ids:
            for tid in room.recruitable_npc_ids:
                tpl = get_npc_template(tid)
                if tpl:
                    in_party = any(m.template_id == tid for m in session.party)
                    if not in_party:
                        npc_flavors.append(tpl.get("room_flavor", tpl["name"]))

        # Encounters
        encounter_lines = []
        active_groups = session.world.active_encounter_groups(session.current_room_id)
        for eg in active_groups:
            label = eg.label if eg.label else eg.group
            if room.id == "test_arena":
                encounter_lines.append(
                    f"[{eg.group}] {label} — {len(eg.members)} opponent(s)  "
                    f"(ATTACK {eg.group} to engage)"
                )
            else:
                encounter_lines.append(f"Hostile group present: {', '.join(eg.members)}")

        # Environment footer
        footer = ""
        if session.clock:
            footer = session.clock.env_footer(
                room.room_type, room.base_temp_f,
                carried_light(session.player, session.party, session.player.lit_sources, session.clock, session.send)
            )

        await session.send(room.render(item_names, npc_flavors, encounter_lines, env_footer=footer))

        # Other players
        if session.player:
            others = [
                n for n in await session.world.players_in_room(session.current_room_id)
                if n != session.player.name
            ]
            if others:
                await session.send(f"\n  Also here: {', '.join(others)}\n")

        # Stamina warning
        if session.player and session.player.stamina <= 0.0:
            await session.send(
                "  !! The party is completely exhausted. Rest to recover stamina. !!\n"
            )

    async def _do_move(self, session: GameSession, direction: str) -> None:
        """Move in a direction."""
        from server.config import STAMINA_DRAIN_PER_MOVE, MOUNT_STAMINA_REDUCTION

        room = session.world.get_room(session.current_room_id)
        if room is None:
            await session.send("  You are in the void. Something went wrong.\n")
            return

        dest_id = room.exits.get(direction)
        if not dest_id:
            await session.send(f"  You can't go {direction} from here.\n")
            return

        # Block exhausted movement
        if session.player and session.player.stamina <= 0.0:
            await session.send("  You are too exhausted to move. Rest to recover your stamina.\n")
            return

        # Drain stamina
        if session.player:
            members = [session.player] + list(session.party)
            mount_mult = 1.0
            if session._mounted:
                horse_count = sum(
                    1 for m in members for item_id in m.inventory
                    if (item := __import__('server.engine.items', fromlist=['get_item']).get_item(item_id))
                    and item.type == "mount"
                )
                party_size = max(1, len(members))
                ratio = min(1.0, horse_count / party_size)
                mount_mult = 1.0 - (MOUNT_STAMINA_REDUCTION * ratio)

            for m in members:
                drain = STAMINA_DRAIN_PER_MOVE * mount_mult
                if session.clock and "fortified" in m.get_active_buffs(session.clock):
                    drain *= 0.7
                m.stamina = max(0.0, m.stamina - drain)

        # Cart and horse logic
        dest_room = session.world.get_room(dest_id)
        if dest_room:
            # Cart logic
            if dest_room.room_type in ("indoor", "underground") and session._cart_present:
                session._cart_present = False
                session._cart_room_id = session.current_room_id
                await session.send(f"  Your cart remains outside.\n")
            elif dest_room.room_type == "outdoor" and session._cart_room_id:
                session._cart_present = True
                session._cart_room_id = None
                await session.send("  Your cart catches up with the party.\n")

            # Horse logic
            if dest_room.room_type in ("indoor", "underground") and session._mounted:
                session._mounted = False
                session._horses_outside = True
                await session.send("  Your horses wait outside.\n")
            elif dest_room.room_type == "outdoor" and session._horses_outside:
                session._horses_outside = False
                session._mounted = True
                await session.send("  Your horses fall back into step.\n")

        # Broadcast and move
        player_name = session.player.name if session.player else "Someone"
        old_room_id = session.current_room_id

        await session.world.leave_room(player_name, old_room_id)
        await session.broadcast_to_room(f"  {player_name} heads {direction}.\n", exclude_self=True)

        session.current_room_id = dest_id

        await session.world.enter_room(player_name, dest_id)
        opposite = {"north": "south", "south": "north", "east": "west", "west": "east", "up": "down", "down": "up"}.get(direction, direction)
        await session.broadcast_to_room(f"  {player_name} arrives from the {opposite}.\n", exclude_self=True)

        await self._do_look(session)

    async def _do_examine(self, session: GameSession, args: str, *_) -> None:
        """Examine an item or NPC."""
        from server.engine.items import get_item
        from server.engine.npc import get_npc_template

        target = args.lower().strip()
        if not target:
            await session.send("  Examine what?\n")
            return

        room = session.world.get_room(session.current_room_id)

        # Check room items
        for item_id in room.item_ids:
            item = get_item(item_id)
            if item and target in item.name.lower():
                await session.send(_box(item.name, [item.description, item.short_desc()]))
                return

        # Check inventory
        for item_id in session.player.inventory:
            item = get_item(item_id)
            if item and target in item.name.lower():
                await session.send(_box(item.name, [item.description, item.short_desc()]))
                return

        # Check recruitable NPCs
        for tid in room.recruitable_npc_ids:
            tpl = get_npc_template(tid)
            if tpl and target in tpl["name"].lower():
                await session.send(_box(
                    tpl["name"],
                    [tpl.get("room_flavor", ""), f"Class: {tpl['class_type'].capitalize()}, Level {tpl['level']}"]
                ))
                return

        await session.send(f"  You don't see '{args}' here.\n")

    async def _do_inventory(self, session: GameSession, args: str, *_) -> None:
        """Show inventory."""
        await do_inventory(session.send, session.player, session.party, session._cart_inventory, args)

    async def _do_equip(self, session: GameSession, args: str, *_) -> None:
        """Equip an item."""
        await do_equip(session.send, session.player, args)

    async def _do_unequip(self, session: GameSession, args: str, *_) -> None:
        """Unequip an item."""
        await do_unequip(session.send, session.player, args)

    async def _do_drop(self, session: GameSession, args: str, *_) -> None:
        """Drop an item."""
        room = session.world.get_room(session.current_room_id)
        await do_drop(session.send, session.player, room, session.broadcast_to_room, args)

    async def _do_pick_up(self, session: GameSession, args: str, *_) -> None:
        """Pick up an item."""
        room = session.world.get_room(session.current_room_id)
        await do_pick_up(
            session.send, session.player, session.party, room,
            session._cart_inventory, session._cart_present,
            session.broadcast_to_room, args
        )

    async def _do_stash(self, session: GameSession, args: str, *_) -> None:
        """Stash item in cart (alias for LOAD CART)."""
        await do_load_cart(session.send, session.player, session.party, session._cart_inventory, session._cart_present, args)

    async def _do_load_cart(self, session: GameSession, args: str, *_) -> None:
        """Load item into cart."""
        await do_load_cart(session.send, session.player, session.party, session._cart_inventory, session._cart_present, args)

    async def _do_unload_cart(self, session: GameSession, args: str, *_) -> None:
        """Unload item from cart."""
        await do_unload_cart(session.send, session.player, session.party, session._cart_inventory, session._cart_present, args)

    async def _do_give(self, session: GameSession, args: str, *_) -> None:
        """Give item to party member."""
        await do_give(session.send, session.player, session.party, args)

    async def _do_stats(self, session: GameSession, *args) -> None:
        """Show character stats."""
        await session.send(session.player.stats_summary() + "\n")

    async def _do_gold(self, session: GameSession, *args) -> None:
        """Show gold amount."""
        await session.send(f"  You have {session.player.gold} gold.\n")

    async def _do_skills(self, session: GameSession, args: str, *_) -> None:
        """Show skill tree."""
        from server.engine.skills import render_skills_section
        await session.send(
            render_skills_section(
                session.player.class_type,
                session.player.unlocked_skills,
                session.player.skill_points,
                args.lower().strip()
            ) + "\n"
        )

    async def _do_learn(self, session: GameSession, args: str, *_) -> None:
        """Learn a skill."""
        from server.engine.skills import can_learn, get_skill_tree, get_skill

        skill_id = args.strip()
        if not skill_id:
            await session.send("  Learn what? Usage: LEARN <skill_id>\n")
            return

        ok, reason = can_learn(
            session.player.class_type, skill_id,
            session.player.unlocked_skills, session.player.skill_points
        )
        if not ok:
            await session.send(f"  Cannot learn: {reason}\n")
            return

        tree = get_skill_tree(session.player.class_type)
        node = next(n for n in tree if n.skill_id == skill_id)
        session.player.skill_points -= node.unlock_cost
        session.player.unlocked_skills[skill_id] = 1
        skill = get_skill(skill_id)
        await session.send(f"  You learned {skill.name}!\n")

    async def _do_modifiers(self, session: GameSession, *args) -> None:
        """Show character modifiers."""
        from server.engine.character import MODIFIER_CATALOGUE
        from server.config import MODIFIER_BONUS_PER_LEVEL

        lines = [f"  Modifier Points available: {session.player.modifier_points}", ""]
        for mod_id, meta in MODIFIER_CATALOGUE.items():
            level = session.player.modifiers.get(mod_id, 0)
            bonus_pct = round(level * MODIFIER_BONUS_PER_LEVEL * 100)
            lines.append(f"  {meta['label']:<25} Lv.{level} (+{bonus_pct}%)")
        await session.send(_box("MODIFIERS", lines))

    async def _do_upgrade(self, session: GameSession, args: str, *_) -> None:
        """Upgrade a modifier."""
        from server.engine.character import MODIFIER_CATALOGUE
        from server.config import MODIFIER_BONUS_PER_LEVEL

        mod_id = args.strip().lower()
        if not mod_id:
            await session.send("  Upgrade what? Usage: UPGRADE <modifier_id>\n")
            return

        if mod_id not in MODIFIER_CATALOGUE:
            await session.send(f"  Unknown modifier. Valid: {', '.join(MODIFIER_CATALOGUE.keys())}\n")
            return

        if session.player.modifier_points < 1:
            await session.send("  You have no modifier points.\n")
            return

        session.player.modifier_points -= 1
        session.player.modifiers[mod_id] = session.player.modifiers.get(mod_id, 0) + 1

        meta = MODIFIER_CATALOGUE[mod_id]
        new_level = session.player.modifiers[mod_id]
        new_pct = round(new_level * MODIFIER_BONUS_PER_LEVEL * 100)
        await session.send(
            f"  {meta['label']} improved to Lv.{new_level} (+{new_pct}%).\n"
            f"  Modifier points remaining: {session.player.modifier_points}\n"
        )

    async def _do_party(self, session: GameSession, *args) -> None:
        """Show party status."""
        from server.engine.survival import party_survival_aggregate

        lines = []
        lines.append(session.player.stats_summary())
        lines.append("")
        if not session.party:
            lines.append("  (no companions)")
        for i, npc in enumerate(session.party, 1):
            lines.append(f"  [{i}] {npc.stats_summary()}")
            lines.append("")

        h_pct, t_pct, s_pct = party_survival_aggregate(session.player, session.party)
        lines.append(
            f"  Survival  Stamina {s_pct * 100:.0f}%  "
            f"Hunger {h_pct * 100:.0f}%  "
            f"Thirst {t_pct * 100:.0f}%"
        )
        await session.send(_box("PARTY", lines))

    async def _do_talk(self, session: GameSession, args: str, *_) -> None:
        """Talk to a recruitable NPC."""
        from server.engine.npc import get_npc_template, spawn_npc

        name = args.lower().strip()
        if not name:
            await session.send("  Talk to who?\n")
            return

        room = session.world.get_room(session.current_room_id)
        if not room:
            return

        for tid in room.recruitable_npc_ids:
            tpl = get_npc_template(tid)
            if tpl and name in tpl["name"].lower():
                already_in_party = any(m.template_id == tid for m in session.party)
                if already_in_party:
                    await session.send(f"  {tpl['name']} is already in your party.\n")
                    return
                if len(session.party) >= 4:
                    await session.send("  Your party is full. Dismiss someone first.\n")
                    return

                await session.send(tpl.get("recruit_dialogue", f"{tpl['name']} nods at you.\n"))

                # Store pending recruit in session state
                session._pending_recruit = tid
                return

        await session.send(f"  There's no one named '{args}' here to talk to.\n")

    async def _do_dismiss(self, session: GameSession, args: str, *_) -> None:
        """Dismiss a companion."""
        name = args.lower().strip()
        if not name:
            await session.send("  Dismiss who?\n")
            return

        for npc in session.party:
            if name in npc.name.lower():
                session.party.remove(npc)
                await session.send(f"  {npc.name} has left your party.\n")
                return

        await session.send(f"  No companion named '{args}' in your party.\n")

    async def _do_campfire(self, session: GameSession, *args) -> None:
        """Enter campfire state."""
        room = session.world.get_room(session.current_room_id)
        if not room:
            return

        has_kit = "campfire_kit" in session.player.inventory
        if not room.is_campfire and not has_kit:
            await session.send("  No campfire here. Find a campfire room or use a Campfire Kit.\n")
            return

        if has_kit and not room.is_campfire:
            session.player.inventory.remove("campfire_kit")

        if room.is_campfire:
            session.last_campfire_room_id = session.current_room_id

        await session.transition_to(State.CAMPFIRE)

    async def _do_status(self, session: GameSession, *args) -> None:
        """Show survival status."""
        await do_survival_status(session.send, session.player, session.party)

    async def _do_sit(self, session: GameSession, *args) -> None:
        """Sit down to rest."""
        session._sitting = True
        await session.send("  You sit down to rest.\n")

    async def _do_stand(self, session: GameSession, *args) -> None:
        """Stand up."""
        session._sitting = False
        await session.send("  You stand up.\n")

    async def _do_eat(self, session: GameSession, args: str, *_) -> None:
        """Eat food."""
        await do_eat(session.send, session.player, session.party, session.clock, args)

    async def _do_drink(self, session: GameSession, args: str, *_) -> None:
        """Drink."""
        await do_drink(session.send, session.player, session.party, session.clock, args)

    async def _do_buffs(self, session: GameSession, *args) -> None:
        """Show active buffs."""
        await do_buffs(session.send, session.player, session.party, session.clock)

    async def _do_attack(self, session: GameSession, args: str, *_) -> None:
        """Initiate combat."""
        from server.engine.npc import get_npc_template

        room = session.world.get_room(session.current_room_id)
        if not room:
            return

        group_id = args.strip().upper() if args else None
        active = session.world.active_encounter_groups(session.current_room_id)

        if not active:
            await session.send("  There's no one left to fight here.\n")
            return

        # Lighting check
        if session.clock:
            eff_light = effective_light(
                session.player, session.party,
                session.player.lit_sources, session.clock, room
            )
            if eff_light < 0.05:
                # Check for darkvision enemies
                target_group = (
                    next((g for g in active if g.group == group_id), None)
                    if group_id else active[0]
                )
                enemy_has_darkvision = False
                if target_group:
                    for tid in target_group.members:
                        tpl = get_npc_template(tid)
                        if tpl and tpl.get("darkvision", False):
                            enemy_has_darkvision = True
                            break
                if not enemy_has_darkvision:
                    await session.send(
                        "  It is pitch black — you cannot fight what you cannot see.\n"
                        "  Light a torch or find another source of light.\n"
                    )
                    return

        # Arena: pick group by letter
        if room.id == "test_arena":
            if not group_id:
                await session.send("  Specify a group: ATTACK A, ATTACK B, ATTACK C, or ATTACK D\n")
                return
            target_group = next((g for g in active if g.group == group_id), None)
            if not target_group:
                await session.send(f"  Group '{group_id}' is defeated or doesn't exist.\n")
                return
            arena_group = group_id
        else:
            target_group = active[0]
            arena_group = None

        await session.transition_to(
            State.COMBAT,
            encounter_group=target_group,
            arena_group=arena_group
        )

    async def _do_use(self, session: GameSession, args: str, *_) -> None:
        """Use a utility skill."""
        # Delegate to GameSession method (utility skills are complex)
        await session._handle_use_skill(args)

    async def _do_save(self, session: GameSession, *args) -> None:
        """Save game."""
        session.save()
        await session.send("  Game saved.\n")

    async def _do_time(self, session: GameSession, *args) -> None:
        """Show game time."""
        await do_time(session.send, session.clock)

    async def _do_weather(self, session: GameSession, *args) -> None:
        """Show weather."""
        room = session.world.get_room(session.current_room_id)
        await do_weather(session.send, session.clock, room)

    async def _do_light(self, session: GameSession, *args) -> None:
        """Show lighting info."""
        room = session.world.get_room(session.current_room_id)
        await do_light(session.send, session.clock, room, session.player.lit_sources, lambda: carried_light(
            session.player, session.party, session.player.lit_sources, session.clock, session.send
        ))

    async def _do_envdetails(self, session: GameSession, *args) -> None:
        """Show environment details."""
        room = session.world.get_room(session.current_room_id)
        await do_envdetails(session.send, session.clock, room, lambda: carried_light(
            session.player, session.party, session.player.lit_sources, session.clock, session.send
        ))

    async def _do_lit(self, session: GameSession, args: str, *_) -> None:
        """Light a light source."""
        await do_light_source(session.send, session.player, session.party, session.player.lit_sources, session.clock, args, extinguish=False)

    async def _do_extinguish(self, session: GameSession, args: str, *_) -> None:
        """Extinguish a light source."""
        await do_light_source(session.send, session.player, session.party, session.player.lit_sources, session.clock, args, extinguish=True)

    async def _do_ride(self, session: GameSession, *args) -> None:
        """Mount horses."""
        # Check for horses
        from server.engine.items import get_item

        horse_count = sum(
            1 for m in ([session.player] + list(session.party))
            for item_id in m.inventory
            if (item := get_item(item_id)) and item.type == "mount"
        )

        if horse_count == 0:
            await session.send("  You don't have any horses.\n")
            return

        room = session.world.get_room(session.current_room_id)
        if room and room.room_type != "outdoor":
            await session.send("  You can only mount up outdoors.\n")
            return

        session._mounted = True
        await session.send("  The party mounts up and prepares to ride.\n")

    async def _do_dismount(self, session: GameSession, *args) -> None:
        """Dismount horses."""
        session._mounted = False
        await session.send("  The party dismounts.\n")

    async def _do_horses(self, session: GameSession, *args) -> None:
        """Show horse status."""
        from server.engine.items import get_item
        from server.config import MOUNT_STAMINA_REDUCTION

        horse_count = sum(
            1 for m in ([session.player] + list(session.party))
            for item_id in m.inventory
            if (item := get_item(item_id)) and item.type == "mount"
        )
        party_size = 1 + len(session.party)
        ratio = min(1.0, horse_count / max(1, party_size)) if session._mounted else 0.0
        reduction_pct = round(MOUNT_STAMINA_REDUCTION * ratio * 100)

        await session.send(
            f"  Horses: {horse_count} | Party: {party_size} | Stamina drain: -{reduction_pct}%\n"
        )

    async def _do_say(self, session: GameSession, args: str, raw_args: str) -> None:
        """Say something to the room."""
        player_name = session.player.name if session.player else "Someone"
        await do_say(session.send, session.broadcast_to_room, player_name, raw_args)

    async def _do_emote(self, session: GameSession, args: str, raw_args: str) -> None:
        """Perform an emote."""
        player_name = session.player.name if session.player else "Someone"
        await do_emote(session.send, session.broadcast_to_room, player_name, raw_args)

    async def _do_shout(self, session: GameSession, args: str, raw_args: str) -> None:
        """Shout to all players."""
        player_name = session.player.name if session.player else "Someone"
        await do_shout(session.send, session._sessions, player_name, raw_args)

    async def _do_help(self, session: GameSession, args: str, *_) -> None:
        """Show help."""
        await session._send_help(args)

    async def _try_recruit_response(self, session: GameSession, text: str) -> bool:
        """Handle YES/NO response after TALK command."""
        from server.engine.npc import spawn_npc

        if not hasattr(session, "_pending_recruit") or session._pending_recruit is None:
            return False

        upper = text.strip().upper()
        if upper not in ("YES", "NO", "Y", "N"):
            return False

        tid = session._pending_recruit
        session._pending_recruit = None

        if upper in ("YES", "Y"):
            npc = spawn_npc(tid, session.class_defs)
            if npc:
                npc.owner = session.player.name
                session.party.append(npc)
                await session.send(
                    f"\n  {npc.name} joins your party!\n"
                    f"  Their default strategies are already configured.\n"
                    f"  Visit the campfire to customise them with MANAGE {npc.name}.\n"
                )
            else:
                await session.send("  Something went wrong recruiting that NPC.\n")
        else:
            await session.send("  You decline.\n")

        return True
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_phase02_commands.py tests/test_phase03_utility_skills.py -v 2>&1 | tail -40`
Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/navigation.py
git commit -m "feat(states): add NavigationHandler with O(1) command dispatch"
```

---

## Phase 4: Refactor GameSession

### Task 10: Refactor GameSession to Coordinator

**Files:**
- Modify: `server/engine/game.py` — Replace with ~250 line coordinator version

- [ ] **Step 1: Write new GameSession**

```python
"""
GameSession — per-connection state machine coordinator.

Refactored from 1,667-line god object to stateless coordinator.
State-specific logic moved to handlers in server.engine.states.

States:
  CONNECT     → prompt for name
  CREATION    → character creation wizard
  NAVIGATION  → explore rooms, talk to NPCs
  CAMPFIRE    → rest, manage party, strategies, learn skills
  STRATEGY    → strategy editor sub-mode
  COMBAT      → hands-off while CombatSession runs

All output flows through `await self.send(text)`.
Input arrives via `await self.handle_input(raw_text)`.
"""
from __future__ import annotations

from server.config import DEBUG_NO_DEATH_PENALTY, DEBUG_RESPAWN_ROOM_ID, DEATH_XP_LOSS_PCT, DEATH_GOLD_LOSS_PCT, STAT_POINT_BUY_BUDGET, MIN_STAT, MAX_STAT, MODIFIER_BONUS_PER_LEVEL, MOUNT_STAMINA_REDUCTION, STAMINA_DRAIN_PER_MOVE
from server.engine.character import Character, MODIFIER_CATALOGUE, XP_TABLE
from server.engine.combat import CombatSession
from server.engine.items import get_item, equipped_weapon, total_equipped_weight
from server.engine.npc import NPC, spawn_npc
from server.engine.persistence import init_db, load_player, save_player
from server.engine.skills import can_learn, get_skill, render_skill_tree, render_skills_section
from server.engine.strategy import add_strategy, clear_strategies, list_strategies, remove_strategy
from server.engine.help_registry import send_help, _HELP_TOPICS
from server.engine.inventory_ops import party_inventory_view, do_inventory, do_equip, do_unequip, do_drop, do_pick_up, do_give, do_load_cart, do_unload_cart, auto_assign_item, auto_assign_item_with_message
from server.engine.campfire import do_formation, do_manage
from server.engine.chat import do_say, do_emote, do_shout
from server.engine.environment import carried_light as _carried_light_fn, effective_light as _effective_light_fn, do_time, do_weather, do_light, do_envdetails, do_light_source
from server.engine.survival import party_survival_aggregate, apply_survival_penalties, drain_survival_tick, sitting_stamina_tick, do_survival_status, do_eat, do_drink, do_buffs
from server.engine.world import WorldMap
from server.engine.world_clock import WorldClock
from server.engine.states import State, HANDLER_REGISTRY


def _box(title: str, lines: list[str]) -> str:
    """Format a boxed display."""
    width = 60
    out = [f"\n{'═' * width}", f"  {title}", f"{'─' * width}"]
    out += [f"  {l}" for l in lines]
    out.append("═" * width)
    return "\n".join(out)


class GameSession:
    """Coordinator for a player session — delegates state logic to handlers."""

    def __init__(
        self,
        send_fn,
        world: WorldMap,
        class_defs: dict,
        clock: WorldClock | None = None,
        sessions: dict | None = None
    ) -> None:
        # Core services (injected)
        self._send_raw = send_fn
        self.world = world
        self.class_defs = class_defs
        self.clock: WorldClock | None = clock
        self._sessions: dict = sessions if sessions is not None else {}

        # Player session state
        self.player: Character | None = None
        self.party: list[NPC] = []
        self.current_room_id: str = "town_square"
        self.last_campfire_room_id: str = "test_campfire"
        self._quit: bool = False

        # Shared mechanical state (used across multiple states)
        self._mounted: bool = False
        self._cart_present: bool = False
        self._cart_inventory: list[str] = []
        self._horses_outside: bool = False
        self._was_mounted: bool = False
        self._sitting: bool = False

        # State management
        self._state: State = State.CONNECT
        self._state_data: dict = {}

        # Active combat session (set by CombatHandler)
        self._combat: CombatSession | None = None

        # Pending recruit (used by NavigationHandler)
        self._pending_recruit: str | None = None

        # Clock subscription
        self._weather_cb = None

    # ─────────────────────────────────────────────────────────────────────────
    # Core services used by all handlers
    # ─────────────────────────────────────────────────────────────────────────

    async def send(self, text: str) -> None:
        """Send output to the player."""
        await self._send_raw(text)

    async def broadcast_to_room(self, message: str, exclude_self: bool = True) -> None:
        """Broadcast a message to all players in the current room."""
        room_id = self.current_room_id
        for name, session in self._sessions.items():
            if exclude_self and self.player and name == self.player.name:
                continue
            if session.current_room_id == room_id:
                await session.send(message)

    def save(self) -> None:
        """Save player progress to database."""
        if not self.player:
            return
        data = {
            "character": self.player.to_dict(),
            "party": [npc.to_dict() for npc in self.party],
            "current_room_id": self.current_room_id,
            "last_campfire_room_id": self.last_campfire_room_id,
        }
        save_player(self.player.name, data)

    # ─────────────────────────────────────────────────────────────────────────
    # State management
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        """Current game state."""
        return self._state

    async def transition_to(self, new_state: State, **context) -> None:
        """Transition to a new state with lifecycle hooks."""
        # Exit current state
        await HANDLER_REGISTRY[self._state].on_exit(self)

        # Update state and context
        self._state = new_state
        self._state_data = context

        # Enter new state
        await HANDLER_REGISTRY[new_state].on_enter(self)

    async def handle_input(self, raw: str) -> None:
        """Main entry point — delegates to current state handler."""
        text = raw.strip()
        if not text:
            return

        # Global quit command (works from any state)
        if text.upper() in ("QUIT", "EXIT", "BYE", "LOGOUT"):
            await self._do_quit()
            return

        # Delegate to state handler
        await HANDLER_REGISTRY[self._state].handle(self, text)

    # ─────────────────────────────────────────────────────────────────────────
    # Lifecycle methods
    # ─────────────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize and start the session."""
        init_db()
        await HANDLER_REGISTRY[State.CONNECT].on_enter(self)

    async def _do_quit(self) -> None:
        """Handle player quit."""
        if self.player:
            self.save()
        self._unsubscribe_clock()
        self._quit = True
        await self.send("\n  Farewell, adventurer. Safe travels.\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Clock subscription
    # ─────────────────────────────────────────────────────────────────────────

    def _subscribe_clock(self) -> None:
        """Subscribe to weather broadcasts."""
        if self.clock and not self._weather_cb:
            async def _on_weather(msg: str) -> None:
                if self._state in (State.NAVIGATION, State.CAMPFIRE, State.COMBAT):
                    room = self.world.get_room(self.current_room_id)
                    if room and room.room_type != "underground":
                        await self.send(f"\n  {msg}\n")
                    if self.player:
                        temp_label = "Comfortable"
                        if self.clock and room:
                            temp_label = self.clock.temperature_label(room.room_type, room.base_temp_f)
                        drain_survival_tick(self.player, self.party, self.clock, temp_label)
                        if self._state != State.COMBAT:
                            sitting_stamina_tick(self.player, self.party, self.clock, self._sitting)
            self._weather_cb = _on_weather
            self.clock.subscribe(self._weather_cb)

    def _unsubscribe_clock(self) -> None:
        """Unsubscribe from weather broadcasts."""
        if self.clock and self._weather_cb:
            self.clock.unsubscribe(self._weather_cb)
            self._weather_cb = None

    # ─────────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────────

    async def _load_save(self, save: dict) -> None:
        """Load player save data."""
        self.player = Character.from_dict(save["character"])
        self.party = []
        for nd in save.get("party", []):
            npc = NPC.from_dict(nd)
            self.party.append(npc)
        self.current_room_id = save.get("current_room_id", "town_square")
        self.last_campfire_room_id = save.get("last_campfire_room_id", "test_campfire")
        self._state = State.NAVIGATION

    # ─────────────────────────────────────────────────────────────────────────
    # Help system
    # ─────────────────────────────────────────────────────────────────────────

    async def _send_help(self, topic: str = "") -> None:
        """Send help text to the player."""
        await send_help(self.send, topic)

    # ─────────────────────────────────────────────────────────────────────────
    # Utility skill handler (delegates to existing complex logic)
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_use_skill(self, skill_id: str) -> None:
        """Handle utility skill usage."""
        from server.engine.skills import get_skill

        skill = get_skill(skill_id)
        if skill is None:
            await self.send(f"  Unknown skill '{skill_id}'.\n")
            return

        if skill_id not in self.player.unlocked_skills:
            await self.send(f"  You haven't unlocked '{skill.name}'.\n")
            return

        if skill.use_context != "utility":
            await self.send(f"  '{skill.name}' is a combat skill — use it via strategy.\n")
            return

        if skill.mp_cost > 0 and self.player.mp < skill.mp_cost:
            await self.send(f"  Not enough mana for '{skill.name}'.\n")
            return

        if skill.stamina_cost > 0 and self.player.stamina < skill.stamina_cost:
            await self.send(f"  Not enough stamina for '{skill.name}'.\n")
            return

        if skill.required_items:
            party_inv = list(self.player.inventory)
            for npc in self.party:
                party_inv.extend(npc.inventory)
            for item_id in skill.required_items:
                if item_id not in party_inv:
                    await self.send(f"  You need a {item_id} to use '{skill.name}'.\n")
                    return

        # Deduct costs
        self.player.mp -= skill.mp_cost
        self.player.stamina -= skill.stamina_cost

        # Consume items
        if skill.consumes_item and skill.required_items:
            for item_id in skill.required_items:
                if item_id in self.player.inventory:
                    self.player.inventory.remove(item_id)
                    break
                else:
                    for npc in self.party:
                        if item_id in npc.inventory:
                            npc.inventory.remove(item_id)
                            break

        # Execute effect
        await self._execute_utility_effect(skill)

    async def _execute_utility_effect(self, skill) -> None:
        """Execute utility skill effect."""
        effect = skill.effect_type

        if effect == "unlock_door":
            await self.send("  You probe the lock... but there are no locked exits here.\n")
        elif effect == "reveal_traps":
            await self.send("  You scan the room. You detect no hidden traps.\n")
        elif effect == "provide_light":
            base = self.clock.game_minutes_elapsed if self.clock else 0
            self._arcane_light_until = base + 120
            await self.send("  Arcane light fills the room for 120 game-minutes.\n")
        elif effect == "identify_item":
            await self.send("  You sense the arcane properties of items around you.\n")
        elif effect == "bless_camp":
            self._bless_camp_active = True
            await self.send("  You bless the camp. Next rest will reduce hunger drain by 50%.\n")
        elif effect == "purify_food":
            await self.send("  You purify the food in your pack.\n")
        elif effect == "fortify_party":
            self._fortify_active = True
            await self.send("  You bolster the party's defenses until next battle.\n")
        else:
            await self.send(f"  You use {skill.name}.\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Campfire handlers (delegated to by CampfireHandler)
    # ─────────────────────────────────────────────────────────────────────────

    async def _do_formation(self, args: str) -> None:
        """Show or change formation."""
        await do_formation(self.send, self.player, self.party, args)

    async def _do_manage(self, name: str) -> None:
        """Manage companion strategies."""
        target = await do_manage(self.send, self.player, self.party, name, get_skill, list_strategies)
        if target is not None:
            await self.transition_to(State.STRATEGY, target=target, context="campfire")

    async def _do_show_party(self) -> None:
        """Display party status."""
        lines = []
        lines.append(self.player.stats_summary())
        lines.append("")
        if not self.party:
            lines.append("  (no companions)")
        for i, npc in enumerate(self.party, 1):
            lines.append(f"  [{i}] {npc.stats_summary()}")
            lines.append("")
        h_pct, t_pct, s_pct = party_survival_aggregate(self.player, self.party)
        lines.append(
            f"  Survival  Stamina {s_pct * 100:.0f}%  "
            f"Hunger {h_pct * 100:.0f}%  "
            f"Thirst {t_pct * 100:.0f}%"
        )
        await self.send(_box("PARTY", lines))

    async def _do_learn(self, skill_id: str) -> None:
        """Learn a skill."""
        ok, reason = can_learn(
            self.player.class_type, skill_id,
            self.player.unlocked_skills, self.player.skill_points
        )
        if not ok:
            await self.send(f"  Cannot learn: {reason}\n")
            return
        from server.engine.skills import get_skill_tree
        tree = get_skill_tree(self.player.class_type)
        node = next(n for n in tree if n.skill_id == skill_id)
        self.player.skill_points -= node.unlock_cost
        self.player.unlocked_skills[skill_id] = 1
        skill = get_skill(skill_id)
        await self.send(f"  You learned {skill.name}!\n")

    async def _do_show_modifiers(self) -> None:
        """Show character modifiers."""
        lines = [f"  Modifier Points available: {self.player.modifier_points}", ""]
        for mod_id, meta in MODIFIER_CATALOGUE.items():
            level = self.player.modifiers.get(mod_id, 0)
            bonus_pct = round(level * MODIFIER_BONUS_PER_LEVEL * 100)
            lines.append(f"  {meta['label']:<25} Lv.{level} (+{bonus_pct}%)")
        await self.send(_box("MODIFIERS", lines))

    async def _do_upgrade(self, mod_id: str) -> None:
        """Upgrade a modifier."""
        mod_id = mod_id.strip().lower()
        if mod_id not in MODIFIER_CATALOGUE:
            await self.send(f"  Unknown modifier. Valid: {', '.join(MODIFIER_CATALOGUE.keys())}\n")
            return
        if self.player.modifier_points < 1:
            await self.send("  You have no modifier points.\n")
            return
        self.player.modifier_points -= 1
        self.player.modifiers[mod_id] = self.player.modifiers.get(mod_id, 0) + 1
        meta = MODIFIER_CATALOGUE[mod_id]
        new_level = self.player.modifiers[mod_id]
        new_pct = round(new_level * MODIFIER_BONUS_PER_LEVEL * 100)
        await self.send(
            f"  {meta['label']} improved to Lv.{new_level} (+{new_pct}%).\n"
            f"  Modifier points remaining: {self.player.modifier_points}\n"
        )

    async def _do_dismiss(self, args: str) -> None:
        """Dismiss a companion."""
        name = args.lower().strip()
        for npc in self.party:
            if name in npc.name.lower():
                self.party.remove(npc)
                await self.send(f"  {npc.name} has left your party.\n")
                return
        await self.send(f"  No companion named '{args}' in your party.\n")
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v 2>&1 | tail -50`
Expected: All tests pass

- [ ] **Step 3: Verify file size reduced**

Run: `wc -l /Users/robinsondesouza/Documents/vibing/openCode/projects/ashveil-mud/server/engine/game.py`
Expected: ~250 lines (down from 1,667)

- [ ] **Step 4: Commit**

```bash
git add server/engine/game.py
git commit -m "refactor(game): decompose GameSession into state handlers"
```

---

## Phase 5: Cleanup and Verification

### Task 11: Update State Handler Import Order

**Files:**
- Modify: `server/engine/states/__init__.py`

- [ ] **Step 1: Add proper error handling for missing handlers**

```python
# Add at top of _get_handlers():
"""Lazy-load handlers to avoid circular imports.

Raises:
    ImportError: If any handler module fails to import.
"""
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add server/engine/states/__init__.py
git commit -m "chore(states): add error handling documentation"
```

---

### Task 12: Final Integration Test

**Files:**
- Test: Full workflow test

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests pass

- [ ] **Step 2: Verify line counts**

Run: `find /Users/robinsondesouza/Documents/vibing/openCode/projects/ashveil-mud/server/engine/states -name "*.py" -exec wc -l {} \;`
Expected:
- base.py: ~35 lines
- contexts.py: ~45 lines  
- connect.py: ~40 lines
- creation.py: ~120 lines
- strategy.py: ~80 lines
- campfire.py: ~100 lines
- combat.py: ~140 lines
- navigation.py: ~350 lines
- __init__.py: ~45 lines

- [ ] **Step 3: Document final state**

```bash
# Add summary to git log
git log --oneline -10
```

- [ ] **Step 4: Final commit**

```bash
git commit --allow-empty -m "feat(states): complete GameSession decomposition"
```

---

## Plan Self-Review

**Spec coverage:** All architecture requirements from IMPROVEMENTS.md A1 are addressed:
- ✅ GameSession reduced from 1,667 to ~250 lines
- ✅ 6 state handlers created with clear boundaries
- ✅ O(1) command dispatch in NavigationHandler
- ✅ TypedDict contexts for state-specific data
- ✅ StateHandler protocol for type safety

**Placeholder scan:** No TBDs, TODOs, or incomplete sections.

**Type consistency:** All handler signatures match StateHandler protocol. Context types are consistent.

---

## Success Criteria

After implementation:
1. `server/engine/game.py` is ~250 lines (85% reduction)
2. All existing tests pass without modification
3. New handlers are in `server/engine/states/`
4. State transitions work correctly
5. No regression in gameplay functionality

---

**Plan complete and saved to `/Users/robinsondesouza/Documents/vibing/openCode/projects/ashveil-mud/docs/superpowers/plans/2026-04-12-game-session-decomposition.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
