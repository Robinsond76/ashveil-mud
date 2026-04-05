# Plan: Phase 9 — Multiplayer Foundations

**Spec:** [phase-09-multiplayer-foundations.md](../specs/phase-09-multiplayer-foundations.md)
**Depends on:** All earlier phases (stable world state required)
**Status:** NOT STARTED

---

## Overview

Lay the architectural groundwork for multiple simultaneous players. Players can see each other in rooms, receive movement/action broadcast messages, pick up shared loot, and communicate via `SAY` and `EMOTE`. No PvP in this phase.

---

## Phase A — Session Registry

1. Add `_sessions: dict[str, GameSession] = {}` at module level in `server/main.py`
2. Pass `sessions=_sessions` to the `GameSession()` constructor in the WebSocket endpoint handler
3. Update `GameSession.__init__()` to accept and store `sessions: dict` param as `self._sessions`
4. In `GameSession.run()`, after character is loaded and name is confirmed:
   - `self._sessions[player_name] = self`
5. In `GameSession.run()` finally block (on disconnect):
   - `self._sessions.pop(player_name, None)`

---

## Phase B — Room Occupancy

6. Add `room_occupants: dict[str, list[str]]` field to `WorldMap` in `server/engine/world.py` (default empty dict via `field(default_factory=dict)`)
7. Add methods to `WorldMap`:
   ```python
   def enter_room(self, player_name: str, room_id: str) -> None:
       self.room_occupants.setdefault(room_id, []).append(player_name)

   def leave_room(self, player_name: str, room_id: str) -> None:
       if room_id in self.room_occupants:
           self.room_occupants[room_id] = [
               n for n in self.room_occupants[room_id] if n != player_name
           ]

   def players_in_room(self, room_id: str) -> list[str]:
       return list(self.room_occupants.get(room_id, []))
   ```
8. In `GameSession.run()` after character load and `_sessions` registration:
   - Call `world_map.enter_room(player_name, starting_room_id)`
   - Broadcast connect message to room: `"[Name] shimmers into existence."`
9. In `GameSession.run()` finally block:
   - Call `world_map.leave_room(player_name, current_room_id)`
   - Broadcast disconnect message: `"[Name] fades from sight."`

---

## Phase C — Broadcast Helper

10. Add `_broadcast_to_room(message: str, exclude_self: bool = True)` async method to `GameSession`:
    ```python
    async def _broadcast_to_room(self, message: str, exclude_self: bool = True) -> None:
        room_id = self._current_room
        for name, session in self._sessions.items():
            if exclude_self and name == self._player.name:
                continue
            if session._current_room == room_id:
                await session._send(message)
    ```
    *No locks needed — asyncio is cooperative; all operations occur in the same event loop.*

---

## Phase D — Movement Broadcasts

11. In `_do_move()`, before executing the move:
    - `world_map.leave_room(player_name, old_room_id)`
    - `await self._broadcast_to_room(f"{player_name} heads {direction}.", exclude_self=True)`
12. After executing the move (new room set):
    - `world_map.enter_room(player_name, new_room_id)`
    - `await self._broadcast_to_room(f"{player_name} arrives from the {opposite_direction}.", exclude_self=True)`

    Helper: `_opposite_direction(direction: str) -> str` mapping north↔south, east↔west, up↔down.

---

## Phase E — LOOK Update

13. In `_do_look()`, after printing exits:
    - `others = [n for n in world_map.players_in_room(current_room) if n != player_name]`
    - If `others`: append `"\nAlso here: " + ", ".join(others)`

---

## Phase F — Shared Room Items

14. In `_do_take()`:
    - Confirm item is removed from `Room.item_ids` (should already be; verify architectural correctness)
    - After successful pickup: `await self._broadcast_to_room(f"{player_name} picks up the {item_name}.", exclude_self=True)`
15. In `_do_drop()`:
    - Confirm item is added to `Room.item_ids`
    - After drop: `await self._broadcast_to_room(f"{player_name} drops the {item_name}.", exclude_self=True)`

---

## Phase G — Chat Commands

16. Add `SAY <message>` handler in `_handle_navigation()`:
    - Sender sees: `[You say]: "message"`
    - Room broadcast: `[{name} says]: "message"`
    - `await self._broadcast_to_room(f'[{player_name} says]: "{message}"', exclude_self=True)`
17. Add `EMOTE <action>` / `ME <action>` handler:
    - All in room including sender see: `* {name} {action}`
    - Use `exclude_self=False` so sender also sees it

---

## Phase H — Combat Broadcast (Stretch)

18. In `GameSession._start_combat()`:
    - `await self._broadcast_to_room(f"{player_name} initiates combat with {target_name}!", exclude_self=True)`

---

## Concurrency Safety Notes

- `_sessions` dict is accessed from multiple asyncio coroutines — safe because asyncio is cooperative (no preemptive threading)
- `Room.item_ids` mutations must complete within a single coroutine (no `await` mid-mutation) — already the case in `_do_take()` / `_do_drop()`
- Do not introduce `threading` or `asyncio.run()` calls; stay in the single event loop

---

## Out of Scope (future phases)

- Player-vs-player combat
- `INVITE <player>` for cross-login party formation
- `TELL <player> <message>` private messaging
- Trading between players
- Guild system

---

## Relevant Files

| File | Changes |
|------|---------|
| `server/main.py` | `_sessions` dict, pass to `GameSession`, register/deregister |
| `server/engine/world.py` | `room_occupants` field, `enter_room()`, `leave_room()`, `players_in_room()` |
| `server/engine/game.py` | `__init__` sessions param, `_broadcast_to_room()`, movement broadcasts, LOOK update, item broadcasts, SAY/EMOTE handlers, combat broadcast |

---

## Verification Checklist

- [ ] Two browser tabs connected: Player B sees *"[Player A] arrives from the north."* when A moves in
- [ ] Player A moves out: Player B sees *"[Player A] heads south."*
- [ ] `LOOK` in shared room: *"Also here: [Player B]"* line appears
- [ ] Player A picks up item: Player B sees broadcast; item no longer in room description for B
- [ ] Player A drops item: Player B sees broadcast; item appears in room for B
- [ ] `SAY hello`: Player A sees `[You say]: "hello"`, Player B sees `[Player A says]: "hello"`
- [ ] `EMOTE waves`: both players see `* Player A waves`
- [ ] Player A disconnects: Player B sees *"[Player A] fades from sight."*
- [ ] Weather broadcast from WorldClock fires to both players simultaneously
- [ ] Solo player (no others in room): no *"Also here"* line in LOOK
