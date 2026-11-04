#!/usr/bin/env python3
"""Conway's Game of Life on a contribution-graph-shaped board, rendered as a
self-animating SVG (light mode).

  python3 life.py                       # seed from l03x's contribution calendar
  python3 life.py --seed pattern        # seed from PATTERN below
  python3 life.py --out path/to/life.svg

--seed calendar reads GH_TOKEN, or falls back to `gh auth token`.
"""
import argparse
import datetime as dt
import random
import json
import os
import subprocess
import urllib.request

# ---- board ---------------------------------------------------------------
COLS, ROWS = 53, 7          # same shape as the contribution graph
WRAP = True                 # torus: edges wrap around
MAX_GEN = 120               # cap on frames per animation loop
FRAME_MS = 250              # time per generation in the animation

# ---- seed when --seed pattern (7 rows, '#' = alive) -----------------------
# Placeholder: a few gliders. We'll pick the real pattern next.
PATTERN = [
    "..#......................#..........................",
    "...#......................#.........................",
    ".###....................###.........................",
    ".....................................#..............",
    "......................................#.............",
    "....................................###.............",
    ".....................................................",
]

# ---- style ---------------------------------------------------------------
CELL, GAP, RADIUS = 10, 3, 2
# cell colour by age: newborn -> long-lived (index 0..3)
LIGHT = {"bg": "#ffffff", "empty": "#ebedf0",
         "age": ["#9be9a8", "#40c463", "#30a14e", "#216e39"]}

# Cells added when the seed fizzles out (game ends within MIN_GEN steps).
# These all run long on a 53x7 torus.
MIN_GEN = 20
EXTRA_PATTERNS = {
    "lwss":   [".#..#", "#....", "#...#", "####."],   # spaceship, flies forever
    "glider": [".#.", "..#", "###"],                  # flies forever (diagonal, wraps)
    "rpent":  [".##", "##.", ".#."],                  # R-pentomino, ~60 gens of chaos
    "acorn":  [".#.....", "...#...", "##..###"],      # acorn, ~50 gens of chaos
}
# colour of the added cells (and their descendants), by age
EXTRA_AGE = ["#c8e1ff", "#79b8ff", "#2188ff", "#005cc5"]

GH_USER = "l03x"


# ---- seeding ---------------------------------------------------------------
def seed_from_pattern():
    alive = {}
    for r, line in enumerate(PATTERN[:ROWS]):
        for c, ch in enumerate(line[:COLS]):
            if ch == "#":
                alive[(c, r)] = 0
    return alive


