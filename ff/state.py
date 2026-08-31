"""Tracks what has happened in the draft so far."""

import json
import os

from . import config, engine
from .advice import Roster
from .players import norm_name


class DraftState:
    def __init__(self, analyzer, slot, teams=None, rounds=None):
        self.a = analyzer
        self.teams = teams or config.TEAMS
        self.rounds = rounds or config.total_rounds()
        self.slot = slot
        self.my_picks = engine.snake_picks(slot, self.teams, self.rounds)
        self.current_pick = 1
        self.drafted_keys = set()
        self.history = []          # (pick_no, team_idx, player)
        self.rosters = {i: Roster(f"Team {i}") for i in range(1, self.teams + 1)}
        self.rosters[slot].name = "YOU"

    # -- pick bookkeeping --------------------------------------------------
    def team_on_clock(self, pick=None):
        pick = pick or self.current_pick
        r = engine.pick_to_round(pick, self.teams)
        idx = (pick - 1) % self.teams
        return idx + 1 if r % 2 == 1 else self.teams - idx

    def is_my_pick(self, pick=None):
        return self.team_on_clock(pick) == self.slot

    def my_next_pick(self, after=None):
        after = after if after is not None else self.current_pick
        for p in self.my_picks:
            if p >= after and p <= self.teams * self.rounds:
                if p == after and self.is_my_pick(after):
                    continue
                return p
        return None

    def my_roster(self):
        return self.rosters[self.slot]

    def draft(self, player, team=None):
        team = team or self.team_on_clock()
        self.drafted_keys.add(player.key)
        player.drafted_by = team
        self.rosters[team].add(player)
        self.history.append((self.current_pick, team, player))
        self.current_pick += 1
        return team

    def undo(self):
        if not self.history:
            return None
        pick, team, player = self.history.pop()
        self.drafted_keys.discard(player.key)
        self.rosters[team].players = [p for p in self.rosters[team].players if p.key != player.key]
        player.drafted_by = None
        self.current_pick = pick
        return player

    def recent_positions(self, n=8):
        """Positions taken in the last n picks -- used to spot a positional run."""
        return [p.pos for _, _, p in self.history[-n:]]

    def run_alert(self, n=6, threshold=4):
        recent = self.recent_positions(n)
        counts = {}
        for pos in recent:
            counts[pos] = counts.get(pos, 0) + 1
        for pos, c in sorted(counts.items(), key=lambda x: -x[1]):
            if c >= threshold and pos in config.SKILL_POSITIONS:
                return pos, c, len(recent)
        return None

    def is_complete(self):
        return self.current_pick > self.teams * self.rounds

    # -- persistence -------------------------------------------------------
    def save(self, path):
        data = {
            "slot": self.slot, "teams": self.teams, "rounds": self.rounds,
            "scoring": self.a.scoring, "current_pick": self.current_pick,
            "history": [[pick, team, p.name, p.pos, p.team] for pick, team, p in self.history],
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)

    def load(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        index = {}
        for p in self.a.ranked:
            index.setdefault((norm_name(p.name), p.pos), p)
        self.current_pick = 1
        self.drafted_keys.clear()
        self.history.clear()
        for i in self.rosters:
            self.rosters[i].players = []
        restored = 0
        for pick, team, name, pos, _team_abbr in data.get("history", []):
            p = index.get((norm_name(name), pos))
            if p is None:
                continue
            self.current_pick = pick
            self.draft(p, team)
            restored += 1
        self.current_pick = data.get("current_pick", self.current_pick)
        return restored
