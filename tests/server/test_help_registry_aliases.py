"""Test that help topics mention their shorthand command aliases."""
from pathlib import Path


def test_aliases_in_help_text():
    """Verify help topics mention their shorthand forms."""
    # Import after ensuring we're in the right path
    import sys
    sys.path.insert(0, '/Users/robinsondesouza/Documents/vibing/openCode/projects/ashveil-mud/.worktrees/command-aliases')
    from server.engine.display.help_data import _HELP_TOPICS
    
    # Map of primary command to expected shorthand notation in help
    expected_aliases_in_help = {
        "LOOK": ["L"],
        "EXAMINE": ["X"],
        "EQUIP": ["EQ"],
        "UNEQUIP": ["UNEQ"],
        "ATTACK": ["K"],
        "PARTY": ["P"],
        "SKILLS": ["SK"],
        "STATUS": ["SS"],
        "BUFFS": ["B"],
        "TALK": ["T"],
        "DISMISS": ["DIS"],
        "SAVE": ["SV"],
        "SAY": ["'"],
        "TIME": ["TI"],
        "WEATHER": ["WEA"],
        "UPGRADE": ["UPG"],
        "LEARN": ["LRN"],
        "DRINK": ["DR"],
        "EAT": ["EA"],
        "GIVE": ["GIV"],
        "HORSES": ["HOR"],
    }
    
    for command, aliases in expected_aliases_in_help.items():
        help_text = _HELP_TOPICS.get(command, "")
        help_upper = help_text.upper()
        
        # Check that at least one alias form appears
        found_alias = False
        for alias in aliases:
            # Look for patterns like "(or X)" or "Usage: COMMAND (or X)" or "COMMAND / X"
            # Check both original case and uppercase since help text varies
            alias_upper = alias.upper()
            # Check for various patterns where alias might appear
            patterns = [
                f"(or {alias})",
                f"(OR {alias_upper})",
                f"/ {alias}",
                f"/ {alias_upper}",
                f"(or {alias} ",  # e.g., "(or X <target>)"
                f"(OR {alias_upper} ",
            ]
            if any(p in help_upper for p in patterns):
                found_alias = True
                break
        
        assert found_alias, f"Help for {command} should mention aliases {aliases}"
