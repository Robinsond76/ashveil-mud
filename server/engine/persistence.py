"""
Persistence layer — SQLAlchemy + SQLite.

Stores player saves as a single JSON blob per player name.
Swapping to Postgres requires only changing DATABASE_URL.

Public interface:
  init_db()                → create tables
  save_player(name, data)  → upsert save data
  load_player(name)        → dict | None
  delete_player(name)      → remove save
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from server.config import DATABASE_URL

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
    with Session(_engine) as session:
        record = session.get(PlayerSave, name)
        blob = json.dumps(data)
        if record is None:
            record = PlayerSave(name=name, save_data=blob)
            session.add(record)
        else:
            record.save_data = blob
            record.updated_at = datetime.now(timezone.utc)
        session.commit()


def load_player(name: str) -> dict | None:
    with Session(_engine) as session:
        record = session.get(PlayerSave, name)
        if record is None:
            return None
        return json.loads(record.save_data)


def delete_player(name: str) -> bool:
    with Session(_engine) as session:
        record = session.get(PlayerSave, name)
        if record is None:
            return False
        session.delete(record)
        session.commit()
        return True
