"""The actual thinking: what a player is worth, and who you should take.

The central idea is VOR (Value Over Replacement). A running back who scores
250 points is not automatically better than a wide receiver who scores 240.
What matters is how much better he is than the guy you could get for free at
the same position. In a 10-team league roughly 30 running backs start every
week, so the "replacement" running back is about RB30 -- and a player's real
draft value is how far above that line he sits.

That one adjustment is why the tool will sometimes tell you to take a lower
projected player: he's rarer at his position.
"""

import functools
import statistics

from . import config


def snake_picks(slot, teams=None, rounds=None):
    """Overall pick numbers for a given draft slot in a snake draft."""
    teams = teams or config.TEAMS
    rounds = rounds or config.total_rounds()
    picks = []
    for r in range(1, rounds + 1):
        if r % 2 == 1:
            picks.append((r - 1) * teams + slot)
        else:
            picks.append((r - 1) * teams + (teams - slot + 1))
    return picks


def pick_to_round(pick, teams=None):
    teams = teams or config.TEAMS
    return (pick - 1) // teams + 1


def starter_demand(teams=None):
    """How many of each position get drafted as weekly starters league-wide."""
    teams = teams or config.TEAMS
    demand = {p: config.STARTERS.get(p, 0) * teams for p in config.ALL_POSITIONS}
    return demand


class Analyzer:
    """Computes value for a pool of players under one scoring format."""

    def __init__(self, pool, scoring, teams=None, expert_weight=0.6):
        self.pool = [p for p in pool if (p.proj is not None or p.ecr is not None)]
        self.scoring = scoring
        self.teams = teams or config.TEAMS
        self.expert_weight = expert_weight
        self.replacement = {}
        self._compute()

    # -- replacement level ------------------------------------------------
    def _compute_replacement(self):
        """Find the projected points of a freely-available starter at each spot."""
        by_pos = {}
        for p in self.pool:
            by_pos.setdefault(p.pos, []).append(p)
        for pos in by_pos:
            by_pos[pos].sort(key=lambda x: (x.proj if x.proj is not None else -1), reverse=True)

        demand = starter_demand(self.teams)

        # Fill FLEX from the best remaining RB/WR/TE, which pushes the
        # replacement line deeper at whichever positions are actually used.
        flex_slots = config.STARTERS.get("FLEX", 0) * self.teams
        used = {pos: min(demand.get(pos, 0), len(by_pos.get(pos, []))) for pos in by_pos}
        if flex_slots:
            cands = []
            for pos in config.FLEX_POSITIONS:
                lst = by_pos.get(pos, [])
                for p in lst[used.get(pos, 0):]:
                    if p.proj is not None:
                        cands.append(p)
            cands.sort(key=lambda x: x.proj, reverse=True)
            for p in cands[:flex_slots]:
                used[p.pos] = used.get(p.pos, 0) + 1

        for pos, lst in by_pos.items():
            idx = used.get(pos, 0)
            # Average a small window at the replacement line so one weird
            # projection doesn't swing every value at the position.
            window = [x.proj for x in lst[idx:idx + 5] if x.proj is not None]
            if not window:
                window = [x.proj for x in lst[-5:] if x.proj is not None] or [0.0]
            self.replacement[pos] = statistics.fmean(window)
        self.starters_used = used

    # -- composite value --------------------------------------------------
    def _compute(self):
        self._compute_replacement()

        for p in self.pool:
            base = p.proj if p.proj is not None else 0.0
            p.vor = round(base - self.replacement.get(p.pos, 0.0), 1)

        # Rank by VOR (scarcity-aware) and by expert consensus, then blend.
        by_vor = sorted(self.pool, key=lambda x: x.vor, reverse=True)
        vor_rank = {id(p): i + 1 for i, p in enumerate(by_vor)}

        experts = [p for p in self.pool if p.ecr is not None]
        worst_ecr = max((p.ecr for p in experts), default=len(self.pool)) + 25

        for p in self.pool:
            vr = vor_rank[id(p)]
            if p.ecr is not None:
                blended = self.expert_weight * p.ecr + (1 - self.expert_weight) * vr
            else:
                # No expert rank at all -- almost certainly a deep flier.
                blended = max(vr, worst_ecr)
            p.value = blended

        ordered = sorted(self.pool, key=lambda x: x.value)
        for i, p in enumerate(ordered):
            p.rank = i + 1
        self.ranked = ordered
        self._compute_tiers()

        # Positional rank within the merged board.
        counts = {}
        for p in ordered:
            counts[p.pos] = counts.get(p.pos, 0) + 1
            p.pos_rank = counts[p.pos]

    def _compute_tiers(self):
        """Give each position a set of tiers that read correctly top to bottom.

        FantasyPros ships expert tiers, which capture genuine cliff judgement.
        But they're numbered against *their* ranking, so once the board is
        re-sorted by value the labels scramble -- you'd see tier 8 above tier 6.

        Fix: walk each position in board order and carry a running maximum, so
        tiers never go backwards. A player the experts tier lower but this
        board rates higher simply folds into the current tier, which is an
        honest way to say "this board likes him more than the consensus does".
        """
        by_pos = {}
        for p in self.ranked:
            by_pos.setdefault(p.pos, []).append(p)

        for lst in by_pos.values():
            running = 0
            raw = []
            for p in lst:
                t = p.tier if p.tier is not None else running
                running = max(running, t, 1)
                raw.append(running)
            # Renumber so tiers come out consecutive: 1, 2, 3 ...
            order = {t: i + 1 for i, t in enumerate(sorted(set(raw)))}
            for p, t in zip(lst, raw):
                p.vtier = order[t]

    # -- helpers -----------------------------------------------------------
    def available(self, drafted_keys):
        return [p for p in self.ranked if p.key not in drafted_keys]

    def tier_remaining(self, pos, tier, drafted_keys):
        """How many players are left in a given positional tier."""
        if tier is None:
            return None
        return sum(1 for p in self.ranked
                   if p.pos == pos and p.vtier == tier and p.key not in drafted_keys)


