"""
Tests for Improvement 05 — Config & Validation.

Covers:
  - validate_room_data() exit reference checks
  - save_player() schema version stamping
  - load_player() backward-compatibility with old saves
"""
import pytest


# ── Room validation ───────────────────────────────────────────────────────────


def test_validate_rooms_catches_bad_exit():
    """Room with an exit pointing to a non-existent room should surface an error."""
    from server.engine.world import validate_room_data

    bad_rooms = {
        "room_a": {
            "id": "room_a",
            "exits": {"north": "room_that_does_not_exist"},
        }
    }

    errors = validate_room_data(bad_rooms)
    assert len(errors) > 0
    assert "room_that_does_not_exist" in errors[0]


def test_validate_rooms_accepts_valid_data():
    """Fully valid room data should return no errors."""
    from server.engine.world import validate_room_data

    good_rooms = {
        "room_a": {
            "id": "room_a",
            "exits": {"south": "room_b"},
        },
        "room_b": {
            "id": "room_b",
            "exits": {"north": "room_a"},
        },
    }

    errors = validate_room_data(good_rooms)
    assert errors == []


def test_validate_rooms_empty_dict():
    """Empty room dict should return no errors."""
    from server.engine.world import validate_room_data

    errors = validate_room_data({})
    assert errors == []


def test_validate_rooms_no_exits():
    """Room with no exits field should not raise and return no errors."""
    from server.engine.world import validate_room_data

    rooms = {
        "room_a": {"id": "room_a"},
    }
    errors = validate_room_data(rooms)
    assert errors == []


def test_validate_rooms_multiple_bad_exits():
    """Each invalid exit should produce a separate error entry."""
    from server.engine.world import validate_room_data

    rooms = {
        "room_a": {
            "id": "room_a",
            "exits": {"north": "missing_1", "east": "missing_2"},
        }
    }
    errors = validate_room_data(rooms)
    assert len(errors) == 2


# ── Save schema versioning ────────────────────────────────────────────────────


def test_save_includes_schema_version(tmp_path, monkeypatch):
    """save_player should stamp _schema_version into the saved blob."""
    import server.engine.persistence as pers
    from server.config import SAVE_SCHEMA_VERSION

    # Redirect the DB to a temp file for this test
    from sqlalchemy import create_engine
    from server.engine.persistence import Base, PlayerSave
    tmp_db = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(tmp_db, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    monkeypatch.setattr(pers, "_engine", engine)

    pers.save_player("schema_test", {"name": "hero", "class_type": "warrior"})
    data = pers.load_player("schema_test")

    assert data is not None
    assert data.get("_schema_version") == SAVE_SCHEMA_VERSION


def test_load_player_without_schema_version_is_backward_compatible(tmp_path, monkeypatch):
    """Loading a save that has no _schema_version should still succeed (backward compat)."""
    import json
    import server.engine.persistence as pers
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from server.engine.persistence import Base, PlayerSave

    tmp_db = f"sqlite:///{tmp_path}/test2.db"
    engine = create_engine(tmp_db, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(pers, "_engine", engine)

    # Manually insert a save blob without _schema_version
    old_blob = json.dumps({"name": "old_hero", "class_type": "mage"})
    with Session(engine) as session:
        session.add(PlayerSave(name="old_hero", save_data=old_blob))
        session.commit()

    data = pers.load_player("old_hero")
    assert data is not None
    assert data["name"] == "old_hero"
