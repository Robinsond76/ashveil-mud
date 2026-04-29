"""Tests for character deletion feature at login screen."""
import pytest
from server.engine.persistence import save_player, load_player, delete_player, init_db
from server.engine.states.connect import ConnectHandler
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def clean_db():
    """Clean up test characters before and after each test."""
    init_db()
    delete_player("testdelete")
    delete_player("TestDelete")
    delete_player("TESTDELETE")
    yield
    delete_player("testdelete")
    delete_player("TestDelete")
    delete_player("TESTDELETE")


@pytest.fixture
def mock_session():
    """Create a mock GameSession with required attributes."""
    session = MagicMock()
    session.send = AsyncMock()
    session._state_data = {}
    session.player = None
    session._load_save = AsyncMock()
    session._subscribe_clock = MagicMock()
    session._send_help = AsyncMock()
    session.transition_to = AsyncMock()
    return session


@pytest.fixture
def handler():
    """Create a ConnectHandler instance."""
    return ConnectHandler()


@pytest.mark.asyncio
async def test_initiate_deletion_existing_character(handler, mock_session):
    """Test initiating deletion of an existing character shows confirmation prompt."""
    # Create a test character
    test_save = {"name": "testdelete", "level": 5, "class": "warrior"}
    save_player("testdelete", test_save)
    
    # Verify character exists
    assert load_player("testdelete") is not None
    
    # Initiate deletion
    await handler._initiate_deletion(mock_session, "testdelete")
    
    # Check that pending_deletion was set
    assert mock_session._state_data.get("pending_deletion") == "testdelete"
    
    # Verify warning message was sent
    calls = mock_session.send.call_args_list
    warning_found = any("WARNING" in str(call) and "PERMANENTLY" in str(call) for call in calls)
    assert warning_found, "Expected warning message about permanent deletion"
    
    # Verify confirmation prompt was sent
    confirmation_found = any("confirm" in str(call).lower() or "type the name" in str(call).lower() for call in calls)
    assert confirmation_found, "Expected confirmation prompt"


@pytest.mark.asyncio
async def test_initiate_deletion_nonexistent_character(handler, mock_session):
    """Test initiating deletion of a non-existent character shows error."""
    # Ensure character doesn't exist
    delete_player("nonexistentchar")
    
    # Try to initiate deletion
    await handler._initiate_deletion(mock_session, "nonexistentchar")
    
    # Check that pending_deletion was NOT set
    assert mock_session._state_data.get("pending_deletion") is None
    
    # Verify error message was sent
    calls = mock_session.send.call_args_list
    error_found = any("not found" in str(call).lower() or "does not exist" in str(call).lower() or "no character" in str(call).lower() for call in calls)
    assert error_found, f"Expected 'not found' error message, got: {calls}"
    
    # Verify prompt was sent to try again
    prompt_found = any(">" in str(call) or "try again" in str(call).lower() for call in calls)
    assert prompt_found, "Expected retry prompt"


@pytest.mark.asyncio
async def test_confirm_deletion_with_correct_name(handler, mock_session):
    """Test confirming deletion with correct character name deletes the character."""
    # Create a test character
    test_save = {"name": "testdelete", "level": 5, "class": "warrior"}
    save_player("testdelete", test_save)
    
    # Set up pending deletion
    mock_session._state_data["pending_deletion"] = "testdelete"
    
    # Confirm deletion with correct name
    await handler._handle_deletion_confirmation(mock_session, "testdelete")
    
    # Verify character was deleted
    assert load_player("testdelete") is None
    
    # Verify success message was sent
    calls = mock_session.send.call_args_list
    success_found = any("deleted" in str(call).lower() and "success" in str(call).lower() for call in calls)
    assert success_found, f"Expected success message, got: {calls}"
    
    # Verify pending_deletion was cleared
    assert mock_session._state_data.get("pending_deletion") is None
    
    # Verify returned to login prompt
    welcome_found = any("welcome" in str(call).lower() or "enter your character name" in str(call).lower() for call in calls)
    assert welcome_found, "Expected welcome/login prompt after deletion"


