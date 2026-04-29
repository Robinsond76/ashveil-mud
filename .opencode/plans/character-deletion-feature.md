# Character Deletion Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the ability for players to delete their characters, available at the login screen with confirmation.

**Architecture:** Extend the connect state handler to recognize a DELETE command, which will prompt for confirmation before permanently removing the character from the database.

**Tech Stack:** Python (backend), SQLite persistence layer already has `delete_player()` function

---

## Research Notes

**Existing Infrastructure:**
- `server/engine/persistence.py` already has `delete_player(name)` function (line 101-110)
- `server/engine/states/connect.py` handles login flow - this is where to add DELETE
- `server/engine/help_registry.py` contains all HELP topics - need to add DELETE help
- `GETTING_STARTED.md` documents character creation - should document deletion too

**Current Login Flow:**
1. Player enters name at "Enter your character name (new or existing):" prompt
2. If name exists → load save and enter game
3. If name doesn't exist → go to character creation wizard

**Proposed DELETE Flow:**
1. Player types "DELETE <name>" at login prompt
2. System confirms character exists
3. System asks "Are you sure? Type the character name again to confirm deletion:"
4. Player types name again to confirm
5. Character is deleted, success message shown
6. Returns to login prompt

---

## Task 1: Backend - Add DELETE Command to Connect State

**Files:**
- Modify: `server/engine/states/connect.py` - Add DELETE command handling

---

- [ ] **Step 1: Add pending deletion tracking to connect handler**

Modify the `ConnectHandler` class to track deletion state. Add after imports:

```python
class ConnectHandler:
    """Handles player login and account creation flow."""

    async def on_enter(self, session: GameSession) -> None:
        """Display welcome message and prompt for name."""
        await session.send(
            "\n" + "═" * 60 + "\n"
            "  Welcome to ASHVEIL MUD\n"
            "  A text-based fantasy world\n" +
            "═" * 60 + "\n"
            "\nEnter your character name (new or existing):\n"
            "\n  To delete a character, type: DELETE <name>\n> "
        )
```

- [ ] **Step 2: Add DELETE command handling in connect handler**

Modify the `handle()` method to check for DELETE command before normal login:

```python
async def handle(self, session: GameSession, text: str) -> None:
    """Process login name or deletion command."""
    name = text.strip()
    upper = name.upper()

    if upper in ("HELP", "?"):
        await session._send_help("")
        return

    # Handle deletion confirmation if pending
    ctx = session._state_data
    if ctx.get("pending_deletion"):
        await self._handle_deletion_confirmation(session, name)
        return

    # Handle DELETE command
    if upper.startswith("DELETE "):
        char_name = name[7:].strip()  # Remove "DELETE " prefix
        await self._initiate_deletion(session, char_name)
        return

    # Normal login flow
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
        # Trigger look after transition
        from server.engine.states.navigation import NavigationHandler
        nav = NavigationHandler()
        await nav._do_look(session)
    else:
        # New character - go to creation wizard
        await session.transition_to(
            State.CREATION,
            step="class",
            pending_name=name
        )
```

- [ ] **Step 3: Add deletion initiation method**

Add new method `_initiate_deletion()`:

```python
async def _initiate_deletion(self, session: GameSession, char_name: str) -> None:
    """Start the character deletion process."""
    from server.engine.persistence import load_player

    if not char_name:
        await session.send("  Usage: DELETE <character_name>\n> ")
        return

    if not char_name.isalpha() or len(char_name) < 2 or len(char_name) > 20:
        await session.send("  Name must be 2–20 letters only.\n> ")
        return

    # Check if character exists
    save = load_player(char_name)
    if not save:
        await session.send(f"  Character '{char_name}' not found.\n> ")
        return

    # Store pending deletion in session state
    session._state_data["pending_deletion"] = char_name.lower()

    await session.send(
        f"\n  ⚠️  WARNING: You are about to DELETE '{char_name}'\n"
        f"  This action cannot be undone!\n"
        f"\n  To confirm, type the character name again:\n"
        f"  (or type CANCEL to abort)\n> "
    )
```

- [ ] **Step 4: Add deletion confirmation method**

Add new method `_handle_deletion_confirmation()`:

