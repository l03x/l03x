#!/usr/bin/env python3
"""ASCII-art "L03X" that decodes out of random characters, then keeps glitching.

  python3 ascii_l03x.py --out l03x.svg

Intro: every cell scrambles through random characters and locks into place
at its own random moment until the banner is complete (plays once).
Loop: the finished banner with a few of its own characters glitching at
random (forever). Cells outside the name stay blank once settled.
"""
import argparse
import random
from xml.sax.saxutils import escape

ART = [
    '...                                                  ..',
    '  .zf"` `"tu       .n~~%x.       .x~~"*Weu.      .H88x.  :~)88:',
    " x88      '8N.   x88X   888.    d8Nu.  9888c    x888888X ~:8888",
    ' 888k     d88&  X888X   8888L   88888  98888   ~   "8888X  %88"',
    ' 8888N.  @888F X8888X   88888   "***"  9888%        X8888',
    ' `88888 9888%  88888X   88888X       ..@8*"      .xxX8888xxxd>',
    '   %888 "88F   88888X   88888X    ````"8Weu     :88888888888"',
    '    8"   "*h=~ 88888X   88888f   ..    ?8888L   ~   \'8888',
    "  z8Weu        48888X   88888  :@88N   '8888N  xx.  X8888:    .",
    ' ""88888i.   Z  ?888X   8888"  *8888~  \'8888F X888  X88888x.x"',
    '"   "8888888*    "88X   88*`   \'*8"`   9888%  X88% : \'%8888"',
    '      ^"**""       ^"==="`       `~===*%"`     "*=~    `""',
]
PAD_X, PAD_Y = 3, 1          # extra random cells around the art (they settle to blank)

CHARSET = "!#$%&*+-/0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_{|}~"
FRAME_MS = 70
INTRO_FRAMES = 58            # scramble -> name (~4 s)
SETTLE_MIN, SETTLE_MAX = 6, 54
JITTER = 0.35                # 0 = strict outside-in order, 1 = fully random
LOOP_FRAMES = 300            # glitch loop after the name is formed (~21 s)
GLITCH_RATE = 0.5            # chance per loop frame that new glitches start
GLITCH_LEN = (1, 4)          # frames a glitch lasts

FONT_PX, CHAR_W, LINE_H = 14, 8.4, 16
# colours readable on both GitHub themes (transparent background)
# s = settled name, x = scrambling, g = glitch (short names keep the file small)
COLOR = {"s": "#3fb950", "x": "#808080", "g": "#58a6ff"}
OPACITY = {"s": 1, "x": .55, "g": 1}

SEED = 3
# displayed width in px; 686 = life.svg (53 cells x 13 px - 3 px gap)
TARGET_WIDTH = 686


def build_grid():
    w = max(len(l) for l in ART) + 2 * PAD_X
    h = len(ART) + 2 * PAD_Y
    target = [[" "] * w for _ in range(h)]
    for r, line in enumerate(ART):
        for c, ch in enumerate(line):
            target[r + PAD_Y][c + PAD_X] = ch
    return target, w, h


def frames(rng, target, w, h):
    cells = [(r, c) for r in range(h) for c in range(w)]
    # Cells far from the name clear first; the name itself locks in last.
    # Distance is measured to the nearest name character, with rows counted
    # ~2x because a character cell is about twice as tall as it is wide.
    name = [cell for cell in cells if target[cell[0]][cell[1]] != " "]
    dist = {(r, c): min(((r - nr) * LINE_H / CHAR_W) ** 2 + (c - nc) ** 2
                        for nr, nc in name) ** .5
            for r, c in cells}
    far = max(dist.values()) or 1
    span = SETTLE_MAX - SETTLE_MIN
    settle = {}
    for cell in cells:
        t = SETTLE_MIN + (1 - dist[cell] / far) * span * (1 - JITTER)
        settle[cell] = round(t + rng.uniform(0, span * JITTER))

    intro = []
    for f in range(INTRO_FRAMES):
        frame = {}
        for (r, c) in cells:
            if f >= settle[(r, c)]:
                ch = target[r][c]
                if ch != " ":
                    frame[(r, c)] = (ch, "s")
            else:
                frame[(r, c)] = (rng.choice(CHARSET), "x")
        intro.append(frame)

    name_cells = [cell for cell in cells if target[cell[0]][cell[1]] != " "]
    glitches = {}                       # cell -> frames left
    loop = []                           # per frame: {cell: glitch char}
    for f in range(LOOP_FRAMES):
        if f < LOOP_FRAMES - GLITCH_LEN[1] and rng.random() < GLITCH_RATE:
            for _ in range(rng.randint(1, 2)):
                glitches[rng.choice(name_cells)] = rng.randint(*GLITCH_LEN)
        frame = {}
        for cell in list(glitches):
            frame[cell] = rng.choice(CHARSET)
            glitches[cell] -= 1
            if glitches[cell] == 0:
                del glitches[cell]
        loop.append(frame)               # ends clean, so the loop seams invisibly
    return intro, loop