@pytest.mark.asyncio
async def test_cancel_deletion_with_cancel_command(handler, mock_session):
    """Test that typing CANCEL aborts the deletion process."""
    # Set up pending deletion
    mock_session._state_data["pending_deletion"] = "testdelete"
    
    # Cancel deletion
    await handler._handle_deletion_confirmation(mock_session, "CANCEL")
    
    # Verify pending_deletion was cleared
    assert mock_session._state_data.get("pending_deletion") is None
    
    # Verify cancellation message was sent
    calls = mock_session.send.call_args_list
    cancel_found = any("cancel" in str(call).lower() for call in calls)
    assert cancel_found, f"Expected cancellation message, got: {calls}"
    
    # Verify returned to login prompt
    prompt_found = any("enter your character name" in str(call).lower() or "welcome" in str(call).lower() for call in calls)
    assert prompt_found, "Expected login prompt after cancellation"


@pytest.mark.asyncio
async def test_wrong_confirmation_name_cancels_deletion(handler, mock_session):
    """Test that typing wrong character name cancels deletion."""
    # Create a test character (so it exists, but wrong name provided)
    test_save = {"name": "testdelete", "level": 5, "class": "warrior"}
    save_player("testdelete", test_save)
    
    # Set up pending deletion
    mock_session._state_data["pending_deletion"] = "testdelete"
    
    # Try to confirm with wrong name
    await handler._handle_deletion_confirmation(mock_session, "wrongname")
    
    # Verify character was NOT deleted
    assert load_player("testdelete") is not None
    
    # Verify pending_deletion was cleared
    assert mock_session._state_data.get("pending_deletion") is None
    
    # Verify error/cancellation message was sent
    calls = mock_session.send.call_args_list
    mismatch_found = any("not match" in str(call).lower() or "cancel" in str(call).lower() or "abort" in str(call).lower() for call in calls)
    assert mismatch_found, f"Expected mismatch/cancellation message, got: {calls}"
    
    # Verify returned to login prompt
    prompt_found = any("enter your character name" in str(call).lower() or "welcome" in str(call).lower() for call in calls)
    assert prompt_found, "Expected login prompt after failed confirmation"


@pytest.mark.asyncio
async def test_case_insensitive_confirmation(handler, mock_session):
    """Test that character name confirmation is case-insensitive."""
    # Create a test character
    test_save = {"name": "testdelete", "level": 5, "class": "warrior"}
    save_player("testdelete", test_save)
    
    # Set up pending deletion with lowercase
    mock_session._state_data["pending_deletion"] = "testdelete"
    
    # Confirm with different case (uppercase)
    await handler._handle_deletion_confirmation(mock_session, "TESTDELETE")
    
    # Verify character was deleted (case insensitive match)
    assert load_player("testdelete") is None
    assert load_player("TestDelete") is None
    
    # Verify success message was sent
    calls = mock_session.send.call_args_list
    success_found = any("deleted" in str(call).lower() and "success" in str(call).lower() for call in calls)
    assert success_found, f"Expected success message, got: {calls}"


@pytest.mark.asyncio
async def test_delete_command_in_handle_method(handler, mock_session):
    """Test that DELETE command is recognized in handle() method."""
    # Create a test character
    test_save = {"name": "testdelete", "level": 5, "class": "warrior"}
    save_player("testdelete", test_save)
    
    # Send DELETE command through handle
    await handler.handle(mock_session, "DELETE testdelete")
    
    # Check that pending_deletion was set (indicating _initiate_deletion was called)
    assert mock_session._state_data.get("pending_deletion") == "testdelete"


@pytest.mark.asyncio
async def test_pending_deletion_check_in_handle(handler, mock_session):
    """Test that handle() checks for pending_deletion and routes to confirmation."""
    # Create a test character
    test_save = {"name": "testdelete", "level": 5, "class": "warrior"}
    save_player("testdelete", test_save)
    
    # Set up pending deletion
    mock_session._state_data["pending_deletion"] = "testdelete"
    
    # Send confirmation through handle
    await handler.handle(mock_session, "testdelete")
    
    # Verify character was deleted (indicating _handle_deletion_confirmation was called)
    assert load_player("testdelete") is None


@pytest.mark.asyncio
async def test_welcome_message_includes_delete_hint(handler, mock_session):
    """Test that on_enter welcome message includes DELETE command hint."""
    await handler.on_enter(mock_session)
    
    # Check that welcome message includes DELETE hint
    calls = mock_session.send.call_args_list
    welcome_text = " ".join([str(call) for call in calls])
    
    delete_hint_found = "delete" in welcome_text.lower() and "delete <name>" in welcome_text.lower()
    assert delete_hint_found, f"Expected DELETE hint in welcome message, got: {welcome_text}"
