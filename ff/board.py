"""The live draft board you actually sit in front of during the draft."""

import os
import sys

from . import config, engine, players as players_mod, sheet
from .advice import Recommender
from .players import norm_name
from .state import DraftState

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else str(text)


def bold(t):   return c(t, "1")
def dim(t):    return c(t, "2")
def green(t):  return c(t, "32")
def yellow(t): return c(t, "33")
def red(t):    return c(t, "31")
def cyan(t):   return c(t, "36")
def mag(t):    return c(t, "35")

POS_COLOR = {"RB": "32", "WR": "36", "TE": "35", "QB": "33", "K": "2", "DST": "2"}

# Anything that moves the draft forward redraws the board; the rest just prints.
STATE_CHANGING = {"me", "u", "undo", "load", "scoring", "gone", "took"}
KNOWN_COMMANDS = {
    "q", "quit", "exit", "h", "help", "?", "b", "best", "l", "list", "avail",
    "r", "roster", "teams", "p", "player", "top", "u", "undo", "scoring",
    "sheet", "save", "load", "me", "plan", "need", "gone", "took",
}


def pos_tag(p):
    return c(f"{p.pos}{p.pos_rank}", POS_COLOR.get(p.pos, "0"))


def find(analyzer, query, available_only=True, drafted_keys=None):
    """Fuzzy-find a player. Returns (exact_match, [candidates])."""
    q = norm_name(query)
    if not q:
        return None, []
    pool = analyzer.ranked
    if available_only and drafted_keys is not None:
        pool = [p for p in pool if p.key not in drafted_keys]

    exact = [p for p in pool if norm_name(p.name) == q]
    if len(exact) == 1:
        return exact[0], []
    if exact:
        return None, exact

    starts, contains = [], []
    for p in pool:
        n = norm_name(p.name)
        parts = n.split()
        if n.startswith(q) or (parts and parts[-1].startswith(q)):
            starts.append(p)
        elif q in n:
            contains.append(p)
        elif len(q.split()) > 1:
            # "ja chase" style: initials + last name
            toks = q.split()
            if parts and parts[-1].startswith(toks[-1]) and parts[0].startswith(toks[0]):
                starts.append(p)

    cands = starts or contains
    cands = sorted(cands, key=lambda x: x.rank)
    if len(cands) == 1:
        return cands[0], []
    return None, cands[:12]


def fmt_row(p, extra=""):
    inj = ""
    if p.injury and str(p.injury).lower() not in ("none", "null"):
        inj = red(f" [{p.injury}]")
    bye = dim(f" bye{p.bye}") if p.bye else ""
    proj = f"{p.proj:.0f}" if p.proj else "--"
    adp = f"{p.adp:.0f}" if p.adp else "--"
    return (f"{p.rank:>3}. {bold(p.name):<32} {pos_tag(p):<14} {p.team:<3}"
            f" proj {proj:>4}  VOR {p.vor:>6.1f}  ADP {adp:>4}{bye}{inj} {extra}")


