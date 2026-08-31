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

        # Positional rank within the merged board.
        counts = {}
        for p in ordered:
            counts[p.pos] = counts.get(p.pos, 0) + 1
            p.pos_rank = counts[p.pos]

    # -- helpers -----------------------------------------------------------
    def available(self, drafted_keys):
        return [p for p in self.ranked if p.key not in drafted_keys]

    def tier_remaining(self, pos, tier, drafted_keys):
        """How many players are left in a given positional tier."""
        if tier is None:
            return None
        return sum(1 for p in self.ranked
                   if p.pos == pos and p.tier == tier and p.key not in drafted_keys)
