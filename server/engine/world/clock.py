"""
WorldClock — shared world time, weather, temperature, and lighting state.

A single instance is created at startup in main.py and passed to every
GameSession.  Sessions call subscribe() to receive weather announcements
pushed as ambient narrative messages.

Time resolution
---------------
  WORLD_TICK_SECONDS real seconds advance the world by 1 game-minute.
  1 real minute  = GAME_MINS_PER_REAL_MIN (10) game-minutes
  1 game day     = 1440 game-minutes  →  144 real minutes (2.4 real hours)

Moon phase: 28-day cycle determines night outdoor ambient light.
"""
from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable

from server.config import (
    GAME_START_HOUR,
    WEATHER_MAX_DURATION,
    WEATHER_MIN_DURATION,
    WEATHER_WARN_MINUTES,
    WORLD_TICK_SECONDS,
)

# ── Weather catalogue ─────────────────────────────────────────────────────────

WEATHER_TYPES: tuple[str, ...] = ("sunny", "cloudy", "rainy", "windy", "stormy")

# Warning and arrival messages shown to all outdoor/indoor players
_WEATHER_TRANSITIONS: dict[str, tuple[str, str]] = {
    "sunny":  (
        "The clouds begin to part overhead.",
        "The sky clears — warm sunlight spreads across the land.",
    ),
    "cloudy": (
        "Grey clouds are gathering on the horizon.",
        "An overcast sky settles in, muting the daylight.",
    ),
    "rainy":  (
        "The air grows heavy and damp. Rain seems imminent.",
        "Rain begins to fall, pattering against stone and leaf alike.",
    ),
    "windy":  (
        "A steady wind picks up from the north.",
        "A cold wind sweeps through, rustling cloaks and snuffing candles.",
    ),
    "stormy": (
        "Dark clouds mass on the horizon. The pressure drops sharply.",
        "A storm breaks — rain lashes the ground and distant thunder rolls.",
    ),
}

# Per-weather: temperature modifier (°F) and outdoor light modifier [0..1]
_WEATHER_FX: dict[str, dict[str, float]] = {
    "sunny":  {"temp_mod":  5.0, "light_mod":  0.00},
    "cloudy": {"temp_mod": -2.0, "light_mod":  0.00},
    "rainy":  {"temp_mod": -5.0, "light_mod": -0.10},
    "windy":  {"temp_mod": -8.0, "light_mod":  0.00},
    "stormy": {"temp_mod":-12.0, "light_mod": -0.20},
}

# ── Moon phase (28-day cycle) ─────────────────────────────────────────────────
# (name, night outdoor ambient light fraction)
_MOON_PHASES: list[tuple[str, float]] = [
    ("new moon",         0.05),  # day  0
    ("new moon",         0.05),  # day  1
    ("new moon",         0.05),  # day  2
    ("waxing crescent",  0.15),  # day  3
    ("waxing crescent",  0.15),  # day  4
    ("waxing crescent",  0.15),  # day  5
    ("waxing crescent",  0.15),  # day  6
    ("first quarter",    0.35),  # day  7
    ("first quarter",    0.35),  # day  8
    ("first quarter",    0.35),  # day  9
    ("waxing gibbous",   0.55),  # day 10
    ("waxing gibbous",   0.55),  # day 11
    ("waxing gibbous",   0.55),  # day 12
    ("waxing gibbous",   0.55),  # day 13
    ("full moon",        0.70),  # day 14
    ("full moon",        0.70),  # day 15
    ("waning gibbous",   0.55),  # day 16
    ("waning gibbous",   0.55),  # day 17
    ("waning gibbous",   0.55),  # day 18
    ("waning gibbous",   0.55),  # day 19
    ("last quarter",     0.35),  # day 20
    ("last quarter",     0.35),  # day 21
    ("last quarter",     0.35),  # day 22
    ("waning crescent",  0.15),  # day 23
    ("waning crescent",  0.15),  # day 24
    ("waning crescent",  0.15),  # day 25
    ("new moon",         0.05),  # day 26
    ("new moon",         0.05),  # day 27
]

# ── Label helpers ─────────────────────────────────────────────────────────────

def temperature_label(temp_f: float) -> str:
    if temp_f > 95:  return "Scorching"
    if temp_f > 80:  return "Hot"
    if temp_f > 60:  return "Comfortable"
    if temp_f > 45:  return "Cool"
    if temp_f > 30:  return "Cold"
    if temp_f > 10:  return "Bitter Cold"
    return "Freezing"