class Board:
    def __init__(self, analyzer, slot, scoring, save_path=None):
        self.a = analyzer
        self.scoring = scoring
        self.state = DraftState(analyzer, slot)
        self.rec = Recommender(analyzer, self.state)
        self.save_path = save_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "draft_progress.json")

    # -- rendering ---------------------------------------------------------
    def header(self):
        s = self.state
        if s.is_complete():
            print(bold(green("\n  DRAFT COMPLETE")))
            return
        rnd = engine.pick_to_round(s.current_pick, s.teams)
        team = s.team_on_clock()
        who = bold(green("YOUR PICK")) if s.is_my_pick() else dim(f"Team {team} on the clock")
        nxt = s.my_next_pick()
        away = ""
        if not s.is_my_pick() and nxt:
            away = dim(f"  (your next pick: {nxt}, {nxt - s.current_pick} away)")
        print(f"\n{bold('='*78)}")
        print(f" Round {rnd}  |  Pick {s.current_pick}  |  {who}{away}")
        print(bold("=" * 78))

        alert = s.run_alert()
        if alert:
            pos, cnt, window = alert
            print(yellow(f"  ! RUN ALERT: {cnt} of the last {window} picks were {pos}s. "
                         f"They're drying up."))

    def show_best(self, n=6):
        s = self.state
        picks = self.rec.top(n=n)
        if not picks:
            print(dim("  nothing left to recommend"))
            return
        roster = s.my_roster()
        from . import plan as plan_mod
        bits = []
        for row in plan_mod.budget_rows(roster):
            if row["pos"] in ("K", "DST") and row["have"] == 0 and \
                    engine.pick_to_round(s.current_pick, s.teams) < config.LATE_ROUND_ONLY.get(row["pos"], 99):
                continue
            mark = green(f"{row['have']}/{row['target']}") if row["have"] >= row["target"] \
                else f"{row['have']}/{row['target']}"
            bits.append(f"{row['pos']} {mark}")
        print(f"\n{bold('BEST PICKS FOR YOU')}   {dim('have/want:')} " + dim(" | ").join(bits) + "\n")
        for i, (val, p, reasons, slot) in enumerate(picks, 1):
            marker = green("=>") if i == 1 else "  "
            tier = f"T{p.vtier}" if p.vtier else "--"
            print(f" {marker} {bold(str(i)+'.')} {bold(p.name):<30} {pos_tag(p):<14} {p.team:<4}"
                  f" {dim(tier)}  proj {p.proj or 0:.0f}  VOR {p.vor:.0f}")
            for r in reasons[:4]:
                print(f"        {dim('-')} {r}")
            print()

    def show_list(self, pos=None, n=15):
        avail = self.a.available(self.state.drafted_keys)
        if pos:
            pos = pos.upper()
            pos = {"DEF": "DST", "D": "DST"}.get(pos, pos)
            avail = [p for p in avail if p.pos == pos]
        print(f"\n{bold('BEST AVAILABLE' + (' - ' + pos if pos else ''))}\n")
        last_tier = None
        for p in avail[:n]:
            if p.vtier != last_tier and pos:
                print(dim(f"   -- tier {p.vtier} --"))
                last_tier = p.vtier
            print("  " + fmt_row(p))
        print()

    def show_roster(self, team=None):
        s = self.state
        team = team or s.slot
        r = s.rosters[team]
        title = "YOUR LINEUP" if team == s.slot else f"TEAM {team}"
        print(f"\n{bold(title)}\n")

        slots, bench = r.lineup()
        starting = 0.0
        for label, p in slots:
            if p is None:
                print(f"   {bold(label.ljust(6))}  {dim('-- empty --')}")
            else:
                starting += p.proj or 0
                bye = dim("  bye " + str(p.bye)) if p.bye else ""
                print(f"   {bold(label.ljust(6))}  {p.name:<28} "
                      f"{c(p.pos.ljust(4), POS_COLOR.get(p.pos, '0'))} {p.team:<4}"
                      f" proj {p.proj or 0:6.0f}{bye}")
        if bench:
            print(f"\n   {dim('BENCH')}")
            for p in bench:
                print(f"   {'':<6}  {dim(p.name.ljust(28))} "
                      f"{c(p.pos.ljust(4), POS_COLOR.get(p.pos, '0'))} {p.team:<4}"
                      f" proj {p.proj or 0:6.0f}")
        print(f"\n   {dim('projected starting points:')} {bold(f'{starting:.0f}')}")

        if team == s.slot:
            self.show_progress()
        byes = {w: len(v) for w, v in r.bye_weeks().items() if len(v) >= 3}
        if byes:
            print(yellow("   heavy bye weeks: " + ", ".join(
                f"wk{w} ({n} players)" for w, n in sorted(byes.items()))))
        print()

    def show_progress(self):
        """One line per position: how many you have vs how many you want."""
        from . import plan as plan_mod
        roster = self.state.my_roster()
        print(f"\n   {bold('POSITION PROGRESS')}")
        for row in plan_mod.budget_rows(roster):
            have, target = row["have"], row["target"]
            filled = "#" * min(have, target)
            empty = "." * max(0, target - have)
            over = "+" * max(0, have - target)
            bar = c(filled, POS_COLOR.get(row["pos"], "0")) + dim(empty) + yellow(over)
            still = max(0, target - have)
            tag = green("done") if still == 0 else f"need {still} more"
            print(f"   {row['pos']:<5} {bar:<24} {have}/{target}  {dim(tag)}")

    def show_plan(self):
        from . import plan as plan_mod
        print()
        print(plan_mod.render_budget(self.state.my_roster()))
        print()
        print(plan_mod.render_timeline(self.a))
        print()

    def show_all_rosters(self):
        for t in range(1, self.state.teams + 1):
            r = self.state.rosters[t]
            tag = bold(green("YOU")) if t == self.state.slot else f"Team {t}"
            names = ", ".join(f"{p.name} ({p.pos})" for p in r.players) or dim("--")
            print(f"  {tag:<16} {names}")
        print()

    def show_player(self, p):
        print(f"\n{bold(p.name)}  {pos_tag(p)}  {p.team}")
        print(f"  {dim('projected ' + str(config.PROJECTION_SEASON) + ':')} {p.proj or 0:.1f} pts"
              f"   {dim('over replacement:')} {p.vor:.1f}")
        if p.last is not None:
            gp = f" in {p.last_gp:.0f} games" if p.last_gp else ""
            print(f"  {dim('actual ' + str(config.ACTUALS_SEASON) + ':')} {p.last:.1f} pts{gp}")
        if p.ecr:
            print(f"  {dim('expert consensus rank:')} {p.ecr:.0f}"
                  + (f"  (tier {p.vtier})" if p.vtier else "")
                  + (f"   best {p.expert_best:.0f} / worst {p.expert_worst:.0f}" if p.expert_best else ""))
        if p.adp:
            print(f"  {dim('average draft position:')} {p.adp:.1f}")
        bits = []
        if p.age:  bits.append(f"age {p.age}")
        if p.bye:  bits.append(f"bye week {p.bye}")
        if p.injury and str(p.injury).lower() not in ("none", "null"):
            bits.append(red(f"injury: {p.injury}"))
        if bits:
            print("  " + dim(" | ".join(str(b) for b in bits)))
        if p.drafted_by:
            owner = "YOU" if p.drafted_by == self.state.slot else f"Team {p.drafted_by}"
            print(red(f"  ALREADY DRAFTED by {owner}"))
        print()

    def show_top_performers(self, n=15, pos=None):
        pool = [p for p in self.a.ranked if p.last is not None]
        if pos:
            pool = [p for p in pool if p.pos == pos.upper()]
        pool.sort(key=lambda x: -x.last)
        print(f"\n{bold(f'BEST ACTUAL PERFORMERS, {config.ACTUALS_SEASON} SEASON')} "
              f"{dim('(' + self.scoring + ' scoring)')}\n")
        for i, p in enumerate(pool[:n], 1):
            gone = red(" [drafted]") if p.key in self.state.drafted_keys else ""
            gp = f"{p.last_gp:.0f}g" if p.last_gp else "--"
            ppg = p.last / p.last_gp if p.last_gp else 0
            print(f" {i:>3}. {bold(p.name):<30} {pos_tag(p):<14} {p.team:<4}"
                  f" {p.last:>6.1f} pts  {gp:>4}  {ppg:>5.1f}/g"
                  f"   {dim('proj ' + (f'{p.proj:.0f}' if p.proj else '--'))}{gone}")
        print()

    # -- actions -----------------------------------------------------------
    def do_pick(self, query, to_me=False):
        s = self.state
        if s.is_complete():
            print(dim("  draft is over"))
            return
        p, cands = find(self.a, query, available_only=True, drafted_keys=s.drafted_keys)
        if p is None:
            if not cands:
                gone, _ = find(self.a, query, available_only=False)
                if gone is not None and gone.key in s.drafted_keys:
                    owner = "YOU" if gone.drafted_by == s.slot else f"Team {gone.drafted_by}"
                    print(red(f"  {gone.name} was already drafted by {owner}"))
                else:
                    print(red(f"  no available player matching '{query}'"))
                return
            print(yellow(f"  '{query}' matches several players -- be more specific:"))
            for cnd in cands:
                print(f"     {cnd.name} ({cnd.pos}-{cnd.team})")
            return

        team = s.team_on_clock()
        if to_me:
            team = s.slot
        was_mine = team == s.slot
        pick_no = s.current_pick
        s.draft(p, team)
        who = bold(green("YOU")) if was_mine else f"Team {team}"
        print(f"  pick {pick_no}: {who} -> {bold(p.name)} ({p.pos}-{p.team})")
        self.autosave()

    def autosave(self):
        try:
            self.state.save(self.save_path)
        except OSError:
            pass

    def switch_scoring(self, new):
        new = new.lower().strip()
        alias = {"standard": "std", "halfppr": "half", "half-ppr": "half", "0.5": "half", "1": "ppr", "full": "ppr"}
        new = alias.get(new, new)
        if new not in config.VALID_SCORING:
            print(red(f"  scoring must be one of: {', '.join(config.VALID_SCORING)}"))
            return
        drafted = [(pick, team, p.name, p.pos) for pick, team, p in self.state.history]
        pool, _ = players_mod.build(new)
        self.a = engine.Analyzer(pool, new)
        self.scoring = new
        old_slot = self.state.slot
        self.state = DraftState(self.a, old_slot)
        index = {(norm_name(p.name), p.pos): p for p in self.a.ranked}
        for pick, team, name, pos in drafted:
            p = index.get((norm_name(name), pos))
            if p:
                self.state.current_pick = pick
                self.state.draft(p, team)
        self.state.current_pick = len(drafted) + 1
        self.rec = Recommender(self.a, self.state)
        print(green(f"  scoring switched to {new.upper()} -- all rankings recomputed"))

    def prompt(self):
        """The input prompt says whose pick you're about to type in."""
        s = self.state
        if s.is_complete():
            return bold("draft over > ")
        if s.is_my_pick():
            return bold(green(f"pick {s.current_pick} -- YOUR PICK > "))
        return bold(f"pick {s.current_pick} (Team {s.team_on_clock()}) > ")

    # -- main loop ---------------------------------------------------------
    def help(self):
        print(f"""
{bold('COMMANDS')}  {dim('(just type a name to record a pick)')}

  {cyan('<name>')}          someone else took him -- marks him gone, advances the pick
  {cyan('gone <name>')}     same thing, spelled out
  {cyan('me <name>')}       YOU took him
  {cyan('b')} / best        show your best picks right now, with reasons
  {cyan('l')} / list [POS]  best available (optionally RB/WR/TE/QB/K/DST)
  {cyan('r')} / roster      your lineup, bench, and position progress
  {cyan('plan')}            how many of each position to draft, and how long you can wait
  {cyan('teams')}           every team's roster
  {cyan('p')} / player <n>  full detail on one player
  {cyan('top')} [POS]       last season's actual best scorers
  {cyan('u')} / undo        undo the last pick
  {cyan('scoring <fmt>')}   switch std / half / ppr and recompute everything
  {cyan('sheet')}           write a fresh printable cheat sheet
  {cyan('save')} / {cyan('load')}     save or restore draft progress
  {cyan('h')} / help        this list
  {cyan('q')} / quit        exit
""")

    def run(self):
        print(bold(cyan(f"\n  Fantasy draft helper -- {config.TEAMS}-team {config.DRAFT_TYPE}, "
                        f"{self.scoring.upper()} scoring, you pick at slot {self.state.slot}")))
        print(dim(f"  Your picks: {', '.join(str(x) for x in self.state.my_picks[:8])} ..."))
        print(dim("  As each player comes off the board, just type his name -- that marks"))
        print(dim("  him gone. Use 'me <name>' when the pick is yours. 'h' for all commands."))
        print(dim("  Wrong name? Type 'u' to undo.\n"))
        self.header()
        if self.state.is_my_pick():
            self.show_best()

        while True:
            try:
                raw = input("\n" + self.prompt()).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  bye")
                return
            if not raw:
                continue
            parts = raw.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd in ("q", "quit", "exit"):
                self.autosave()
                print(dim("  progress saved. good luck.\n"))
                return
            elif cmd in ("h", "help", "?"):
                self.help()
            elif cmd in ("b", "best"):
                self.show_best()
            elif cmd in ("l", "list", "avail"):
                self.show_list(arg or None, n=20 if arg else 15)
            elif cmd in ("r", "roster"):
                self.show_roster()
            elif cmd == "teams":
                self.show_all_rosters()
            elif cmd in ("plan", "need"):
                self.show_plan()
            elif cmd in ("p", "player"):
                if not arg:
                    print(dim("  usage: player <name>"))
                    continue
                p, cands = find(self.a, arg, available_only=False)
                if p:
                    self.show_player(p)
                elif cands:
                    for cnd in cands:
                        print(f"     {cnd.name} ({cnd.pos}-{cnd.team})")
                else:
                    print(red(f"  no player matching '{arg}'"))
            elif cmd == "top":
                self.show_top_performers(pos=arg or None)
            elif cmd in ("u", "undo"):
                p = self.state.undo()
                print(green(f"  undid pick: {p.name}") if p else dim("  nothing to undo"))
                self.autosave()
            elif cmd == "scoring":
                if arg:
                    self.switch_scoring(arg)
                else:
                    print(f"  scoring is {bold(self.scoring.upper())}"
                          f"  {dim('(scoring std|half|ppr to change)')}")
            elif cmd == "sheet":
                path = sheet.write_all(self.a, self.scoring)
                print(green(f"  wrote {path}"))
            elif cmd == "save":
                self.state.save(self.save_path)
                print(green(f"  saved to {self.save_path}"))
            elif cmd == "load":
                try:
                    n = self.state.load(self.save_path)
                    print(green(f"  restored {n} picks"))
                except (OSError, ValueError) as e:
                    print(red(f"  could not load: {e}"))
            elif cmd == "me":
                self.do_pick(arg, to_me=True)
            elif cmd in ("gone", "took"):
                # Same as typing the name -- just spelled out for clarity.
                self.do_pick(arg)
            else:
                self.do_pick(raw)

            # Only redraw the board when the draft state actually moved.
            if cmd in STATE_CHANGING or cmd not in KNOWN_COMMANDS:
                self.header()
                if self.state.is_my_pick() and not self.state.is_complete():
                    self.show_best()
