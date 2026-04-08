"""
Persistence layer — SQLAlchemy + SQLite.

Stores player saves as a single JSON blob per player name.
Swapping to Postgres requires only changing DATABASE_URL.

Public interface:
  init_db()                → create tables
  save_player(name, data)  → upsert save data (with schema version + retry)
  load_player(name)        → dict | None  (warns if schema version is old)
  delete_player(name)      → remove save
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from server.config import DATABASE_URL, SAVE_SCHEMA_VERSION

logger = logging.getLogger(__name__)

_MAX_SAVE_RETRIES = 3
_RETRY_DELAY_SECONDS = 0.1

_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class PlayerSave(Base):
    __tablename__ = "player_saves"

    name = Column(String(64), primary_key=True)
    save_data = Column(Text, nullable=False)   # JSON blob
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    Base.metadata.create_all(_engine)


def save_player(name: str, data: dict) -> None:
    save_data = dict(data)
    save_data["_schema_version"] = SAVE_SCHEMA_VERSION

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_SAVE_RETRIES + 1):
        try:
            with Session(_engine) as session:
                record = session.get(PlayerSave, name)
                blob = json.dumps(save_data)
                if record is None:
                    record = PlayerSave(name=name, save_data=blob)
                    session.add(record)
                else:
                    record.save_data = blob
                    record.updated_at = datetime.now(timezone.utc)
                session.commit()
            return
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "save_player attempt %d/%d for '%s' failed: %s",
                attempt, _MAX_SAVE_RETRIES, name, exc,
            )
            if attempt < _MAX_SAVE_RETRIES:
                time.sleep(_RETRY_DELAY_SECONDS)

    logger.error("All save attempts failed for '%s'", name)
    raise last_exc  # type: ignore[misc]


def load_player(name: str) -> dict | None:
    with Session(_engine) as session:
        record = session.get(PlayerSave, name)
        if record is None:
            return None
        data = json.loads(record.save_data)
        version = data.get("_schema_version", 0)
        if version < SAVE_SCHEMA_VERSION:
            logger.warning(
                "Save '%s' has schema version %d (current: %d). "
                "Migration may be needed.",
                name, version, SAVE_SCHEMA_VERSION,
            )
        return data


def delete_player(name: str) -> bool:
    with Session(_engine) as session:
        record = session.get(PlayerSave, name)
        if record is None:
            return False
        session.delete(record)
        session.commit()
        return True
