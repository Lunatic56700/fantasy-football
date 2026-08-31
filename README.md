# Fantasy Football Draft Helper

A draft-day assistant for people who don't follow football closely. It pulls real
data — last season's actual scoring, this season's projections, average draft
position, and the consensus of 100+ expert analysts — and tells you who to take
next and *why*, in plain English.

Built for a **10-team snake draft**. Scoring format is a one-line toggle.

---

## Draft day in 60 seconds

```bash
python3 draft.py update      # refresh the data (do this right before the draft)
python3 draft.py plan        # how many of each position you need  <- read this first
python3 draft.py sheet       # make a printable cheat sheet
python3 draft.py live        # open the live draft board
```

It'll ask which pick you have in round 1. Then, as each pick happens in your
real draft, **just type the player's name**. The tool marks them gone and, when
it's your turn, shows you the best available picks with reasons.

```
> gibbs
  pick 1: Team 1 -> Jahmyr Gibbs (RB-DET)

==============================================================================
 Round 1  |  Pick 4  |  YOUR PICK
==============================================================================

BEST PICKS FOR YOU  (still need: QBx1, RBx2, WRx2, TEx1, Kx1, DSTx1, FLEXx1)

 => 1. Jonathan Taylor                RB4    IND  T1  proj 254  VOR 98
        - fills your empty RB slot
        - 3 left in this RB tier -- big drop after
        - almost certainly gone by pick 17
        - projected down on last year (339 -> 254)
```

Partial names work (`gibbs`, `jamarr`, `st brown`). If it's ambiguous it asks.

No `pip install` needed — it's all standard library Python 3.

---

## How many of each position do you need?

You have **15 roster spots** and you can't just take running backs. Run
`python3 draft.py plan` and it prints this:

| Pos | You start | Draft this many | Why |
|---|---|---|---|
| **QB** | 1 | **1** | You only start one, and late-round QBs score nearly as much. Don't reach. |
| **RB** | 2 | **5** | You start 2, plus they fill your FLEX. They get hurt the most, so carry extras. |
| **WR** | 2 | **5** | You start 2, plus they fill your FLEX. Deepest position — good ones last into the middle rounds. |
| **TE** | 1 | **2** | Get a top-3 guy early or wait until late. The middle is a dead zone. |
| **K** | 1 | **1** | Interchangeable. **Last round, never earlier.** |
| **DST** | 1 | **1** | Nearly interchangeable. Second-to-last round. |

That's 8 starters + 1 FLEX + 6 bench = 15 picks. These numbers aren't
hardcoded — they're computed from your league settings, so if you change the
roster in `ff/config.py` they change too.

**FLEX** means one extra slot you can fill with any RB, WR, or TE. That's why
you draft more RBs and WRs than you start.

### How long can you wait?

The other half of the question. This is measured from real draft data — the
pick by which each group is typically gone:

```
RB   top 5 by pick ~8   | top 12 by ~18  | top 16 by ~32  | top 24 by ~60
WR   top 5 by pick ~12  | top 10 by ~24  | top 21 by ~47  | top 29 by ~71
TE   top 1 by pick ~22  | top 3  by ~44  | top 4  by ~51  | top 8  by ~77
QB   top 2 by pick ~35  | top 6  by ~69  | top 10 by ~98  | top 20 by ~189
```

Read it as: *elite running backs are gone by pick 8, but you can still get a
top-10 quarterback at pick 98.* That's the whole argument for waiting on QB.

### Your likely draft, round by round

`python3 draft.py plan --slot 4` simulates the draft — everyone else picking by
average draft position, you picking by value — and shows the shape of it:

```
  R1       4   RB    Jonathan Taylor       RB1
  R2      17   TE    Brock Bowers          RB1 TE1
  R3      24   WR    George Pickens        RB1 WR1 TE1
  R4      37   RB    Travis Etienne        RB2 WR1 TE1
  ...
  R13    124   DST   Philadelphia Eagles
  R14    137   K     Ka'imi Fairbairn
  Ends with: 1 QB, 5 RB, 5 WR, 2 TE, 1 K, 1 DST
```

Real drafts wander, so treat it as a shape, not a script. During the live
draft the tool tracks this for you and won't let you overload a position.

---

## The one concept worth understanding: VOR

**VOR = Value Over Replacement.** It's the number that should drive your picks,
and it's why the tool sometimes recommends a *lower*-projected player.

Last season Josh Allen (QB) scored the most fantasy points of anyone — 375. So
why does this tool rank him 22nd instead of 1st?

Because you only start **one** quarterback, and there are plenty of good ones.
A QB you can get much later still projects for ~292. So all of Allen's monster
production only gains you about **70 points over a replacement quarterback**.

Compare Jahmyr Gibbs: he projects for 300, but the 22nd-best running back —
the last one who starts every week in a 10-team league — projects for only 156.
Gibbs gains you **144 points** over what's freely available.

> Allen scores more. Gibbs *wins you more games.* That gap is VOR, and it's the
> whole game. **Draft the biggest VOR, not the biggest projection.**

