"""
Phase 2 — Survival Stats: combat penalty + stamina drain tests (Phase D).
Tests that CombatSession accepts and applies survival_multiplier,
and that stamina drains on combat actions.
"""
import pytest
from unittest.mock import AsyncMock

from server.engine.character import Character
from server.engine.combat import CombatSession, CombatState
from server.engine.npc import NPC


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_warrior(name="Hero", hp=100):
    c = Character(name=name, class_type="warrior")
    c.max_hp = hp
    c.hp = hp
    c.STR = 10
    return c


def make_monster(name="Goblin", hp=50):
    n = NPC.__new__(NPC)
    n.name = name
    n.class_type = "warrior"
    n.hp = hp
    n.max_hp = hp
    n.STR = 5
    n.DEX = 5
    n.INT = 5
    n.WIS = 5
    n.CON = 5
    n.AGI = 5
    n.mp = 0
    n.max_mp = 0
    n.equipment = {s: None for s in ["weapon", "helmet", "chest", "legs", "boots", "offhand"]}
    n.inventory = []
    n.modifiers = {}
    n.unlocked_skills = {}
    n.strategies = []
    n.grid_row = -1
    n.grid_col = -1
    n.darkvision = False
    n.status_effects = {}
    n.loot_table = []
    n.xp_reward = 0
    n.template_id = "goblin"
    return n


# ── Phase D: CombatSession survival_multiplier attribute ─────────────────────

def test_combat_session_accepts_survival_multiplier():
    send = AsyncMock()
    player = make_warrior()
    enemy = make_monster()
    session = CombatSession(
        player_party=[player],
        enemy_party=[enemy],
        send=send,
        survival_multiplier=0.75,
    )
    assert session.survival_multiplier == 0.75


def test_combat_session_default_survival_multiplier_is_1():
    send = AsyncMock()
    player = make_warrior()
    enemy = make_monster()
    session = CombatSession(
        player_party=[player],
        enemy_party=[enemy],
        send=send,
    )
    assert session.survival_multiplier == 1.0


def test_player_damage_is_scaled_by_survival_multiplier():
    """With multiplier=0, player deals 0 (or minimum) damage to verify the hook fires."""
    import random
    random.seed(42)

    send = AsyncMock()
    attacker = make_warrior("Hero", hp=200)
    target = make_monster("Goblin", hp=10000)  # huge HP so it can't die

    session = CombatSession(
        player_party=[attacker],
        enemy_party=[target],
        send=send,
        survival_multiplier=0.0,
    )
    log: list[str] = []
    # Directly call the resolve path
    from server.engine.combat import Combatant
    actor_c = next(c for c in session.player_combatants if c.name == "Hero")
    session._resolve_attack(attacker, target, log, is_player_side=True)
    # Either capped at 1 (min damage) or 0 — the multiplier was applied
    # We just need the multiplier to have been acknowledged; target HP should
    # be very close to original (significantly less damage than multiplier=1 would give)
    assert target.hp >= 9990  # near max — multiplied by 0.0 → only 1 min dmg allowed


def test_enemy_damage_not_scaled_by_survival_multiplier():
    """Enemy attacks are NOT penalised by the player's survival state."""
    import random
    random.seed(42)

    send = AsyncMock()
    player = make_warrior("Hero", hp=10000)
    enemy = make_monster("Goblin", hp=200)

    session = CombatSession(
        player_party=[player],
        enemy_party=[enemy],
        send=send,
        survival_multiplier=0.0,
    )
    log: list[str] = []
    session._resolve_attack(enemy, player, log, is_player_side=False)
    # Enemy damage should NOT be zeroed — player HP should have dropped
    assert player.hp < 10000


# ── Phase D: stamina drain from combat tick ───────────────────────────────────

def test_flee_action_drains_5_stamina_from_player_characters():
    """After a player-side FLEE, stamina should be deducted."""
    import asyncio

    send_msgs: list[str] = []
    async def send_fn(msg: str): send_msgs.append(msg)

    warrior = make_warrior("Hero", hp=200)
    warrior.stamina = 50.0
    warrior.strategies = [{"priority": 1, "condition": "ALWAYS", "action": "FLEE", "target": "any"}]
    enemy = make_monster("Goblin", hp=200)

    session = CombatSession(
        player_party=[warrior],
        enemy_party=[enemy],
        send=send_fn,
        survival_multiplier=1.0,
    )
    log: list[str] = []
    from server.engine.combat import Combatant
    actor_c = next(c for c in session.player_combatants if c.name == "Hero")
    session._do_action(actor_c, log)
    # After flee attempt, stamina should be reduced by 5
    assert warrior.stamina == 45.0