```python
async def _handle_deletion_confirmation(self, session: GameSession, confirmation: str) -> None:
    """Handle deletion confirmation or cancellation."""
    from server.engine.persistence import delete_player

    ctx = session._state_data
    char_name = ctx.get("pending_deletion", "")

    upper = confirmation.upper()

    if upper == "CANCEL":
        ctx.pop("pending_deletion", None)
        await session.send("  Deletion cancelled.\n\nEnter your character name:\n> ")
        return

    # Check if confirmation matches (case-insensitive)
    if confirmation.lower() != char_name:
        ctx.pop("pending_deletion", None)
        await session.send(
            f"  Names did not match. Deletion cancelled.\n"
            f"\nEnter your character name:\n> "
        )
        return

    # Delete the character
    deleted = delete_player(char_name)
    ctx.pop("pending_deletion", None)

    if deleted:
        await session.send(
            f"\n  ✓ Character '{char_name}' has been deleted.\n"
            f"\nEnter your character name:\n> "
        )
    else:
        await session.send(
            f"\n  Error: Could not delete '{char_name}'.\n"
            f"\nEnter your character name:\n> "
        )
```

- [ ] **Step 5: Run tests to verify no regressions**

```bash
/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/ -v --tb=short
```

Expected: All 623 tests pass

- [ ] **Step 6: Commit**

```bash
git add server/engine/states/connect.py
git commit -m "feat: add character deletion command at login"
```

---

## Task 2: Add Help Documentation for DELETE Command

**Files:**
- Modify: `server/engine/help_registry.py` - Add DELETE help topic
- Modify: `server/engine/help_registry.py` - Add DELETE to general help list

---

- [ ] **Step 1: Add DELETE help topic**

Add to `_HELP_TOPICS` dictionary (find a good alphabetical position, near other meta commands):

```python
"DELETE": _box("HELP: DELETE", [
    "  Delete a character permanently.",
    "  Usage: DELETE <character_name>",
    "",
    "  Available at the login screen only.",
    "  You will be asked to confirm by typing the name again.",
    "  This action cannot be undone!",
    "",
    "  Examples:",
    "    DELETE aldric",
    "",
    "  To cancel confirmation, type: CANCEL",
    "",
    "  See also: QUIT, EXIT, LOGOUT",
]),
```

- [ ] **Step 2: Update general help to mention DELETE**

Find the general help entry (usually "" or at the top) and add reference to DELETE command:

Look for the section that lists available commands and add DELETE to the list.

- [ ] **Step 3: Run tests**

```bash
/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/ -v --tb=short
```

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add server/engine/help_registry.py
git commit -m "docs: add DELETE command to help system"
```

---

## Task 3: Update Getting Started Documentation

**Files:**
- Modify: `GETTING_STARTED.md` - Add character deletion section

---

- [ ] **Step 1: Find appropriate location in GETTING_STARTED.md**

Look for the "Creating a Character" section and add a new subsection after it about deleting characters.

- [ ] **Step 2: Add character deletion documentation**

Add a new section after the character creation section:

```markdown
---

## Deleting a Character

To permanently delete a character, use the **DELETE** command at the login screen.

### Step 1 — Initiate Deletion

At the welcome prompt, type DELETE followed by your character's name:

```
> DELETE aldric
```

### Step 2 — Confirm Deletion

You will be asked to confirm:

```
⚠️  WARNING: You are about to DELETE 'aldric'
  This action cannot be undone!

  To confirm, type the character name again:
  (or type CANCEL to abort)
> 
```

Type the exact character name again to confirm, or type **CANCEL** to abort.

### Important Notes

- **Permanent**: Deleted characters cannot be recovered
- **Login only**: DELETE only works at the welcome screen, not while playing
- **Case-insensitive**: Works with any capitalization
- **No login required**: You can delete without logging in first

```

- [ ] **Step 3: Commit**

```bash
git add GETTING_STARTED.md
git commit -m "docs: add character deletion instructions to getting started guide"
```

---

## Task 4: Create Test for Deletion Feature

**Files:**
- Create: `tests/test_character_deletion.py`

---

- [ ] **Step 1: Write test for deletion flow**

```python
"""Tests for character deletion feature."""

import pytest

from server.engine.states.connect import ConnectHandler
from server.engine.persistence import save_player, load_player, delete_player
from server.engine.character import Character


@pytest.fixture
def sample_character_data():
    """Create sample save data for testing."""
    char = Character(
        name="testdelete",
        class_type="warrior",
        level=1,
        xp=0,
        hp=100,
        max_hp=100,
        mp=50,
        max_mp=50,
    )
    return {
        "character": char.to_dict(),
        "party": [],
        "current_room_id": "town_square",
        "last_campfire_room_id": "test_campfire",
    }