This is why you don't take a quarterback early, and why kickers and defenses
are near-worthless picks until the very end.

---

## What the numbers mean

| Column | Meaning |
|---|---|
| **PROJ** | Projected points for the 2026 season |
| **LAST** | What he *actually* scored in 2025 |
| **VOR** | Points above a freely-available starter at his position — **the number that matters** |
| **ADP** | Average Draft Position: where he normally gets picked |
| **ECR** | Expert Consensus Rank, averaged across 100+ analysts |
| **TIER** | Players in a tier are roughly interchangeable. A tier ending is a cliff |
| **BYE** | The week he doesn't play |

**Tiers are the most useful idea for a beginner.** If 6 players are left in a
tier, relax — you can wait. If 1 is left, the drop after him is real, and that's
when you reach.

---

## Commands in the live board

| Command | What it does |
|---|---|
| `<name>` | Record a pick for whoever's on the clock |
| `me <name>` | Force a pick onto your team |
| `b` | Your best picks right now, with reasons |
| `l` / `l RB` | Best available, overall or by position |
| `r` | Your lineup, bench, and position progress |
| `plan` | How many of each position to draft, and how long you can wait |
| `teams` | Every team's roster |
| `p <name>` | Full detail on one player |
| `top` / `top RB` | Last season's actual best scorers |
| `u` | Undo the last pick |
| `scoring ppr` | Switch format and recompute everything instantly |
| `sheet` | Write a fresh cheat sheet |
| `save` / `load` | Save or restore progress (autosaves after every pick) |
| `q` | Quit |

---

## Switching scoring format

If you find out mid-draft that your league is full PPR, just type:

```
> scoring ppr
  scoring switched to PPR -- all rankings recomputed
```

Your drafted players are preserved and the whole board re-ranks. To change the
default permanently, edit `SCORING` in `ff/config.py` (`"std"`, `"half"`, or
`"ppr"`). You can also run any command with `--scoring ppr`.

**Which is which?** PPR gives 1 point per catch, half-PPR gives 0.5, standard
gives none. More PPR = pass-catchers (wide receivers, receiving backs) are worth
more. If you truly can't find out, **half-PPR is the most common default** and is
what this ships with.

---

## What the tool weighs when it recommends someone

- **VOR** — the base value, as above
- **Your roster needs** — an empty starting slot is worth far more than a backup
- **Tier cliffs** — if his tier is nearly empty, waiting costs you real points
- **Will he last?** — if he'll likely still be there at your next pick, it
  nudges you toward the guy who won't be
- **Value vs ADP** — a player falling well past his usual draft slot is a bargain
- **Expert disagreement** — a wide best/worst spread means boom-or-bust
- **Injuries**, **bye-week pileups**, and **year-over-year swings**
- **Position caps** — it won't let you stack 4 quarterbacks, and it holds
  kickers and defenses until the last two rounds

---

## Draft strategy, in short

Grounded in what the analysts are actually saying for 2026:

1. **Round 1: take the best running back available.** There's a clear gap
   between the top two backs (Gibbs, Bijan Robinson) and everyone else. Elite
   RBs are the scarcest thing in fantasy.
2. **Rounds 2–6: fill your starting receivers and a second back.** Get to
   2 RB and 2 WR before you start drafting depth — this is where starting
   lineups get won.
3. **Don't draft a quarterback early.** The gap between QB1 and QB10 is small.
   Rounds 6–9 is fine.
4. **One elite tight end or wait entirely.** The position falls off a cliff
   after the top few; if you miss them, take one late.
5. **Kicker and defense in the last two rounds. Never earlier.** They're
   nearly interchangeable and change week to week.
6. **Watch the run alert.** When 4+ of the last 6 picks were the same position,
   that position is drying up — the tool warns you.

---

## Where the data comes from

| Source | What it provides |
|---|---|
| [Sleeper API](https://sleeper.com) | 2025 actual scoring, 2026 projections, ADP in all three formats, injury status |
| [FantasyPros](https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php) | Expert Consensus Rankings aggregated from 100+ analysts, tiers, and expert disagreement |

Everything is cached in `data/` and committed, so **the tool works with no
internet** — if the wifi dies at the draft, it still runs off the last pull.
Run `python3 draft.py update` before the draft to get same-day injury news.

---

## Other commands

```bash
python3 draft.py plan --slot 4              # position plan + round-by-round
python3 draft.py rank --pos RB --limit 40   # rankings, any position
python3 draft.py top --pos WR               # last season's actual leaders
python3 draft.py sheet --limit 250          # bigger cheat sheet
python3 draft.py --scoring ppr rank         # any command in another format
```

## League settings

Everything configurable lives in `ff/config.py` — team count, roster slots,
bench size, and how late to allow kickers and defenses.

---

## A caveat worth stating

Projections are estimates, and every source disagrees. This tool is a fast,
consistent second opinion that keeps you from the common beginner mistakes —
drafting a kicker in round 8, taking a fourth quarterback, missing a tier cliff.
It is not a guarantee. When the tool and your gut disagree on a player you
actually like, take your guy.
