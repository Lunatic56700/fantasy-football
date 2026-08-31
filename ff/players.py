"""Merge every source into one clean list of players with real numbers on them."""

import re
import unicodedata

from . import config, fetch

# Sleeper uses different suffixes per scoring format.
PTS_KEY = {"std": "pts_std", "half": "pts_half_ppr", "ppr": "pts_ppr"}
ADP_KEY = {"std": "adp_std", "half": "adp_half_ppr", "ppr": "adp_ppr"}

POS_ALIAS = {"DEF": "DST", "D/ST": "DST", "PK": "K"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

TEAM_ALIAS = {"JAC": "JAX", "WSH": "WAS", "LAR": "LAR", "LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"}


def norm_name(name):
    """Normalise a player name so the two sources match up.

    'Amon-Ra St. Brown', 'James Cook III' and "Ja'Marr Chase" all have to
    survive a round trip between Sleeper and FantasyPros.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[.'’`]", "", s)     # periods and apostrophes vanish
    s = re.sub(r"[-/]", " ", s)           # hyphens become spaces
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    parts = [p for p in s.split() if p]
    while len(parts) > 2 and parts[-1] in SUFFIXES:
        parts.pop()
    return " ".join(parts)


def norm_pos(pos):
    p = (pos or "").upper()
    return POS_ALIAS.get(p, p)


def norm_team(team):
    t = (team or "FA").upper()
    return TEAM_ALIAS.get(t, t)


class Player:
    __slots__ = ("name", "pos", "team", "age", "bye", "injury", "proj", "last",
                 "last_gp", "proj_gp", "adp", "ecr", "tier", "expert_best",
                 "expert_worst", "expert_stdev", "expert_delta", "pos_rank",
                 "vor", "value", "sleeper_id", "drafted_by", "rank")

    def __init__(self, **kw):
        for s in self.__slots__:
            setattr(self, s, kw.get(s))
        self.drafted_by = None

    @property
    def key(self):
        return (norm_name(self.name), self.pos)

    @property
    def label(self):
        return f"{self.name} ({self.pos}-{self.team})"

    def __repr__(self):
        return f"<{self.name} {self.pos} {self.team} proj={self.proj}>"


def _num(d, key):
    try:
        v = d.get(key)
        return float(v) if v is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def build(scoring=None):
    """Build the merged player board for the given scoring format."""
    scoring = scoring or config.SCORING
    if scoring not in config.VALID_SCORING:
        raise ValueError(f"unknown scoring {scoring!r}")

    raw_players = fetch.load("players")
    projections = fetch.load("projections") or {}
    actuals = fetch.load("actuals") or {}
    experts_all = fetch.load("experts") or {}
    experts = (experts_all.get(scoring) or {}).get("players", [])

    if raw_players is None:
        raise RuntimeError("no cached data -- run: python3 draft.py update")

    pk, ak = PTS_KEY[scoring], ADP_KEY[scoring]
    players = {}

    # ---- Pass 1: everyone Sleeper knows about who is worth ranking ---------
    for pid, meta in raw_players.items():
        pos = norm_pos(meta.get("position"))
        if pos not in config.ALL_POSITIONS:
            continue
        if pos != "DST" and (meta.get("status") or "") not in ("Active", "Inactive", ""):
            # skip retired / practice-squad-only clutter, but keep DSTs
            pass

        proj = projections.get(pid) or {}
        act = actuals.get(pid) or {}
        proj_pts = _num(proj, pk)
        adp = _num(proj, ak)
        last_pts = _num(act, pk)

        # Nothing projected and nothing scored last year -> not draftable.
        if proj_pts is None and last_pts is None:
            continue

        name = meta.get("full_name") or " ".join(
            x for x in (meta.get("first_name"), meta.get("last_name")) if x
        ).strip()
        if pos == "DST" and not name:
            name = f"{meta.get('team') or pid} DST"
        if not name:
            continue

        if adp is not None and adp >= 999:
            adp = None

        p = Player(
            name=name,
            pos=pos,
            team=norm_team(meta.get("team")),
            age=meta.get("age"),
            injury=meta.get("injury_status"),
            proj=proj_pts,
            proj_gp=_num(proj, "gp"),
            last=last_pts,
            last_gp=_num(act, "gp"),
            adp=adp,
            sleeper_id=pid,
        )
        k = p.key
        # Prefer the record with a real projection if we see a duplicate name.
        if k not in players or (players[k].proj or -1) < (p.proj or -1):
            players[k] = p

    # ---- Pass 2: layer the expert consensus on top ------------------------
    by_name = {}
    for p in players.values():
        by_name.setdefault(norm_name(p.name), []).append(p)

    # Defenses are named by city in one source and by team code in the other,
    # so index them by team as a fallback.
    dst_by_team = {p.team: p for p in players.values() if p.pos == "DST"}

    matched = 0
    for e in experts:
        pos = norm_pos(e["pos"])
        n = norm_name(e["name"])
        target = players.get((n, pos))
        if target is None:
            # fall back to name-only (positions occasionally disagree)
            cands = by_name.get(n, [])
            if len(cands) == 1:
                target = cands[0]
            elif cands:
                same_team = [c for c in cands if c.team == norm_team(e["team"])]
                target = same_team[0] if same_team else cands[0]
        if target is None and pos == "DST":
            target = dst_by_team.get(norm_team(e["team"]))
        if target is None:
            continue
        target.ecr = e["ecr"]
        target.tier = e["tier"]
        target.expert_best = e["best"]
        target.expert_worst = e["worst"]
        target.expert_stdev = e["stdev"]
        target.expert_delta = e["delta"]
        if e.get("bye"):
            try:
                target.bye = int(e["bye"])
            except (TypeError, ValueError):
                pass
        matched += 1

    return list(players.values()), matched
