"""Turns the numbers into a recommendation a human can act on in 30 seconds."""

from . import config, engine

BENCH_DISCOUNT = 0.35      # a backup is worth far less than a starter
SURPLUS_DISCOUNT = 0.10    # depth you'll never start

# Most you'd ever sensibly roster at each position in a 10-team league.
# Past this a player is worth nothing to you no matter how good he is.
MAX_AT_POS = {"QB": 2, "TE": 3, "K": 1, "DST": 1, "RB": 8, "WR": 8}

# QB, K and DST have no FLEX slot, so a second one only ever sits on your
# bench. That makes a backup at these positions worth far less than a
# backup RB or WR, who at least has a path into your lineup.
NO_FLEX_BACKUP = 0.06


class Roster:
    """One team's picks, and what starting slots are still empty."""

    def __init__(self, name):
        self.name = name
        self.players = []

    def add(self, p):
        self.players.append(p)

    def count(self, pos):
        return sum(1 for p in self.players if p.pos == pos)

    def needs(self):
        """Unfilled starting slots, e.g. {'RB': 1, 'TE': 1, 'FLEX': 1}."""
        need = {}
        for pos, n in config.STARTERS.items():
            if pos == "FLEX":
                continue
            have = self.count(pos)
            if have < n:
                need[pos] = n - have
        # FLEX is filled by leftover RB/WR/TE
        flex_n = config.STARTERS.get("FLEX", 0)
        if flex_n:
            spare = 0
            for pos in config.FLEX_POSITIONS:
                spare += max(0, self.count(pos) - config.STARTERS.get(pos, 0))
            if spare < flex_n:
                need["FLEX"] = flex_n - spare
        return need

    def slot_state(self, pos):
        """'starter' | 'flex' | 'bench' | 'surplus' for the next player at pos."""
        have = self.count(pos)
        want = config.STARTERS.get(pos, 0)
        if have < want:
            return "starter"
        if pos in config.FLEX_POSITIONS:
            spare = sum(max(0, self.count(x) - config.STARTERS.get(x, 0))
                        for x in config.FLEX_POSITIONS)
            if spare < config.STARTERS.get("FLEX", 0):
                return "flex"
        # How deep are we already at this position?
        if have >= want + 3:
            return "surplus"
        return "bench"

    def bye_weeks(self):
        byes = {}
        for p in self.players:
            if p.bye:
                byes.setdefault(p.bye, []).append(p)
        return byes