def seed_from_calendar():
    """Alive = any day with contributions in the last year."""
    token = os.environ.get("GH_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    query = """query($u:String!){user(login:$u){contributionsCollection{
      contributionCalendar{weeks{contributionDays{contributionCount weekday}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"u": GH_USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    alive = {}
    for c, week in enumerate(weeks[-COLS:]):
        for day in week["contributionDays"]:
            if day["contributionCount"] > 0:
                alive[(c, day["weekday"])] = 0
    return alive


# ---- simulation ------------------------------------------------------------
# State: {cell: lineage}, lineage 0 = your contributions, 1 = added cells.
# Survivors keep their lineage; a newborn takes the majority lineage of its
# 3 parents (the "Immigration" variant of Life), so you can see who came from where.
def neighbours(c, r):
    for dc in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if dc == dr == 0:
                continue
            nc, nr = c + dc, r + dr
            if WRAP:
                yield nc % COLS, nr % ROWS
            elif 0 <= nc < COLS and 0 <= nr < ROWS:
                yield nc, nr


def step(alive):
    counts, parents = {}, {}
    for cell, lin in alive.items():
        for n in neighbours(*cell):
            counts[n] = counts.get(n, 0) + 1
            parents[n] = parents.get(n, 0) + lin
    nxt = {}
    for cell, n in counts.items():
        if cell in alive and n in (2, 3):
            nxt[cell] = alive[cell]
        elif cell not in alive and n == 3:
            nxt[cell] = 1 if parents[cell] >= 2 else 0
    return nxt


def simulate(seed):
    """Frames of {cell: (lineage, age)}. Stops on repeat, extinction, or MAX_GEN."""
    frames, seen = [], set()
    alive, ages = dict(seed), {cell: 0 for cell in seed}
    for _ in range(MAX_GEN):
        key = frozenset(alive.items())
        if key in seen or not alive:
            break
        seen.add(key)
        frames.append({cell: (lin, ages[cell]) for cell, lin in alive.items()})
        nxt = step(alive)
        ages = {cell: ages[cell] + 1 if cell in alive else 0 for cell in nxt}
        alive = nxt
    if not alive:                       # show the empty board briefly, then loop
        frames += [{}] * 4
    return frames


def add_pattern(seed, rng):
    """Drop one random extra pattern where it doesn't touch existing cells."""
    name = rng.choice(sorted(EXTRA_PATTERNS))
    pat = EXTRA_PATTERNS[name]
    if rng.random() < 0.5:                       # mirror -> other direction
        pat = [line[::-1] for line in pat]
    cells = [(c, r) for r, line in enumerate(pat) for c, ch in enumerate(line) if ch == "#"]
    spots = [(x, y) for x in range(COLS) for y in range(ROWS)]
    rng.shuffle(spots)
    for x, y in spots:
        placed = [((c + x) % COLS, (r + y) % ROWS) for c, r in cells]
        clear = all(((pc + dc) % COLS, (pr + dr) % ROWS) not in seed
                    for pc, pr in placed for dc in range(-2, 3) for dr in range(-2, 3))
        if clear:
            seed.update({cell: 1 for cell in placed})
            return name
    return None


# ---- rendering ------------------------------------------------------------
def age_bucket(age):
    return 0 if age == 0 else 1 if age < 3 else 2 if age < 8 else 3


def cell_path(cells):
    p = CELL + GAP
    return "".join(f"M{c*p} {r*p}h{CELL}v{CELL}h-{CELL}z" for c, r in sorted(cells))


def render(frames):
    p = CELL + GAP
    w, h = COLS * p - GAP, ROWS * p - GAP
    n = len(frames)
    total = n * FRAME_MS / 1000
    pct = 100 / n

    all_cells = {(c, r) for c in range(COLS) for r in range(ROWS)}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
           "<style>",
           f".f{{visibility:hidden;animation:show {total}s step-end infinite}}",
           f"@keyframes show{{0%{{visibility:visible}}{pct:.4f}%,100%{{visibility:hidden}}}}",
           f".e{{fill:{LIGHT['empty']}}}" + "".join(
               f".a{i}{{fill:{col}}}" for i, col in enumerate(LIGHT["age"])) + "".join(
               f".b{i}{{fill:{col}}}" for i, col in enumerate(EXTRA_AGE)),
           "</style>",
           f'<path class="e" d="{cell_path(all_cells)}"/>']
    for i, frame in enumerate(frames):
        buckets = {}
        for cell, (lin, age) in frame.items():
            buckets.setdefault("ab"[lin] + str(age_bucket(age)), []).append(cell)
        out.append(f'<g class="f" style="animation-delay:{i * FRAME_MS / 1000}s">')
        for cls, cells in sorted(buckets.items()):
            out.append(f'<path class="{cls}" d="{cell_path(cells)}"/>')
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", choices=["calendar", "pattern"], default="calendar")
    ap.add_argument("--out", default="life.svg")
    a = ap.parse_args()

    seed = seed_from_calendar() if a.seed == "calendar" else seed_from_pattern()
    frames = simulate(seed)
    rng = random.Random(str(dt.date.today()))   # same extras if rerun the same day
    for _ in range(5):
        if len(frames) > MIN_GEN:
            break
        added = add_pattern(seed, rng)
        if not added:
            break
        print(f"game ended after {len(frames)} steps, adding a {added}")
        frames = simulate(seed)
    svg = render(frames)

    with open(a.out, "w") as f:
        f.write(svg)
    print(f"{len(frames)} frames, {len(svg) // 1024} KiB -> {a.out}")


if __name__ == "__main__":
    main()
