"""Answers the question 'how many of each position do I actually need?'

Three views, in increasing order of concreteness:
  1. the position budget   -- how many of each to end up with
  2. the tier timeline     -- how long you can afford to wait at each spot
  3. the simulated path    -- what your draft probably looks like, round by round
"""

from . import config, engine

POS_ORDER = ("QB", "RB", "WR", "TE", "K", "DST")


def simulate_path(analyzer, slot, rounds=None):
    """Play out a plausible draft: everyone else picks by ADP, you pick by value.

    Gives a concrete round-by-round roadmap instead of generic advice.
    """
    from .advice import Recommender
    from .state import DraftState

    rounds = rounds or config.total_rounds()
    state = DraftState(analyzer, slot, rounds=rounds)
    rec = Recommender(analyzer, state)
    path = []

    while not state.is_complete():
        team = state.team_on_clock()
        avail = analyzer.available(state.drafted_keys)
        if not avail:
            break
        if team == slot:
            picks = rec.top(n=1)
            if not picks:
                break
            choice = picks[0][1]
            path.append({
                "round": engine.pick_to_round(state.current_pick, state.teams),
                "pick": state.current_pick,
                "pos": choice.pos,
                "player": choice,
            })
        else:
            # Everyone else drafts roughly in ADP order.
            choice = min(avail[:40], key=lambda p: (p.adp if p.adp else 9999, p.rank))
        state.draft(choice, team)

    return path, state.rosters[slot]


def budget_rows(roster=None):
    """The position budget, optionally with what you already have."""
    plan = engine.roster_plan()
    notes = engine.plan_notes()
    rows = []
    for pos in POS_ORDER:
        d = plan.get(pos)
        if not d:
            continue
        rows.append({
            "pos": pos,
            "must_start": d["must_start"],
            "target": d["target"],
            "have": roster.count(pos) if roster else None,
            "note": notes.get(pos, ""),
        })
    return rows


def render_budget(roster=None, color=None):
    """Text block: how many of each position to draft."""
    c = color or (lambda t, _: str(t))
    out = []
    flex = config.STARTERS.get("FLEX", 0)
    out.append(f"YOUR ROSTER PLAN  --  {config.TEAMS}-team league, "
               f"{config.roster_size()} players over {config.total_rounds()} rounds")
    out.append("")
    if roster is not None:
        out.append(f"  {'POS':<5}{'START':>6}{'DRAFT':>7}{'HAVE':>6}{'STILL':>7}   WHY")
    else:
        out.append(f"  {'POS':<5}{'START':>6}{'DRAFT':>7}   WHY")
    out.append("  " + "-" * 96)
    for r in budget_rows(roster):
        if roster is not None:
            still = max(0, r["target"] - r["have"])
            flag = "  " if still == 0 else "<-"
            out.append(f"  {r['pos']:<5}{r['must_start']:>6}{r['target']:>7}"
                       f"{r['have']:>6}{still:>7} {flag} {r['note']}")
        else:
            out.append(f"  {r['pos']:<5}{r['must_start']:>6}{r['target']:>7}   {r['note']}")
    out.append("  " + "-" * 96)
    total = sum(r["target"] for r in budget_rows())
    starters = sum(r["must_start"] for r in budget_rows())
    out.append(f"  {'':5}{starters:>6}{total:>7}   "
               f"{starters} starters"
               + (f" + {flex} FLEX (any RB/WR/TE)" if flex else "")
               + f" + {config.BENCH} bench = {config.roster_size()} total")
    return "\n".join(out)


def render_timeline(analyzer, positions=("RB", "WR", "TE", "QB")):
    """Text block: when each tier at each position runs out."""
    out = ["HOW LONG CAN YOU WAIT?  (the pick by which each group is usually gone)", ""]
    for pos in positions:
        rows = engine.position_timeline(analyzer, pos, max_tiers=4)
        if not rows:
            continue
        bits = []
        for r in rows:
            gb = f"{r['gone_by']:.0f}" if r["gone_by"] else "?"
            bits.append(f"top {sum(x['count'] for x in rows[:rows.index(r) + 1]):>2} gone by ~{gb:>3}")
        out.append(f"  {pos:<4} " + "   |   ".join(bits))
    out.append("")
    out.append("  Read it like this: if you want one of the best few at a position,")
    out.append("  you have to spend a pick before that number.")
    return "\n".join(out)


def render_path(analyzer, slot):
    """Text block: your likely draft, round by round."""
    path, roster = simulate_path(analyzer, slot)
    out = [f"YOUR LIKELY DRAFT FROM SLOT {slot}",
           "  (a simulation: everyone else drafts by average draft position,",
           "   you draft by value. Real drafts wander -- treat it as a shape, not a script.)",
           ""]
    out.append(f"  {'RND':<5}{'PICK':>5}   {'POS':<5} {'LIKELY AVAILABLE':<30} {'RUNNING TOTAL'}")
    out.append("  " + "-" * 84)
    counts = {}
    for step in path:
        counts[step["pos"]] = counts.get(step["pos"], 0) + 1
        summary = " ".join(f"{p}{counts[p]}" for p in POS_ORDER if p in counts)
        out.append(f"  R{step['round']:<4}{step['pick']:>5}   {step['pos']:<5} "
                   f"{step['player'].name[:29]:<30} {summary}")
    out.append("  " + "-" * 84)
    final = {}
    for p in roster.players:
        final[p.pos] = final.get(p.pos, 0) + 1
    out.append("  Ends with: " + ", ".join(f"{n} {pos}" for pos, n in
                                           sorted(final.items(), key=lambda kv: POS_ORDER.index(kv[0]))))
    need = roster.needs()
    out.append("  Unfilled starting slots: " + (", ".join(f"{k} x{v}" for k, v in need.items())
                                                if need else "none -- full lineup"))
    return "\n".join(out)


def render_all(analyzer, slot=None, roster=None):
    blocks = [render_budget(roster), "", render_timeline(analyzer)]
    if slot:
        blocks += ["", render_path(analyzer, slot)]
    return "\n".join(blocks)
