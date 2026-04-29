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
COMBAT_TICK_INTERVAL: float = 1.5  # Seconds between combat ticks (used by battle_cry only)
BASE_COOLDOWN_TICKS: int = 8       # Legacy — kept for combat.py import; no longer drives interval
BASE_ATTACK_SPEED: float = 48.0    # Numerator for attack interval (seconds):
                                    #   interval = BASE_ATTACK_SPEED / effective_speed
                                    # AGI 16 → 3.0 s | AGI 12 + 20 lb gear → 4.8 s
MIN_ATTACK_INTERVAL: float = 2.0   # Fastest any combatant may attack (seconds)
MAX_ATTACK_INTERVAL: float = 8.0   # Slowest any combatant may attack (seconds)

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

# ── Combat tuning (extracted from combat.py) ─────────────────────────────────
FLEE_SUCCESS_RATE: float = 0.40          # chance a flee attempt succeeds
CRITICAL_DAMAGE_MULTIPLIER: float = 1.5  # crit hit damage multiplier
CRITICAL_HIT_CHANCE: float = 0.10        # base crit probability per attack
COMBAT_INITIAL_DELAY: float = 0.1        # seconds before first poll tick in _run()
COMBAT_MIN_SLEEP: float = 0.3            # minimum seconds between combatant actions
STAMINA_DRAIN_FLEE: float = 5.0          # stamina cost to attempt a flee

# ── Movement & survival (extracted from game.py) ──────────────────────────────
STAMINA_DRAIN_PER_MOVE: float = 2.0      # stamina drained per room move
SIT_STAMINA_RECOVERY_RATE: float = 1.0   # stamina recovered per tick while sitting
MOUNT_STAMINA_REDUCTION: float = 0.60    # fraction of stamina saving granted by horses

# ── XP progression (extracted from character.py) ─────────────────────────────
# XP_TABLE[level] = total XP needed to reach that level (level 1 = 0)
MAX_LEVEL: int = 10
XP_TABLE: list[int] = [
    0,      # level 1
    300,    # level 2
    900,    # level 3
    2100,   # level 4
    4500,   # level 5
    9000,   # level 6
    16000,  # level 7
    27000,  # level 8
    42000,  # level 9
    66000,  # level 10
]

# ── Save versioning ───────────────────────────────────────────────────────────
SAVE_SCHEMA_VERSION: int = 2

# ── Grid limits ───────────────────────────────────────────────────────────────
MAX_PARTY_SIZE: int = 5     # 1 player + 4 companions
MAX_GRID_SLOTS: int = 6     # 2 rows × 3 columns
