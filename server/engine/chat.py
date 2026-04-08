"""Chat commands — extracted from GameSession."""
from __future__ import annotations


async def do_say(send_fn, broadcast_fn, player_name: str, message: str) -> None:
    message = message.strip()
    if not message:
        await send_fn("  Say what? Usage: SAY <message>\n")
        return
    await send_fn(f'  [You say]: "{message}"\n')
    await broadcast_fn(f'  [{player_name} says]: "{message}"\n', exclude_self=True)


async def do_emote(send_fn, broadcast_fn, player_name: str, action: str) -> None:
    action = action.strip()
    if not action:
        await send_fn("  Emote what? Usage: EMOTE <action>\n")
        return
    await broadcast_fn(f"  * {player_name} {action}\n", exclude_self=False)


async def do_shout(send_fn, sessions, player_name: str, message: str) -> None:
    message = message.strip()
    if not message:
        await send_fn("  Shout what? Usage: SHOUT <message>\n")
        return
    await send_fn(f'  [You shout]: "{message}"\n')
    for name, session in sessions.items():
        if name == player_name:
            continue
        await session._send(f'  [Shout from {player_name}]: "{message}"\n')