def light_label(light: float) -> str:
    if light >= 0.80: return "Well-lit"
    if light >= 0.60: return "Good light"
    if light >= 0.40: return "Dim"
    if light >= 0.20: return "Dark"
    if light >= 0.05: return "Very dark"
    return "Pitch black"


# ── Combat lighting penalty lookup ────────────────────────────────────────────
# Returns (hit_penalty, dodge_penalty) — fractions subtracted from base chances.
def lighting_combat_penalties(light: float) -> tuple[float, float]:
    if light >= 0.80: return (0.00, 0.00)
    if light >= 0.60: return (0.05, 0.10)
    if light >= 0.40: return (0.15, 0.20)
    if light >= 0.20: return (0.30, 0.40)
    if light >= 0.05: return (0.50, 0.75)
    return (1.00, 1.00)  # pitch black — combat forbidden from player side


# ── WorldClock ────────────────────────────────────────────────────────────────

class WorldClock:
    """
    Authoritative world time, weather, and environmental state.
    One instance is shared across all GameSessions via main.py.
    """

    def __init__(self, world=None) -> None:
        # Absolute game-minutes elapsed since the world began (day 0, 00:00).
        # Start at GAME_START_HOUR so new players enter at morning.
        self._total_minutes: int = GAME_START_HOUR * 60

        # Optional WorldMap reference for periodic respawn ticking
        self._world = world

        # Weather state machine
        self.current_weather: str = "sunny"
        self._weather_timer: int = random.randint(
            WEATHER_MIN_DURATION, WEATHER_MAX_DURATION
        )
        self._pending_weather: str | None = None
        self._pending_timer: int = 0
        self._warn_sent: bool = False

        # Async background task handle
        self._task: asyncio.Task | None = None

        # Subscriber callbacks: async (message: str) → None
        self._subscribers: list[Callable[[str], Awaitable[None]]] = []

        # Tick callbacks: async () → None — fired every game-minute tick
        self._tick_subscribers: list[Callable[[], Awaitable[None]]] = []

        # Async lock for subscriber list mutations (A3)
        self._sub_lock: asyncio.Lock = asyncio.Lock()

        # Tick counter for periodic operations (A8)
        self._tick_count: int = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the background tick task. Call once after the event loop starts."""
        self._task = asyncio.get_event_loop().create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _tick_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(WORLD_TICK_SECONDS)
                self._advance_one_minute()
        except asyncio.CancelledError:
            pass

    def _advance_one_minute(self) -> None:
        self._total_minutes += 1
        self._tick_count += 1
        self._tick_weather()
        if self._world is not None:
            self._world.tick_respawns()
        asyncio.get_event_loop().create_task(self._notify_ticks())

    # ── Weather state machine ─────────────────────────────────────────────────

    def _tick_weather(self) -> None:
        if self._pending_weather is None:
            self._weather_timer -= 1
            if self._weather_timer <= 0:
                candidates = [w for w in WEATHER_TYPES if w != self.current_weather]
                self._pending_weather = random.choice(candidates)
                self._pending_timer = WEATHER_WARN_MINUTES
                self._warn_sent = False
        else:
            self._pending_timer -= 1
            # Send warning halfway through the transition window
            if not self._warn_sent and self._pending_timer <= WEATHER_WARN_MINUTES // 2:
                warn_msg, _ = _WEATHER_TRANSITIONS[self._pending_weather]
                asyncio.get_event_loop().create_task(self._broadcast(warn_msg))
                self._warn_sent = True
            if self._pending_timer <= 0:
                self.current_weather = self._pending_weather
                _, arrival_msg = _WEATHER_TRANSITIONS[self._pending_weather]
                asyncio.get_event_loop().create_task(self._broadcast(arrival_msg))
                self._pending_weather = None
                self._weather_timer = random.randint(
                    WEATHER_MIN_DURATION, WEATHER_MAX_DURATION
                )

    async def _broadcast(self, message: str) -> None:
        async with self._sub_lock:
            subscribers = list(self._subscribers)
        for cb in subscribers:
            try:
                await cb(message)
            except Exception:
                pass

    async def _notify_ticks(self) -> None:
        """Notify all tick subscribers that a game-minute has passed."""
        async with self._sub_lock:
            subscribers = list(self._tick_subscribers)
        for cb in subscribers:
            try:
                await cb()
            except Exception:
                pass

    # ── Subscription ──────────────────────────────────────────────────────────

    def subscribe(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Subscribe to weather broadcast messages.
        
        Synchronous-safe: mutations are atomic under asyncio's single-threaded
        model. Async _broadcast iterates a copy, so no lock needed here (A3).
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Unsubscribe from weather broadcast messages."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def subscribe_tick(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Subscribe to every game-minute tick (not just weather changes)."""
        if callback not in self._tick_subscribers:
            self._tick_subscribers.append(callback)

    def unsubscribe_tick(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Unsubscribe from game-minute ticks."""
        if callback in self._tick_subscribers:
            self._tick_subscribers.remove(callback)

    # ── Time properties ───────────────────────────────────────────────────────

    @property
    def total_minutes(self) -> int:
        return self._total_minutes

    @property
    def game_day(self) -> int:
        return self._total_minutes // 1440

    @property
    def hour(self) -> int:
        return (self._total_minutes % 1440) // 60

    @property
    def minute(self) -> int:
        return self._total_minutes % 60

    @property
    def moon_phase_name(self) -> str:
        return _MOON_PHASES[self.game_day % 28][0]

    @property
    def moon_light(self) -> float:
        return _MOON_PHASES[self.game_day % 28][1]

    # ── Ambient light ─────────────────────────────────────────────────────────

    def ambient_light(self, room_type: str) -> float:
        """
        Return ambient light level [0.0, 1.0] for a room type.
        room_type: 'outdoor' | 'indoor' | 'underground'
        """
        if room_type == "indoor":
            return 0.85          # sheltered, always softly lit
        if room_type == "underground":
            return 0.0           # pure darkness

        # Outdoor — time of day + moon phase + weather
        t = self.hour + self.minute / 60.0
        if 7.0 <= t < 18.0:
            base = 1.0
        elif 5.0 <= t < 7.0:
            # Dawn gradient: 60 % → 100 %
            base = 0.60 + 0.40 * ((t - 5.0) / 2.0)
        elif 18.0 <= t < 20.0:
            # Dusk gradient: 100 % → 60 %
            base = 1.0 - 0.40 * ((t - 18.0) / 2.0)
        else:
            # Night — moon-dependent
            base = self.moon_light

        base += _WEATHER_FX[self.current_weather]["light_mod"]
        return max(0.0, min(1.0, base))

    def effective_light(self, room_type: str, carried_light: float) -> float:
        """Combine ambient and best carried light source."""
        return max(self.ambient_light(room_type), min(1.0, carried_light))

    # ── Temperature ───────────────────────────────────────────────────────────

    def temperature_f(self, room_type: str, base_temp_f: float) -> float:
        """Compute actual temperature in °F for the given room."""
        if room_type == "underground":
            return base_temp_f   # caves are thermally stable; weather-immune
        return base_temp_f + _WEATHER_FX[self.current_weather]["temp_mod"]

    def temperature_label(self, room_type: str, base_temp_f: float) -> str:
        return temperature_label(self.temperature_f(room_type, base_temp_f))

    # ── Display helpers ───────────────────────────────────────────────────────

    def time_of_day_label(self) -> str:
        h = self.hour
        if  0 <= h <  5: return "deep night"
        if  5 <= h <  7: return "dawn"
        if  7 <= h < 12: return "morning"
        if h == 12:       return "midday"
        if 13 <= h < 17: return "afternoon"
        if 17 <= h < 20: return "dusk"
        return "evening"

    def time_string(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    def env_footer(self, room_type: str, base_temp_f: float, carried_light: float) -> str:
        """
        One-line environment description appended to room renders.
        Underground rooms only show lighting (no time/weather seeps in).
        Indoor rooms show time of day but no weather.
        Outdoor rooms show the full picture.
        """
        eff = self.effective_light(room_type, carried_light)
        ll  = light_label(eff)

        if room_type == "underground":
            return f"  [{ll}]"

        if room_type == "indoor":
            return f"  [Indoors — {self.time_of_day_label().capitalize()} — {ll}]"

        # Outdoor
        tl   = self.time_of_day_label().capitalize()
        wl   = self.current_weather.capitalize()
        tlab = self.temperature_label(room_type, base_temp_f)
        return f"  [{tl} — {wl} — {tlab} — {ll}]"
