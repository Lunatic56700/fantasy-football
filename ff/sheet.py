"""Printable cheat sheets -- one plain-text, one HTML you can print in colour."""

import html
import os

from . import config

OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rows(analyzer, limit):
    return analyzer.ranked[:limit]


def write_text(analyzer, scoring, limit=200, path=None):
    path = path or os.path.join(OUT_DIR, f"cheatsheet_{scoring}.txt")
    L = []
    L.append(f"FANTASY DRAFT CHEAT SHEET  --  {config.TEAMS}-team {config.DRAFT_TYPE}, {scoring.upper()} scoring")
    L.append(f"Projections for {config.PROJECTION_SEASON}; 'LAST' is actual {config.ACTUALS_SEASON} points.")
    L.append("VOR = points above a freely-available starter at that position. Higher = more valuable.")
    L.append("=" * 104)
    L.append(f"{'#':>4} {'PLAYER':<28}{'POS':<6}{'TM':<4}{'TIER':>5}{'PROJ':>7}{'LAST':>7}{'VOR':>7}{'ADP':>6}{'BYE':>5}  NOTES")
    L.append("-" * 104)
    for p in _rows(analyzer, limit):
        notes = []
        if p.injury and str(p.injury).lower() not in ("none", "null"):
            notes.append(str(p.injury))
        if p.expert_stdev and p.expert_stdev >= 12:
            notes.append("risky/divisive")
        if p.proj and p.last and p.last > 20:
            ch = (p.proj - p.last) / p.last
            if ch >= 0.30:
                notes.append("breakout")
            elif ch <= -0.25:
                notes.append("regression")
        L.append(f"{p.rank:>4} {p.name[:27]:<28}{p.pos + str(p.pos_rank):<6}{p.team:<4}"
                 f"{(p.tier if p.tier else '-'):>5}{(p.proj or 0):>7.0f}"
                 f"{(p.last if p.last is not None else 0):>7.0f}{p.vor:>7.1f}"
                 f"{(p.adp if p.adp else 0):>6.0f}{(p.bye or 0):>5}  {', '.join(notes)}")

    L.append("")
    L.append("BY POSITION")
    L.append("=" * 104)
    for pos in config.SKILL_POSITIONS:
        lst = [p for p in analyzer.ranked if p.pos == pos][:30]
        L.append(f"\n-- {pos} --")
        tier = None
        for p in lst:
            if p.tier != tier:
                L.append(f"   ---- tier {p.tier} ----")
                tier = p.tier
            L.append(f"   {p.pos_rank:>3}. {p.name[:26]:<27}{p.team:<4} proj {(p.proj or 0):>6.0f}"
                     f"  VOR {p.vor:>6.1f}  ADP {(p.adp if p.adp else 0):>5.0f}  bye {(p.bye or 0):>2}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


CSS = """
body{font:12px/1.4 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:18px;color:#111}
h1{font-size:17px;margin:0 0 2px} h2{font-size:13px;margin:16px 0 6px;border-bottom:2px solid #333;padding-bottom:2px}
.sub{color:#555;font-size:11px;margin-bottom:10px}
table{border-collapse:collapse;width:100%;margin-bottom:14px}
th{background:#222;color:#fff;text-align:left;padding:3px 5px;font-size:10px;text-transform:uppercase}
td{padding:2px 5px;border-bottom:1px solid #e5e5e5}
tr:nth-child(even) td{background:#fafafa}
.num{text-align:right;font-variant-numeric:tabular-nums}
.QB{color:#a8710a;font-weight:600}.RB{color:#12762f;font-weight:600}
.WR{color:#0b63a8;font-weight:600}.TE{color:#8a2ba8;font-weight:600}
.K,.DST{color:#777;font-weight:600}
.note{color:#b00;font-size:10px}
.cols{column-count:3;column-gap:16px}
.cols h3{font-size:11px;margin:8px 0 3px;background:#eee;padding:2px 4px}
.tier{background:#f0f0f0;font-size:10px;color:#555;padding:1px 4px}
.p{font-size:10.5px;padding:1px 0;break-inside:avoid}
@media print{body{margin:8px}h2{page-break-after:avoid}}
"""


def write_html(analyzer, scoring, limit=200, path=None):
    path = path or os.path.join(OUT_DIR, f"cheatsheet_{scoring}.html")
    e = html.escape
    out = [f"<!doctype html><meta charset='utf-8'><title>Draft Cheat Sheet ({scoring.upper()})</title><style>{CSS}</style>"]
    out.append(f"<h1>Fantasy Draft Cheat Sheet &mdash; {config.TEAMS}-team {config.DRAFT_TYPE}, {scoring.upper()} scoring</h1>")
    out.append(f"<div class='sub'>PROJ = projected {config.PROJECTION_SEASON} points &middot; "
               f"LAST = actual {config.ACTUALS_SEASON} points &middot; "
               f"VOR = points above a freely-available starter at that position (the number that matters) &middot; "
               f"ADP = where he usually gets drafted</div>")

    out.append("<h2>Overall board</h2><table><tr><th>#</th><th>Player</th><th>Pos</th><th>Tm</th>"
               "<th class='num'>Tier</th><th class='num'>Proj</th><th class='num'>Last</th>"
               "<th class='num'>VOR</th><th class='num'>ADP</th><th class='num'>Bye</th><th>Notes</th></tr>")
    for p in _rows(analyzer, limit):
        notes = []
        if p.injury and str(p.injury).lower() not in ("none", "null"):
            notes.append(str(p.injury))
        if p.expert_stdev and p.expert_stdev >= 12:
            notes.append("divisive")
        if p.proj and p.last and p.last > 20:
            ch = (p.proj - p.last) / p.last
            if ch >= 0.30:
                notes.append("breakout")
            elif ch <= -0.25:
                notes.append("regression")
        out.append(
            f"<tr><td class='num'>{p.rank}</td><td>{e(p.name)}</td>"
            f"<td class='{p.pos}'>{p.pos}{p.pos_rank}</td><td>{e(p.team)}</td>"
            f"<td class='num'>{p.tier or '-'}</td><td class='num'>{(p.proj or 0):.0f}</td>"
            f"<td class='num'>{(p.last if p.last is not None else 0):.0f}</td>"
            f"<td class='num'>{p.vor:.1f}</td><td class='num'>{(p.adp if p.adp else 0):.0f}</td>"
            f"<td class='num'>{p.bye or ''}</td><td class='note'>{e(', '.join(notes))}</td></tr>")
    out.append("</table>")

    out.append("<h2>By position, with tier breaks</h2><div class='cols'>")
    for pos in config.SKILL_POSITIONS:
        out.append(f"<h3 class='{pos}'>{pos}</h3>")
        tier = None
        for p in [x for x in analyzer.ranked if x.pos == pos][:28]:
            if p.tier != tier:
                out.append(f"<div class='tier'>tier {p.tier}</div>")
                tier = p.tier
            out.append(f"<div class='p'>{p.pos_rank}. <b>{e(p.name)}</b> {e(p.team)} "
                       f"<span style='color:#666'>{(p.proj or 0):.0f}pts &middot; bye {p.bye or '-'}</span></div>")
    out.append("</div>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return path


def write_all(analyzer, scoring, limit=200):
    t = write_text(analyzer, scoring, limit)
    h = write_html(analyzer, scoring, limit)
    return f"{os.path.basename(t)} and {os.path.basename(h)}"
