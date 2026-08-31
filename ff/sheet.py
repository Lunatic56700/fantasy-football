"""Printable cheat sheets, organised by position.

The overall board tells you who's best. The position columns tell you what to
actually do with your roster -- which is the part that wins leagues.
"""

import html
import os

from . import config, engine, plan

OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHEET_POSITIONS = ("RB", "WR", "TE", "QB", "DST", "K")
DEPTH = {"RB": 45, "WR": 55, "TE": 24, "QB": 22, "DST": 14, "K": 12}


def _notes(p):
    out = []
    if p.injury and str(p.injury).lower() not in ("none", "null"):
        out.append(str(p.injury))
    if p.expert_stdev and p.expert_stdev >= 12:
        out.append("divisive")
    if p.proj and p.last and p.last > 20:
        ch = (p.proj - p.last) / p.last
        if ch >= 0.30:
            out.append("breakout")
        elif ch <= -0.25:
            out.append("regression")
    return out


# ----------------------------------------------------------------- text ----
def write_text(analyzer, scoring, limit=200, path=None):
    path = path or os.path.join(OUT_DIR, f"cheatsheet_{scoring}.txt")
    L = []
    L.append(f"FANTASY DRAFT CHEAT SHEET  --  {config.TEAMS}-team {config.DRAFT_TYPE}, {scoring.upper()} scoring")
    L.append("=" * 100)
    L.append("")
    L.append(plan.render_budget())
    L.append("")
    L.append(plan.render_timeline(analyzer))
    L.append("")

    L.append("=" * 100)
    L.append("BY POSITION  --  draft down each column; the dashed lines are real drop-offs")
    L.append("=" * 100)
    for pos in SHEET_POSITIONS:
        lst = [p for p in analyzer.ranked if p.pos == pos][:DEPTH.get(pos, 30)]
        if not lst:
            continue
        budget = engine.roster_plan().get(pos, {})
        L.append("")
        L.append(f"--- {pos}  (draft {budget.get('target', 0)}, start {budget.get('must_start', 0)}) "
                 + "-" * 40)
        L.append(f"    {'#':<4}{'PLAYER':<26}{'TM':<4}{'PROJ':>6}{'LAST':>6}{'VOR':>7}{'ADP':>6}{'BYE':>5}  NOTES")
        tier = None
        for p in lst:
            if p.vtier != tier:
                L.append(f"    {'':4}------------------ tier {p.vtier} ------------------")
                tier = p.vtier
            L.append(f"    {p.pos_rank:<4}{p.name[:25]:<26}{p.team:<4}{(p.proj or 0):>6.0f}"
                     f"{(p.last if p.last is not None else 0):>6.0f}{p.vor:>7.1f}"
                     f"{(p.adp if p.adp else 0):>6.0f}{(p.bye or 0):>5}  {', '.join(_notes(p))}")

    L.append("")
    L.append("=" * 100)
    L.append("OVERALL BOARD  --  if you have no idea who to take, take the top name still available")
    L.append("=" * 100)
    L.append(f"{'#':>4} {'PLAYER':<28}{'POS':<6}{'TM':<4}{'PROJ':>7}{'LAST':>7}{'VOR':>7}{'ADP':>6}{'BYE':>5}  NOTES")
    L.append("-" * 100)
    for p in analyzer.ranked[:limit]:
        L.append(f"{p.rank:>4} {p.name[:27]:<28}{p.pos + str(p.pos_rank):<6}{p.team:<4}"
                 f"{(p.proj or 0):>7.0f}{(p.last if p.last is not None else 0):>7.0f}"
                 f"{p.vor:>7.1f}{(p.adp if p.adp else 0):>6.0f}{(p.bye or 0):>5}  {', '.join(_notes(p))}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


# ----------------------------------------------------------------- html ----
CSS = """
body{font:12px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:16px;color:#111}
h1{font-size:18px;margin:0 0 2px}
h2{font-size:13px;margin:18px 0 7px;border-bottom:2px solid #222;padding-bottom:3px;text-transform:uppercase;letter-spacing:.04em}
.sub{color:#555;font-size:11px;margin-bottom:12px}
table{border-collapse:collapse;width:100%;margin-bottom:12px}
th{background:#222;color:#fff;text-align:left;padding:3px 5px;font-size:9.5px;text-transform:uppercase}
td{padding:2px 5px;border-bottom:1px solid #e8e8e8}
tr:nth-child(even) td{background:#fafafa}
.num{text-align:right;font-variant-numeric:tabular-nums}
.QB{color:#a8710a}.RB{color:#12762f}.WR{color:#0b63a8}.TE{color:#8a2ba8}.K,.DST{color:#666}
.note{color:#b00;font-size:9.5px}

/* the position grid -- the main event */
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.col{break-inside:avoid}
.col h3{font-size:12px;margin:0 0 4px;padding:4px 6px;color:#fff;border-radius:3px 3px 0 0}
.col h3 .budget{float:right;font-weight:400;font-size:10px;opacity:.9}
.col.RB h3{background:#12762f}.col.WR h3{background:#0b63a8}
.col.TE h3{background:#8a2ba8}.col.QB h3{background:#a8710a}
.col.K h3,.col.DST h3{background:#666}
.ptable{width:100%;border-collapse:collapse;font-size:10.5px}
.ptable td{padding:1.5px 4px;border-bottom:1px solid #eee}
.ptable .r{color:#999;width:16px;text-align:right}
.ptable .n{font-weight:600}
.ptable .m{color:#777;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tierbreak td{background:#eee;color:#555;font-size:9px;padding:1px 4px;letter-spacing:.05em}
.box{border:1px solid #ccc;border-left:4px solid #222;padding:8px 11px;margin:0 0 14px;background:#fcfcfc}
.box table{margin:6px 0 0}
.box th{background:none;color:#222;border-bottom:1px solid #999}
.box td{border-bottom:1px solid #eee}
.why{color:#555;font-size:10.5px}
.tl{font-size:10.5px;margin:2px 0}
.tl b{display:inline-block;width:34px}
.tl span{display:inline-block;background:#f0f0f0;border-radius:3px;padding:1px 6px;margin-right:5px}
@media print{body{margin:6px;font-size:10px}h2{page-break-after:avoid}.col{page-break-inside:avoid}}
"""


def write_html(analyzer, scoring, limit=200, path=None):
    path = path or os.path.join(OUT_DIR, f"cheatsheet_{scoring}.html")
    e = html.escape
    budget = engine.roster_plan()
    notes = engine.plan_notes()
    o = [f"<!doctype html><meta charset='utf-8'>"
         f"<title>Draft Cheat Sheet ({scoring.upper()})</title><style>{CSS}</style>"]
    o.append(f"<h1>Draft Cheat Sheet &mdash; {config.TEAMS}-team {config.DRAFT_TYPE}, {scoring.upper()}</h1>")
    o.append(f"<div class='sub'>PROJ = projected {config.PROJECTION_SEASON} points &middot; "
             f"LAST = actual {config.ACTUALS_SEASON} &middot; "
             f"VOR = points above a freely-available starter (the number that matters) &middot; "
             f"ADP = where he usually goes</div>")

    # --- the plan box ---
    o.append("<div class='box'><b>HOW MANY OF EACH TO DRAFT</b>"
             "<table><tr><th>Pos</th><th class='num'>Start</th><th class='num'>Draft</th><th>Why</th></tr>")
    for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
        d = budget.get(pos, {})
        o.append(f"<tr><td class='{pos}'><b>{pos}</b></td>"
                 f"<td class='num'>{d.get('must_start', 0)}</td>"
                 f"<td class='num'><b>{d.get('target', 0)}</b></td>"
                 f"<td class='why'>{e(notes.get(pos, ''))}</td></tr>")
    flex = config.STARTERS.get("FLEX", 0)
    o.append(f"</table><div class='why' style='margin-top:6px'>"
             f"{sum(v.get('must_start', 0) for v in budget.values())} starters"
             + (f" + {flex} FLEX (any RB/WR/TE)" if flex else "")
             + f" + {config.BENCH} bench = <b>{config.roster_size()} picks</b></div></div>")

    # --- how long can you wait ---
    o.append("<div class='box'><b>HOW LONG CAN YOU WAIT?</b> "
             "<span class='why'>the pick by which each group is usually gone</span>")
    for pos in ("RB", "WR", "TE", "QB"):
        rows = engine.position_timeline(analyzer, pos, max_tiers=4)
        if not rows:
            continue
        spans, run = [], 0
        for r in rows:
            run += r["count"]
            gb = f"{r['gone_by']:.0f}" if r["gone_by"] else "?"
            spans.append(f"<span>top {run} by pick ~{gb}</span>")
        o.append(f"<div class='tl'><b class='{pos}'>{pos}</b>" + "".join(spans) + "</div>")
    o.append("</div>")

    # --- position columns: the main event ---
    o.append("<h2>By position</h2><div class='grid'>")
    for pos in SHEET_POSITIONS:
        lst = [p for p in analyzer.ranked if p.pos == pos][:DEPTH.get(pos, 30)]
        if not lst:
            continue
        d = budget.get(pos, {})
        o.append(f"<div class='col {pos}'><h3>{pos}"
                 f"<span class='budget'>draft {d.get('target', 0)} &middot; start {d.get('must_start', 0)}</span></h3>"
                 f"<table class='ptable'>")
        tier = None
        for p in lst:
            if p.vtier != tier:
                o.append(f"<tr class='tierbreak'><td colspan='3'>TIER {p.vtier}</td></tr>")
                tier = p.vtier
            nts = _notes(p)
            flag = f" <span class='note'>{e(nts[0])}</span>" if nts else ""
            o.append(f"<tr><td class='r'>{p.pos_rank}</td>"
                     f"<td><span class='n'>{e(p.name)}</span> "
                     f"<span style='color:#888'>{e(p.team)}</span>{flag}</td>"
                     f"<td class='m'>{(p.proj or 0):.0f} &middot; bye {p.bye or '-'}</td></tr>")
        o.append("</table></div>")
    o.append("</div>")

    # --- overall board ---
    o.append("<h2>Overall board</h2>"
             "<div class='sub'>If you're stuck, take the highest name still available that fits a position you still need.</div>"
             "<table><tr><th>#</th><th>Player</th><th>Pos</th><th>Tm</th><th class='num'>Tier</th>"
             "<th class='num'>Proj</th><th class='num'>Last</th><th class='num'>VOR</th>"
             "<th class='num'>ADP</th><th class='num'>Bye</th><th>Notes</th></tr>")
    for p in analyzer.ranked[:limit]:
        o.append(f"<tr><td class='num'>{p.rank}</td><td>{e(p.name)}</td>"
                 f"<td class='{p.pos}'><b>{p.pos}{p.pos_rank}</b></td><td>{e(p.team)}</td>"
                 f"<td class='num'>{p.vtier or '-'}</td><td class='num'>{(p.proj or 0):.0f}</td>"
                 f"<td class='num'>{(p.last if p.last is not None else 0):.0f}</td>"
                 f"<td class='num'>{p.vor:.1f}</td><td class='num'>{(p.adp if p.adp else 0):.0f}</td>"
                 f"<td class='num'>{p.bye or ''}</td>"
                 f"<td class='note'>{e(', '.join(_notes(p)))}</td></tr>")
    o.append("</table>")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    return path


def write_all(analyzer, scoring, limit=200):
    t = write_text(analyzer, scoring, limit)
    h = write_html(analyzer, scoring, limit)
    return f"{os.path.basename(t)} and {os.path.basename(h)}"
