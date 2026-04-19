"""Tests for the NavigationHandler state."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from server.engine.states.navigation import NavigationHandler


@pytest.mark.asyncio
async def test_look_command_alias_l():
    """Test that 'l' works as an alias for 'look'."""
    handler = NavigationHandler()
    
    # Verify 'l' is in commands dict
    assert "l" in handler.commands
    assert handler.commands["l"] == handler._do_look
