"""League settings. Edit these to match your league, then re-run."""

# ---- Scoring format toggle -------------------------------------------------
# "std"  = no points per reception
# "half" = 0.5 points per reception   (most common default)
# "ppr"  = 1.0 points per reception
# Change this one line and every ranking, projection and ADP re-computes.
SCORING = "half"

VALID_SCORING = ("std", "half", "ppr")

# ---- League shape ----------------------------------------------------------
TEAMS = 10
DRAFT_TYPE = "snake"

# Starting lineup. This drives replacement level, which is what makes the
# value numbers meaningful. FLEX may be filled by RB/WR/TE.
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DST": 1}
FLEX_POSITIONS = ("RB", "WR", "TE")
BENCH = 6

# Positions we actually rank and recommend.
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")
ALL_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")

# Don't recommend a kicker or defense before this round -- they are
# near-interchangeable and burning an early pick on one is the single most
# common beginner mistake.
LATE_ROUND_ONLY = {"K": 14, "DST": 13}

# ---- Season context --------------------------------------------------------
PROJECTION_SEASON = 2026
ACTUALS_SEASON = 2025


def roster_size():
    return sum(STARTERS.values()) + BENCH


def total_rounds():
    return roster_size()


def validate():
    if SCORING not in VALID_SCORING:
        raise ValueError(f"SCORING must be one of {VALID_SCORING}, got {SCORING!r}")
