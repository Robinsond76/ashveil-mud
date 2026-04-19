"""Tests for command aliases in NavigationHandler."""
import pytest
from server.engine.states.navigation import NavigationHandler


# Define all expected aliases and their primary commands
EXPECTED_ALIASES = {
    "l": "look",
    "x": "examine",
    "eq": "equip",
    "uneq": "unequip",
    "k": "attack",
    "p": "party",
    "sk": "skills",
    "ss": "status",
    "b": "buffs",
    "t": "talk",
    "dis": "dismiss",
    "sv": "save",
    "'": "say",
    "ti": "time",
    "wea": "weather",
    "upg": "upgrade",
    "lrn": "learn",
    "dr": "drink",
    "ea": "eat",
    "giv": "give",
    "hor": "horses",
}


def test_all_aliases_exist():
    """Verify all expected command aliases are registered."""
    handler = NavigationHandler()
    
    for alias, primary in EXPECTED_ALIASES.items():
        assert alias in handler.commands, f"Alias '{alias}' not found in commands dict"
        primary_handler = handler.commands.get(primary)
        alias_handler = handler.commands.get(alias)
        assert alias_handler == primary_handler, f"Alias '{alias}' should map to same handler as '{primary}'"


def test_no_conflicting_aliases():
    """Ensure no alias conflicts with existing commands."""
    handler = NavigationHandler()
    
    # These are the built-in directional commands that must not be overridden
    reserved = {"n", "s", "e", "w", "u", "d", "go"}
    
    for reserved_cmd in reserved:
        assert reserved_cmd not in EXPECTED_ALIASES, f"'{reserved_cmd}' is reserved and cannot be an alias"
