#!/usr/bin/env python3
"""Fantasy football draft helper.

Quick start on draft day:

    python3 draft.py update      # refresh the data (do this once, before the draft)
    python3 draft.py sheet       # print-friendly cheat sheet
    python3 draft.py live        # the interactive draft board

Everything runs on the Python standard library. No pip install.
"""

import argparse
import sys

from ff import config, engine, fetch, players, sheet
from ff.board import Board


def build_analyzer(scoring):
    pool, matched = players.build(scoring)
    return engine.Analyzer(pool, scoring), len(pool), matched


def cmd_update(args):
    print("Refreshing player data...")
    status = fetch.refresh()
    failed = {k: v for k, v in status.items() if v != "ok"}
    print()
    if failed:
        print("Some sources failed:")
        for k, v in failed.items():
            print(f"  {k}: {v}")
        if fetch.have_data():
            print("\nCached data from an earlier run is still in place, so the tool will work.")
        else:
            print("\nNo usable cached data. Check your internet connection and try again.")
            return 1
    else:
        print("All sources updated.")
    a, n, matched = build_analyzer(args.scoring)
    print(f"{n} players ranked, {matched} matched to expert consensus rankings.")
    return 0


def cmd_sheet(args):
    a, n, _ = build_analyzer(args.scoring)
    t = sheet.write_text(a, args.scoring, args.limit)
    h = sheet.write_html(a, args.scoring, args.limit)
    print(f"Wrote:\n  {t}\n  {h}")
    print(f"\nOpen the .html file in a browser and print it, or keep the .txt open in a window.")
    return 0


def cmd_rank(args):
    a, _, _ = build_analyzer(args.scoring)
    pool = a.ranked
    if args.pos:
        pool = [p for p in pool if p.pos == args.pos.upper()]
    print(f"{'#':>4}  {'PLAYER':<28}{'POS':<6}{'TM':<5}{'PROJ':>7}{'LAST':>7}{'VOR':>8}{'ADP':>7}{'ECR':>6}")
    print("-" * 82)
    for p in pool[:args.limit]:
        print(f"{p.rank:>4}  {p.name[:27]:<28}{p.pos + str(p.pos_rank):<6}{p.team:<5}"
              f"{(p.proj or 0):>7.0f}{(p.last if p.last is not None else 0):>7.0f}"
              f"{p.vor:>8.1f}{(p.adp if p.adp else 0):>7.0f}{(p.ecr if p.ecr else 0):>6.0f}")
    return 0


def cmd_top(args):
    a, _, _ = build_analyzer(args.scoring)
    pool = [p for p in a.ranked if p.last is not None]
    if args.pos:
        pool = [p for p in pool if p.pos == args.pos.upper()]
    pool.sort(key=lambda x: -x.last)
    print(f"Best actual performers, {config.ACTUALS_SEASON} season ({args.scoring} scoring)\n")
    print(f"{'#':>4}  {'PLAYER':<28}{'POS':<6}{'TM':<5}{'PTS':>8}{'GP':>5}{'PPG':>7}{'PROJ26':>8}")
    print("-" * 72)
    for i, p in enumerate(pool[:args.limit], 1):
        ppg = p.last / p.last_gp if p.last_gp else 0
        print(f"{i:>4}  {p.name[:27]:<28}{p.pos:<6}{p.team:<5}{p.last:>8.1f}"
              f"{(p.last_gp or 0):>5.0f}{ppg:>7.1f}{(p.proj or 0):>8.0f}")
    return 0


def cmd_live(args):
    a, n, matched = build_analyzer(args.scoring)
    slot = args.slot
    while slot is None or not (1 <= slot <= config.TEAMS):
        try:
            raw = input(f"Which pick do you have in round 1? (1-{config.TEAMS}): ").strip()
        except (EOFError, KeyboardInterrupt):
            return 1
        try:
            slot = int(raw)
        except ValueError:
            print("  enter a number")
            slot = None
            continue
        if not 1 <= slot <= config.TEAMS:
            print(f"  must be between 1 and {config.TEAMS}")
            slot = None

    age = fetch.cache_age_hours("projections")
    if age is not None and age > 24:
        print(f"  (heads up: your data is {age:.0f} hours old -- "
              f"run 'python3 draft.py update' to refresh)")

    Board(a, slot, args.scoring).run()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fantasy football draft helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--scoring", choices=config.VALID_SCORING, default=config.SCORING,
                    help=f"scoring format (default: {config.SCORING}, set in ff/config.py)")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("update", help="download the latest data")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("live", help="interactive draft board")
    p.add_argument("--slot", type=int, default=None, help="your first-round pick number")
    p.set_defaults(func=cmd_live)

    p = sub.add_parser("sheet", help="write printable cheat sheets")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(func=cmd_sheet)

    p = sub.add_parser("rank", help="print the rankings")
    p.add_argument("--pos", default=None, help="QB/RB/WR/TE/K/DST")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_rank)

    p = sub.add_parser("top", help="last season's best actual scorers")
    p.add_argument("--pos", default=None)
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_top)

    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        args.cmd = "live"
        args.slot = None
        args.func = cmd_live

    config.validate()
    if args.cmd != "update" and not fetch.have_data():
        print("No data yet. Run this first:\n    python3 draft.py update")
        return 1
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 1


if __name__ == "__main__":
    sys.exit(main())
