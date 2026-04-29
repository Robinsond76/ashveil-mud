import pytest
from unittest.mock import MagicMock, patch
from server.engine.combat import CombatSession, Combatant
from server.engine.domain.character import Character
from server.engine.domain.npc import NPC

import os
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "server", "data")

_skill_loaded = False

def _load_skills_once():
    global _skill_loaded
    if not _skill_loaded:
        from server.engine.domain.skills import load_skills
        load_skills(DATA_DIR)
        _skill_loaded = True


class MockChar:
    """Minimal mock for testing status effects."""
    def __init__(self, name, class_type="warrior"):
        self.name = name
        self.class_type = class_type
        self.hp = 100
        self.max_hp = 100
        self.mp = 50
        self.max_mp = 50
        self.is_alive = True
        self.status_effects = {}
        self.unlocked_skills = {}
        self.STR = 12
        self.equipment = {}
        self.action_interval = 1.0
        self.inventory = []
        self.grid_row = -1
        self.grid_col = -1
    
    def roll_damage(self, multiplier=1.0):
        return 10
    
    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.is_alive = False
        return amount
    
    def spell_intensity_bonus(self, damage_type):
        return 0.0


def test_slow_status_only_shown_on_first_apply():
    """Test that 'is now slow' message only appears when status is first applied."""
    _load_skills_once()
    from server.engine.domain.skills import get_skill
    
    # Create mock combatants
    attacker = Combatant(MockChar("Mage", "mage"), is_player_side=True)
    target_char = MockChar("Bandit")
    target = Combatant(target_char, is_player_side=False)
    
    # Create combat session
    send_mock = MagicMock()
    session = CombatSession([attacker.character], [target.character], send_mock)
    
    # Manually call _resolve_skill with frost_bolt twice
    skill_id = "frost_bolt"
    attacker.character.unlocked_skills[skill_id] = 1
    attacker.character.mp = 100
    
    log1 = []
    session._resolve_skill(
        attacker, skill_id, target_char,
        [attacker.character], [target_char], log1
    )
    
    # First application should show "is now slow"
    slow_messages_1 = [m for m in log1 if "is now slow" in m]
    assert len(slow_messages_1) == 1, f"Expected 1 slow message on first apply, got: {slow_messages_1}"
    
    # Apply again (target already has slow)
    log2 = []
    session._resolve_skill(
        attacker, skill_id, target_char,
        [attacker.character], [target_char], log2
    )
    
    # Second application should NOT show "is now slow" again
    slow_messages_2 = [m for m in log2 if "is now slow" in m]
    assert len(slow_messages_2) == 0, f"Expected 0 slow messages on re-apply, got: {slow_messages_2}"