def render_frame(frame, w, h, rows=None, default=None):
    """One <text> per row, split into <tspan>s by style. textLength pins the
    row width so the art stays aligned whatever monospace font the viewer has."""
    out = []
    for r in (range(h) if rows is None else rows):
        runs, cur, buf = [], None, ""
        for c in range(w):
            ch, style = frame.get((r, c), (" ", None))
            if style != cur and buf:
                runs.append((cur, buf))
                buf = ""
            cur, buf = style, buf + ch
        runs.append((cur, buf))
        # merge runs that render the same (default style and blanks)
        merged = []
        for st, t in runs:
            st = None if st in (None, default) else st
            if merged and merged[-1][0] == st:
                merged[-1] = (st, merged[-1][1] + t)
            else:
                merged.append((st, t))
        runs = merged
        if all(s is None for s, t in runs) and not "".join(t for _, t in runs).strip():
            continue
        spans = "".join(
            escape(t) if s in (None, default) else f'<tspan class="{s}">{escape(t)}</tspan>'
            for s, t in runs)
        y = (r + 1) * LINE_H - 4
        cls = f' class="r{r}"' if rows is None and frame is STATIC else ""
        out.append(f'<text{cls} y="{y}" textLength="{w * CHAR_W:.1f}">{spans}</text>')
    return "".join(out)


STATIC = {}


def render(intro, loop, target, w, h):
    W, H = w * CHAR_W, h * LINE_H
    t_intro = len(intro) * FRAME_MS / 1000
    t_loop = len(loop) * FRAME_MS / 1000
    n = len(loop)
    css = [
        f"text{{font:{FONT_PX}px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"
        "white-space:pre}",
        *[f".{k}{{fill:{COLOR[k]};fill-opacity:{OPACITY[k]}}}" for k in COLOR],
        ".i,.l,.st text{visibility:hidden}",
        f".i text{{fill:{COLOR['x']};fill-opacity:{OPACITY['x']}}}",
        f".l text,.st text{{fill:{COLOR['s']}}}",
        f".i{{animation:si {t_intro}s step-end 1}}",
        f".l{{animation:sl {t_loop}s step-end infinite}}",
        f"@keyframes si{{0%{{visibility:visible}}{100 / len(intro):.4f}%,100%{{visibility:hidden}}}}",
        f"@keyframes sl{{0%{{visibility:visible}}{100 / n:.4f}%,100%{{visibility:hidden}}}}",
    ]
    # The finished banner is drawn once, one <text> per row. A row is hidden
    # during the loop frames where it has a glitch; that frame draws the
    # glitched version of the row instead.
    STATIC.clear()
    STATIC.update({(r, c): (target[r][c], "s")
                   for r in range(h) for c in range(w) if target[r][c] != " "})
    for r in range(h):
        if not any(target[r][c] != " " for c in range(w)):
            continue
        hidden = [any(cell[0] == r for cell in fr) for fr in loop]
        steps, prev = [], None
        for f, hid in enumerate(hidden):
            if hid != prev:
                steps.append(f"{100 * f / n:.4f}%{{visibility:{'hidden' if hid else 'visible'}}}")
                prev = hid
        css.append(f"@keyframes k{r}{{{''.join(steps)}100%{{visibility:{'hidden' if prev else 'visible'}}}}}")
        css.append(f".r{r}{{animation:k{r} {t_loop}s step-end {t_intro}s infinite}}")

    scale = TARGET_WIDTH / W
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
           f'width="{TARGET_WIDTH}" height="{H * scale:.0f}" xml:space="preserve">',
           "<style>" + "".join(css) + "</style>"]
    for i, fr in enumerate(intro):
        out.append(f'<g class="i" style="animation-delay:{i * FRAME_MS / 1000:.3f}s">'
                   f'{render_frame(fr, w, h, default="x")}</g>')
    out.append(f'<g class="st">{render_frame(STATIC, w, h, default="s")}</g>')
    for i, glitch in enumerate(loop):
        if not glitch:
            continue
        rows = sorted({r for r, _ in glitch})
        fr = dict(STATIC)
        fr.update({cell: (ch, "g") for cell, ch in glitch.items()})
        delay = t_intro + i * FRAME_MS / 1000
        out.append(f'<g class="l" style="animation-delay:{delay:.3f}s">'
                   f'{render_frame(fr, w, h, rows, default="s")}</g>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="l03x.svg")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    target, w, h = build_grid()
    intro, loop = frames(rng, target, w, h)
    svg = render(intro, loop, target, w, h)
    with open(a.out, "w") as f:
        f.write(svg)
    print(f"{len(intro)} intro + {len(loop)} loop frames, {len(svg) // 1024} KiB -> {a.out}")


if __name__ == "__main__":
    main()