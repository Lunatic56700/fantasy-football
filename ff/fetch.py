"""Download and cache every data source. Standard library only.

Sources
-------
Sleeper (public, no key)
    - players/nfl                 name, team, position, age, injury status
    - stats/nfl/regular/2025      what players ACTUALLY scored last season
    - projections/nfl/regular/26  projected points + ADP in all 3 formats

FantasyPros (public HTML with an embedded JSON blob)
    - Expert Consensus Rankings aggregated from 100+ analysts, including
      tiers and how much the experts DISAGREE about each player.

Everything is cached under data/ so the draft board runs offline. If the
wifi dies at the draft, the tool still works off the last good pull.
"""

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

from . import config

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

SLEEPER = {
    "players":     "https://api.sleeper.app/v1/players/nfl",
    "actuals":     f"https://api.sleeper.app/v1/stats/nfl/regular/{config.ACTUALS_SEASON}",
    "projections": f"https://api.sleeper.app/v1/projections/nfl/regular/{config.PROJECTION_SEASON}",
}

# FantasyPros expert consensus, one page per scoring format.
FANTASYPROS = {
    "std":  "https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php",
    "half": "https://www.fantasypros.com/nfl/rankings/half-point-ppr-cheatsheets.php",
    "ppr":  "https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php",
}


def _get(url, timeout=60, retries=3):
    """Fetch a URL with retries and exponential backoff."""
    ctx = ssl.create_default_context()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/json,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"could not fetch {url}: {last}")


def _cache_path(name):
    return os.path.join(DATA_DIR, f"{name}.json")


def _save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _cache_path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, _cache_path(name))


def load(name):
    """Load a cached source. Returns None if we've never fetched it."""
    path = _cache_path(name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cache_age_hours(name):
    path = _cache_path(name)
    if not os.path.exists(path):
        return None
    return (time.time() - os.path.getmtime(path)) / 3600.0


def parse_fantasypros(html):
    """Pull the embedded expert-consensus JSON out of a FantasyPros page."""
    m = re.search(r"var ecrData\s*=\s*(\{.*?\});\s*\n", html, re.S)
    if not m:
        raise ValueError("FantasyPros page format changed: no ecrData block found")
    data = json.loads(m.group(1))
    players = []
    for p in data.get("players", []):
        pos = (p.get("player_position_id") or "").upper()
        try:
            ecr = float(p.get("rank_ecr"))
        except (TypeError, ValueError):
            continue
        def _f(key):
            try:
                return float(p.get(key))
            except (TypeError, ValueError):
                return None
        players.append({
            "name": p.get("player_name"),
            "team": (p.get("player_team_id") or "FA").upper(),
            "pos": pos,
            "ecr": ecr,
            "tier": p.get("tier"),
            "pos_rank": p.get("pos_rank"),
            "best": _f("rank_min"),
            "worst": _f("rank_max"),
            "stdev": _f("rank_std"),
            "bye": p.get("player_bye_week"),
            # How much the consensus has moved recently -- positive = rising.
            "delta": _f("player_ecr_delta"),
        })
    return {"type": data.get("type"), "year": data.get("year"), "players": players}


# Fields we actually use off a Sleeper player record.
KEEP_FIELDS = ("first_name", "last_name", "full_name", "position", "team",
               "age", "injury_status", "status", "years_exp")


def trim_players(raw, projections, actuals):
    """Sleeper ships 12k players including practice squads -- ~14MB.

    Keep only the ones who are actually draftable, so the cache is small
    enough to commit and the tool works with no internet at the draft.
    """
    from . import config
    keep = {}
    for pid, meta in raw.items():
        pos = (meta.get("position") or "").upper()
        pos = {"DEF": "DST", "PK": "K"}.get(pos, pos)
        if pos not in config.ALL_POSITIONS:
            continue
        if pid not in projections and pid not in actuals:
            continue
        keep[pid] = {k: meta.get(k) for k in KEEP_FIELDS if meta.get(k) is not None}
    return keep


def refresh(verbose=True):
    """Pull every source fresh and cache it. Returns a status dict."""
    status = {}
    fetched = {}

    for name, url in SLEEPER.items():
        if verbose:
            print(f"  fetching sleeper/{name} ...", end="", flush=True)
        try:
            fetched[name] = json.loads(_get(url))
            status[name] = "ok"
            if verbose:
                print(" ok")
        except Exception as e:
            status[name] = f"failed: {e}"
            if verbose:
                print(f" FAILED ({e})")

    projections = fetched.get("projections", load("projections") or {})
    actuals = fetched.get("actuals", load("actuals") or {})
    if "projections" in fetched:
        _save("projections", fetched["projections"])
    if "actuals" in fetched:
        _save("actuals", fetched["actuals"])
    if "players" in fetched:
        slim = trim_players(fetched["players"], projections, actuals)
        _save("players", slim)
        if verbose:
            print(f"  trimmed player list to {len(slim)} draftable players")

    experts = {}
    for scoring, url in FANTASYPROS.items():
        if verbose:
            print(f"  fetching fantasypros/{scoring} ...", end="", flush=True)
        try:
            experts[scoring] = parse_fantasypros(_get(url))
            status[f"experts_{scoring}"] = "ok"
            if verbose:
                print(f" ok ({len(experts[scoring]['players'])} players)")
        except Exception as e:
            status[f"experts_{scoring}"] = f"failed: {e}"
            if verbose:
                print(f" FAILED ({e})")

    if experts:
        old = load("experts") or {}
        old.update(experts)
        _save("experts", old)

    _save("meta", {"fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"), "status": status})
    return status


def have_data():
    """True if we have enough cached data to run."""
    return all(load(n) is not None for n in ("players", "projections", "experts"))
