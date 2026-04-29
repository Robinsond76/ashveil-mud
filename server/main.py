"""
FastAPI entry point.
Serves the browser client and handles WebSocket connections.
Each WebSocket connection gets its own GameSession.
"""
from __future__ import annotations

import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.engine.game import GameSession
from server.engine.domain.items import load_items
from server.engine.domain.npc import load_npcs
from server.engine.domain.skills import load_skills
from server.engine.world.map import WorldMap
from server.engine.world.clock import WorldClock

# ── Resolve data directory ────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data")
CLIENT_DIR = os.path.join(os.path.dirname(_HERE), "client")

# ── One-time startup: load all game data into memory ─────────────────────────
load_items(DATA_DIR)
load_skills(DATA_DIR)
load_npcs(DATA_DIR)

_world = WorldMap()
_world.load(DATA_DIR)

_world_clock = WorldClock(world=_world)

with open(os.path.join(DATA_DIR, "classes", "classes.json"), encoding="utf-8") as _f:
    _class_defs = json.load(_f)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Ashveil MUD")

@app.on_event("startup")
async def on_startup() -> None:
    """Start the shared world clock after the event loop is running."""
    _world_clock.start()

# Serve the browser client
app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(CLIENT_DIR, "index.html"))


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    async def send(text: str) -> None:
        try:
            await websocket.send_text(text)
        except Exception:
            pass

    session = GameSession(send_fn=send, world=_world, class_defs=_class_defs, clock=_world_clock)
    await session.start()

    try:
        while True:
            data = await websocket.receive_text()
            await session.handle_input(data)
            if session._quit:
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await send(f"\n  [Server error: {exc}]\n")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