class Recommender:
    def __init__(self, analyzer, state):
        self.a = analyzer
        self.s = state

    # -- how likely is he to still be here next time I pick? --------------
    def survives(self, p, next_pick):
        """Rough odds the player is still available at your next pick."""
        if next_pick is None:
            return 1.0
        if p.adp is None:
            return 0.5
        gap = p.adp - next_pick
        # ADP has a lot of noise; treat +/- 12 picks as the fuzzy zone.
        if gap >= 14:
            return 0.92
        if gap <= -14:
            return 0.05
        return max(0.05, min(0.92, 0.5 + gap / 28.0))

    def score(self, p, roster, pick_no, next_pick):
        """Marginal value of this player to THIS roster right now."""
        slot = roster.slot_state(p.pos)

        # Below-replacement players would all floor to zero and tie, which
        # lets a penalised kicker beat a real skill player. Keep a small
        # rank-derived residual so the ordering never collapses.
        residual = 25.0 / (1.0 + p.rank / 25.0)
        base = max(p.vor, 0.0) + residual

        have = roster.count(p.pos)
        if slot == "starter":
            mult = 1.0
        elif slot == "flex":
            mult = 0.85
        elif have >= MAX_AT_POS.get(p.pos, 8):
            mult = 0.0
        elif p.pos not in config.FLEX_POSITIONS:
            mult = NO_FLEX_BACKUP
        elif slot == "bench":
            mult = BENCH_DISCOUNT
        else:
            mult = SURPLUS_DISCOUNT
        val = base * mult

        reasons = []
        rnd = engine.pick_to_round(pick_no, self.a.teams)

        # Kickers and defenses: never early. This is the #1 beginner mistake.
        min_round = config.LATE_ROUND_ONLY.get(p.pos)
        if min_round and rnd < min_round:
            val *= 0.02
            reasons.append(f"don't draft a {p.pos} until round {min_round}+")

        # Tier cliff: if his tier is nearly empty, waiting costs you real points.
        left = self.a.tier_remaining(p.pos, p.tier, self.s.drafted_keys)
        if left is not None and p.tier is not None:
            if left <= 2 and slot in ("starter", "flex"):
                val *= 1.18
                reasons.append(f"only {left} left in this {p.pos} tier -- big drop after")
            elif left <= 4 and slot in ("starter", "flex"):
                val *= 1.07
                reasons.append(f"{left} left in this {p.pos} tier")

        # Value vs ADP: has he fallen past where he normally goes?
        if p.adp is not None:
            slide = pick_no - p.adp
            if slide >= 12:
                val *= 1.12
                reasons.append(f"falling -- usually gone by pick {p.adp:.0f}, still here at {pick_no}")
            elif slide >= 6:
                val *= 1.05
                reasons.append(f"slight value, ADP {p.adp:.0f}")
            elif slide <= -14:
                val *= 0.90
                reasons.append(f"reach -- ADP is {p.adp:.0f}, you'd be {abs(slide):.0f} picks early")

        # Will he last? If he certainly will, prefer the guy who won't.
        surv = self.survives(p, next_pick)
        if next_pick and surv >= 0.85 and slot in ("starter", "flex"):
            val *= 0.93
            reasons.append(f"likely still there at your next pick ({next_pick})")
        elif next_pick and surv <= 0.20 and slot in ("starter", "flex"):
            val *= 1.08
            reasons.append(f"almost certainly gone by pick {next_pick}")

        # Injury / risk flags
        if p.injury and str(p.injury).lower() not in ("none", "null", ""):
            val *= 0.90
            reasons.append(f"injury: {p.injury}")
        if p.expert_stdev and p.expert_stdev >= 12:
            reasons.append(f"experts disagree a lot (best {p.expert_best:.0f} / worst {p.expert_worst:.0f})")

        # Consensus momentum
        if p.expert_delta and p.expert_delta >= 5:
            reasons.append("consensus rising fast")
        elif p.expert_delta and p.expert_delta <= -5:
            reasons.append("consensus falling")

        # Year-over-year signal
        if p.proj and p.last and p.last > 20:
            change = (p.proj - p.last) / p.last
            if change >= 0.30:
                reasons.append(f"projected way up on last year ({p.last:.0f} -> {p.proj:.0f})")
            elif change <= -0.25:
                reasons.append(f"projected down on last year ({p.last:.0f} -> {p.proj:.0f})")

        # Bye-week pileup
        byes = roster.bye_weeks()
        if p.bye and len(byes.get(p.bye, [])) >= 3:
            val *= 0.96
            reasons.append(f"bye week {p.bye} is getting crowded")

        if slot == "starter":
            reasons.insert(0, f"fills your empty {p.pos} slot")
        elif slot == "flex":
            reasons.insert(0, "fills your FLEX")
        elif roster.count(p.pos) >= MAX_AT_POS.get(p.pos, 8):
            reasons.insert(0, f"you already have enough {p.pos}s -- don't")
        elif p.pos not in config.FLEX_POSITIONS:
            reasons.insert(0, f"you already have a {p.pos}; a backup one just sits on your bench")
        elif slot == "surplus":
            reasons.insert(0, f"you already have {roster.count(p.pos)} {p.pos}s")

        return val, reasons, slot

    def top(self, n=6, pool_size=60):
        """The n best picks for you right now, with reasons."""
        roster = self.s.my_roster()
        pick_no = self.s.current_pick
        next_pick = self.s.my_next_pick(after=pick_no)
        avail = self.a.available(self.s.drafted_keys)[:pool_size]

        scored = []
        for p in avail:
            val, reasons, slot = self.score(p, roster, pick_no, next_pick)
            scored.append((val, p, reasons, slot))
        scored.sort(key=lambda t: -t[0])
        return scored[:n]
