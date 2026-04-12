# Phase 9: Multiplayer Foundations
**Status: IMPLEMENTED**
**Depends on: All earlier phases (world state must be stable)**

## Overview
Lay the architectural groundwork for multiple players inhabiting Ashveil simultaneously. Players can see each other in rooms, receive messages when others arrive and depart, and observe each other's visible actions. No player-vs-player combat in this phase.

---

## Core Concepts

### Session Registry
`main.py` gains a global `_sessions: dict[str, GameSession]` dictionary keyed by player name. Every authenticated `GameSession` registers itself on startup and deregisters on disconnect.

```python
# main.py
_sessions: dict[str, GameSession] = {}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    session = GameSession(ws, world_map=_world_map, clock=_world_clock, sessions=_sessions)
    await session.run()
```

### Room Occupancy Registry
`WorldMap` gains a `room_occupants: dict[str, list[str]]` — room_id → list of player names currently in that room. Updated on every player move, connect, and disconnect.

```python
# world.py
class WorldMap:
    room_occupants: dict[str, list[str]] = field(default_factory=dict)

    def enter_room(self, player_name: str, room_id: str): ...
    def leave_room(self, player_name: str, room_id: str): ...
    def players_in_room(self, room_id: str) -> list[str]: ...
```

---

## Broadcast System

### Room Broadcast
`GameSession` gains a helper to push a message to all other players in the same room:

```python
async def _broadcast_to_room(self, message: str, exclude_self: bool = True):
    room_id = self._current_room
    for name, session in self._sessions.items():
        if name == self._player.name and exclude_self:
            continue
        if session._current_room == room_id:
            await session._send(message)
```

### World Broadcast
Already exists via `WorldClock` subscriber pattern. No changes needed.

---

## Events That Broadcast

| Trigger | Message to room occupants |
|---------|--------------------------|
| Player enters room | *"[Name] arrives from the [direction]."* |
| Player leaves room | *"[Name] heads [direction]."* |
| Player connects (in room) | *"[Name] shimmers into existence."* |
| Player disconnects | *"[Name] fades from sight."* |
| Player picks up item | *"[Name] picks up the [item]."* |
| Player drops item | *"[Name] drops the [item]."* |
| Player attacks | *"[Name] initiates combat with [target]!"* |
| Player casts a spell | *"[Name] begins channeling [spell]."* (already in Phase 7 via channeling messages) |

---

## `LOOK` Changes

Room description now includes other players:

```
--- Town Square ---
The cobblestoned square hums with the murmur of daily life...

Exits: NORTH (Blacksmith), SOUTH (South Gate), EAST (Alchemist)
Also here: Tharivol, Orin
```

Format:
```python
if others := world_map.players_in_room(room_id):
    others_str = ", ".join(others)
    output += f"\nAlso here: {others_str}"
```

---

## Player-to-Player Communication

### `SAY` Command
```
SAY Hello, traveler!
```
Sends to all players in the same room:
```
[Tharivol says]: "Hello, traveler!"
```
Sender sees:
```
[You say]: "Hello, traveler!"
```

### `EMOTE` / `ME` Command
```
EMOTE waves cheerfully.
```
Everyone in the room (including sender) sees:
```
* Tharivol waves cheerfully.
```

### `SHOUT` / `OOC` (optional, low priority)
```
SHOUT Is anyone at the inn?
```
Broadcasts to all connected players regardless of room:
```
[Shout from Tharivol]: "Is anyone at the inn?"
```

---

## Shared Room Items

Room items (loot, placed items) are currently per-session simulated. In multiplayer mode:
- Room item lists live on `Room` objects (already true architecturally via `WorldMap`)
- When Player A picks up an item, it is removed from `Room.items` — Player B will no longer see it
- When Player A drops an item, it appears in `Room.items` for all players

No changes needed to `Room` dataclass — items already live there. The change is that `GameSession._do_take()` and `_do_drop()` update the shared `Room` object rather than a per-session copy.

---

## Encounter Isolation

Combat in this phase remains **per-party isolated**:
- Two parties in the same room can both be fighting different enemies
- Players do not join each other's combat sessions automatically
- A player watching a fight sees the broadcast messages but cannot participate
- Future phase: `JOIN <player>` command to enter an active combat

This avoids race conditions and keeps Phase 9 scope manageable.

---

## Implementation Plan

### `main.py`
1. Add `_sessions: dict[str, GameSession] = {}`
2. Pass `sessions=_sessions` to `GameSession()`
3. Register: `_sessions[name] = session` after character load
4. Deregister: `del _sessions[name]` on disconnect

### `world.py`
1. Add `room_occupants: dict[str, list[str]]` to `WorldMap`
2. `enter_room(player_name, room_id)` — add to list, ensure list exists
3. `leave_room(player_name, room_id)` — remove from list
4. `players_in_room(room_id) → list[str]`

### `game.py`
1. Accept `sessions: dict[str, GameSession]` in `__init__()`
2. Add `_broadcast_to_room(message, exclude_self)` helper
3. `_do_move()`: call `world_map.leave_room()` before move, `enter_room()` after, broadcast enter/leave messages
4. `_do_look()`: append "Also here" line with other player names
5. Add `SAY`, `EMOTE`, `SHOUT` command handling in `_handle_navigation()`
6. `_do_take()` / `_do_drop()`: broadcast item events to room

### `character.py`
No changes required.

---

## Concurrency Safety

- `_sessions` dict is accessed from multiple asyncio coroutines — all in the same event loop, so no locks needed (asyncio is cooperative, not preemptive)
- `Room.items` mutation must happen atomically within a single coroutine (no `await` mid-mutation) — already the case
- Do not use `threading` anywhere; keep everything in the asyncio event loop

---

## Help entries to add
- `HELP SAY`, `HELP EMOTE`, `HELP SHOUT`, `HELP ME`, `HELP MULTIPLAYER`, `HELP PLAYERS`

---

## Out of Scope (future phases)
- Player-vs-player combat
- Trading between players
- Party formation across separate logins (`INVITE <player>`)
- Private messaging (`TELL <player> <message>`)
- Guild or team system
