"""
Central configuration. All tunable constants and debug flags live here.
To disable death penalties for testing, set DEBUG_NO_DEATH_PENALTY = True.
"""

# ── Debug / testing ─────────────────────────────────────────────────────────
DEBUG_NO_DEATH_PENALTY: bool = True          # No XP/gold loss on defeat
DEBUG_RESPAWN_ROOM_ID: str = "test_entrance" # Room to respawn in when debug on

# ── Death penalty (only used when DEBUG_NO_DEATH_PENALTY = False) ────────────
DEATH_XP_LOSS_PCT: float = 0.10   # 10% of current XP lost
DEATH_GOLD_LOSS_PCT: float = 0.25  # 25% of gold lost

# ── Combat ──────────────────────────────────────────────────────────────────
COMBAT_TICK_INTERVAL: float = 1.5  # Seconds between combat ticks
BASE_COOLDOWN_TICKS: int = 8       # Ticks before a speed-1 combatant acts
                                    # A speed-N combatant acts every
                                    # BASE_COOLDOWN_TICKS / N ticks (min 1)

# ── Character / items ───────────────────────────────────────────────────────
WEIGHT_DIVISOR: int = 10            # Each WEIGHT_DIVISOR units of gear weight
                                    # reduces effective_speed by 1
STAT_POINT_BUY_BUDGET: int = 54     # Total points player may distribute at creation
MIN_STAT: int = 3
MAX_STAT: int = 18
MODIFIER_BONUS_PER_LEVEL: float = 0.05  # +5% per modifier level

# ── Persistence ─────────────────────────────────────────────────────────────
DATABASE_URL: str = "sqlite:///mud.db"

# ── World clock ──────────────────────────────────────────────────────────────
# 1 real minute = 10 game minutes → 1 game day = 144 real minutes (2.4 hrs)
GAME_MINS_PER_REAL_MIN: int = 10
WORLD_TICK_SECONDS: float = 6.0      # real seconds per 1 game-minute advance
GAME_START_HOUR: int = 8             # world starts at 8:00 AM on day 1

# ── Weather ──────────────────────────────────────────────────────────────────
WEATHER_MIN_DURATION: int = 90       # game minutes before weather can change again
WEATHER_MAX_DURATION: int = 240      # game minutes maximum between changes
WEATHER_WARN_MINUTES: int = 60       # game minutes advance warning before change
