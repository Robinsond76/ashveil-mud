import pytest
from server.engine.persistence import save_player, load_player, delete_player, init_db


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield
    # Cleanup after tests
    delete_player("testuser")
    delete_player("TestUser")
    delete_player("TESTUSER")


def test_save_and_load_case_insensitive():
    """Names should be normalized to lowercase."""
    save_player("TestUser", {"name": "TestUser", "level": 1})
    
    # Should be able to load with any case
    data_lower = load_player("testuser")
    data_upper = load_player("TESTUSER")
    data_mixed = load_player("TestUser")
    
    assert data_lower is not None
    assert data_upper is not None
    assert data_mixed is not None
    assert data_lower["name"] == "testuser"  # Normalized
    assert data_upper["name"] == "testuser"
    assert data_mixed["name"] == "testuser"


def test_duplicate_names_rejected():
    """Should not allow creating 'Alice' after 'alice' exists."""
    save_player("alice", {"name": "alice", "level": 1})
    
    # Try to save with different case - should overwrite, not create new
    save_player("ALICE", {"name": "ALICE", "level": 2})
    
    # Should only be one record with latest data
    data = load_player("alice")
    assert data["level"] == 2
    assert data["name"] == "alice"  # Normalized


def test_delete_is_case_insensitive():
    """Delete should work with any case."""
    save_player("Bob", {"name": "Bob", "level": 1})
    
    # Delete with different case
    result = delete_player("BOB")
    assert result is True
    
    # Should be gone
    assert load_player("bob") is None