@pytest.mark.asyncio
async def test_delete_initiate_existing_character(mock_session, sample_character_data):
    """Test DELETE command finds existing character."""
    # Setup: save a character
    save_player("testdelete", sample_character_data)
    
    handler = ConnectHandler()
    mock_session._state_data = {}
    
    # Initiate deletion
    await handler._initiate_deletion(mock_session, "testdelete")
    
    # Should set pending_deletion
    assert mock_session._state_data.get("pending_deletion") == "testdelete"
    
    # Cleanup
    delete_player("testdelete")


@pytest.mark.asyncio
async def test_delete_initiate_nonexistent_character(mock_session):
    """Test DELETE command handles non-existent character."""
    handler = ConnectHandler()
    mock_session._state_data = {}
    
    # Try to delete non-existent character
    await handler._initiate_deletion(mock_session, "nonexistent123")
    
    # Should not set pending_deletion
    assert "pending_deletion" not in mock_session._state_data


@pytest.mark.asyncio
async def test_delete_confirmation_success(mock_session, sample_character_data):
    """Test successful deletion with correct confirmation."""
    # Setup: save a character
    save_player("testdelete", sample_character_data)
    
    handler = ConnectHandler()
    mock_session._state_data = {"pending_deletion": "testdelete"}
    
    # Confirm deletion
    await handler._handle_deletion_confirmation(mock_session, "testdelete")
    
    # Character should be deleted
    assert load_player("testdelete") is None
    assert "pending_deletion" not in mock_session._state_data


@pytest.mark.asyncio
async def test_delete_confirmation_wrong_name(mock_session, sample_character_data):
    """Test deletion cancelled with wrong confirmation name."""
    # Setup: save a character
    save_player("testdelete", sample_character_data)
    
    handler = ConnectHandler()
    mock_session._state_data = {"pending_deletion": "testdelete"}
    
    # Wrong confirmation
    await handler._handle_deletion_confirmation(mock_session, "wrongname")
    
    # Character should still exist
    assert load_player("testdelete") is not None
    assert "pending_deletion" not in mock_session._state_data
    
    # Cleanup
    delete_player("testdelete")


@pytest.mark.asyncio
async def test_delete_confirmation_cancel(mock_session, sample_character_data):
    """Test deletion cancelled with CANCEL command."""
    # Setup: save a character
    save_player("testdelete", sample_character_data)
    
    handler = ConnectHandler()
    mock_session._state_data = {"pending_deletion": "testdelete"}
    
    # Cancel deletion
    await handler._handle_deletion_confirmation(mock_session, "CANCEL")
    
    # Character should still exist
    assert load_player("testdelete") is not None
    assert "pending_deletion" not in mock_session._state_data
    
    # Cleanup
    delete_player("testdelete")


@pytest.mark.asyncio
async def test_delete_case_insensitive(mock_session, sample_character_data):
    """Test deletion works with different capitalizations."""
    # Setup: save a character
    save_player("TestDelete", sample_character_data)
    
    handler = ConnectHandler()
    mock_session._state_data = {"pending_deletion": "testdelete"}
    
    # Confirm with different capitalization
    await handler._handle_deletion_confirmation(mock_session, "TESTDELETE")
    
    # Character should be deleted
    assert load_player("testdelete") is None
```

- [ ] **Step 2: Run the new tests**

```bash
/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/test_character_deletion.py -v
```

Expected: All 5 tests pass

- [ ] **Step 3: Run full test suite**

```bash
/Users/robinsondesouza/Library/Python/3.9/bin/pytest tests/ -v --tb=short
```

Expected: All tests pass (623 + 5 new = 628)

- [ ] **Step 4: Commit**

```bash
git add tests/test_character_deletion.py
git commit -m "test: add tests for character deletion feature"
```

---

## Summary

**Task 1:** Backend adds DELETE command handling in connect state with confirmation
**Task 2:** Help system documents the DELETE command
**Task 3:** GETTING_STARTED.md explains how to delete characters
**Task 4:** Test coverage for deletion flow

**Total files modified:** 3 (connect.py, help_registry.py, GETTING_STARTED.md)
**New files:** 1 (test_character_deletion.py)
**New methods:** 2 (_initiate_deletion, _handle_deletion_confirmation)

**User Flow:**
1. At login screen: `DELETE <name>`
2. System shows warning and asks for confirmation
3. User types name again to confirm, or CANCEL to abort
4. Character permanently deleted
5. Returns to login prompt