# How bench spots get spread across positions. Running backs and receivers
# get the most because they're the ones who get hurt, and because they're the
# only positions with a FLEX slot to feed.
BENCH_WEIGHTS = {"RB": 0.40, "WR": 0.40, "TE": 0.10, "QB": 0.10}

# When rounding leaves a spare spot, this is who gets it.
FILL_PRIORITY = ("RB", "WR", "TE", "QB")


@functools.lru_cache(maxsize=8)
def roster_plan():
    """How many of each position you should end the draft with.

    Derived from your league settings, not hardcoded -- change STARTERS or
    BENCH in config.py and this changes with it.
    """
    size = config.roster_size()
    starters = {p: n for p, n in config.STARTERS.items() if p != "FLEX"}
    flex = config.STARTERS.get("FLEX", 0)
    bench = config.BENCH

    # Start from required starters.
    exact = {p: float(n) for p, n in starters.items()}

    # FLEX is shared by the flex-eligible positions.
    if flex:
        share = flex / len([p for p in config.FLEX_POSITIONS if p in ("RB", "WR")] or [1])
        for p in ("RB", "WR"):
            if p in config.FLEX_POSITIONS:
                exact[p] = exact.get(p, 0) + share

    # Bench spots go where injuries and upside actually live.
    for p, w in BENCH_WEIGHTS.items():
        exact[p] = exact.get(p, 0) + bench * w

    # Round to whole players, hitting the roster size exactly.
    target = {p: int(v) for p, v in exact.items()}
    spare = size - sum(target.values())
    remainders = sorted(
        exact.items(),
        key=lambda kv: (-(kv[1] - int(kv[1])),
                        FILL_PRIORITY.index(kv[0]) if kv[0] in FILL_PRIORITY else 99))
    i = 0
    while spare > 0 and remainders:
        pos = remainders[i % len(remainders)][0]
        if pos in ("K", "DST"):
            i += 1
            continue
        target[pos] += 1
        spare -= 1
        i += 1

    plan = {}
    for pos in config.ALL_POSITIONS:
        must = starters.get(pos, 0)
        plan[pos] = {
            "must_start": must,
            "target": target.get(pos, 0),
            "flex_eligible": pos in config.FLEX_POSITIONS,
        }
    return plan


def plan_notes():
    """Plain-English reason for each position's number."""
    flex = config.STARTERS.get("FLEX", 0)
    return {
        "QB": "You only start one, and late-round QBs score nearly as much. Don't reach.",
        "RB": f"You start {config.STARTERS.get('RB', 0)}"
              + (f" plus they can fill your FLEX" if flex else "")
              + ". They get hurt the most, so carry extras.",
        "WR": f"You start {config.STARTERS.get('WR', 0)}"
              + (f" plus they can fill your FLEX" if flex else "")
              + ". Deepest position -- good ones last into the middle rounds.",
        "TE": "One starter. Either get a top-3 guy early or wait until late; the middle is a dead zone.",
        "K": "Completely interchangeable. Last round, never earlier.",
        "DST": "Nearly interchangeable and matchup-dependent. Second-to-last round.",
    }


def position_timeline(analyzer, pos, max_tiers=5):
    """Where each tier at a position typically runs out, by ADP.

    Answers 'how long can I wait?' -- the question that actually matters.
    """
    rows = []
    seen = {}
    for p in analyzer.ranked:
        if p.pos != pos or p.vtier is None:
            continue
        seen.setdefault(p.vtier, []).append(p)
    for tier in sorted(seen)[:max_tiers]:
        group = seen[tier]
        adps = [p.adp for p in group if p.adp]
        rows.append({
            "tier": tier,
            "count": len(group),
            "players": group,
            "gone_by": max(adps) if adps else None,
            "first_adp": min(adps) if adps else None,
        })
    return rows
