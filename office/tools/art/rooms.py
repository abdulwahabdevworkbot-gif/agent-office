"""Room backgrounds: office, meeting room and lounge, day and night (see STYLE.md and NOTES-rooms.md).

Rebuild all room, furniture and fx art with one command, from the repo root:

    python3 office/tools/art/build_rooms.py

The floor is the exact diamond from STYLE.md (P(u, v) for u, v in 0..1) and the two walls stand on its back edges:
the left wall (windows) on B-L at u=0 and the right wall (door, boards) on B-R at v=0. Things that hang flat on a
wall are drawn in the wall's own plane (an SVG skew), so a circle on the wall is a true ellipse in the view.
Night is the same drawing with night windows, a NIGHT_TINT multiply over it and warm glows on top.
"""
import math, random
from isokit import Svg, Frame, box, floor_poly, floor_ellipse, quad, PAL, shade, mix, f, S, RW, RH, LEFT_FACE, RIGHT_FACE, HILITE
from style import NIGHT_TINT, NIGHT_GLOW

F = Frame()                 # room frame, 1200 x 896
HW = 300                    # wall height (h units, 1508 scale)
T = 0.03                    # wall thickness (floor units)
SLAB = 22                   # floor slab thickness (h units)
LW = 2.0                    # room line width (STYLE.md)
LEN_L = F(0, 0)[0] - F(0, 1)[0]   # left wall length in screen x (552)
LEN_R = F(1, 0)[0] - F(0, 0)[0]   # right wall length in screen x (456)
SUN = (0.00165, 0.0002)     # floor shift (du, dv) per h unit of a sun ray through the left wall


def xl(v):
    """Left wall local x for floor coordinate v (0 at the front end L, LEN_L at the back corner)."""
    return (1 - v) * LEN_L


def xr(u):
    """Right wall local x for floor coordinate u (0 at the back corner, LEN_R at the right end R)."""
    return u * LEN_R


def hy(h):
    return -h * S


def rr(x0, y0, x1, y1, r=0):
    """Rounded rectangle path between two corners (local wall coordinates)."""
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    if r <= 0:
        return f"M{f(x0)} {f(y0)}H{f(x1)}V{f(y1)}H{f(x0)}Z"
    return (f"M{f(x0 + r)} {f(y0)}H{f(x1 - r)}Q{f(x1)} {f(y0)} {f(x1)} {f(y0 + r)}V{f(y1 - r)}"
            f"Q{f(x1)} {f(y1)} {f(x1 - r)} {f(y1)}H{f(x0 + r)}Q{f(x0)} {f(y1)} {f(x0)} {f(y1 - r)}"
            f"V{f(y0 + r)}Q{f(x0)} {f(y0)} {f(x0 + r)} {f(y0)}Z")


def blob(cx, cy, rs):
    """Cloud / foliage blob: union of circles as one path (r, dx, dy)."""
    return "".join(f"M{f(cx + dx - r)} {f(cy + dy)}a{f(r)} {f(r)} 0 1 0 {f(2 * r)} 0a{f(r)} {f(r)} 0 1 0 {f(-2 * r)} 0Z"
                   for r, dx, dy in rs)


# ------------------------------------------------------------------------------------------------ shell
def shell(svg, floor_col, slab_col, night):
    # soft shadow of the whole room on the backdrop
    sh = floor_poly(F, [(-T, -T), (1, -T), (1, 1), (-T, 1)], h=-SLAB - 10, n=1)
    svg.poly(sh, "#000000", stroke=False, op=.35, extra=f'filter="{svg.blur(14)}"')
    # slab edges under the front floor edges
    box(svg, F, -T, 1, -T, 1, -SLAB, 0, slab_col, faces="uv", lw=LW)
    svg.poly([F(0, 0), F(1, 0), F(1, 1), F(0, 1)], floor_col, lw=LW)


def planks(svg, base, line, n=17, seed=3):
    rnd = random.Random(seed)
    for i in range(1, n):
        v = i / n
        svg.line(F(0, v), F(1, v), line, lw=1.3)
    for i in range(n):
        v0, v1 = i / n, (i + 1) / n
        off = (0.137 * i * 7) % 1
        for u in (off, (off + .47) % 1):
            if .04 < u < .97:
                svg.line(F(u, v0 + .004), F(u, v1 - .004), line, lw=1.1, op=.8)
    # a few planks a shade lighter, for life
    for i in rnd.sample(range(n), 5):
        v0, v1 = i / n, (i + 1) / n
        a = rnd.uniform(0, .6)
        svg.poly(floor_poly(F, [(a, v0), (a + .38, v0), (a + .38, v1), (a, v1)], n=1), PAL["floor_alt"], stroke=False,
                 op=.7)


def carpet(svg):
    for i in range(1, 12):
        t = i / 12
        svg.line(F(0, t), F(1, t), PAL["carpet_line"], lw=1.1)
        svg.line(F(t, 0), F(t, 1), PAL["carpet_line"], lw=1.1)


def sun_patches(svg, panes, clip_id, col=None, op=.6):
    """Light through each window pane, projected onto the floor and fading into the room (panes: v0, v1, h0, h1)."""
    du, dv = SUN
    col = col or PAL["sun"]
    svg.group(f'clip-path="url(#{clip_id})"')
    for v0, v1, h0, h1 in panes:
        uv = [(h0 * du, v0 + h0 * dv), (h1 * du, v0 + h1 * dv), (h1 * du, v1 + h1 * dv), (h0 * du, v1 + h0 * dv)]
        vm = (v0 + v1) / 2
        a, b = F(h0 * du, vm + h0 * dv), F(h1 * du, vm + h1 * dv)
        g = svg.linear(a[0], a[1], b[0], b[1], [(0, col, op), (1, col, op * .35)])
        svg.poly(floor_poly(F, uv, n=8), g, stroke=False)
    svg.end()

def walls(svg):
    svg.poly([F(0, 0, 0), F(0, 1, 0), F(0, 1, HW), F(0, 0, HW)], PAL["wall_side"], lw=LW)
    svg.poly([F(0, 0, 0), F(1, 0, 0), F(1, 0, HW), F(0, 0, HW)], PAL["wall"], lw=LW)


def baseboards(svg, wainscot=None):
    bb = PAL["baseboard"]
    if wainscot:
        col, hh = wainscot
        svg.poly([F(0, 0, 0), F(1, 0, 0), F(1, 0, hh), F(0, 0, hh)], col, stroke=False)
        box(svg, F, 0, 1, 0, .006, hh - 3, hh + 3, PAL["frame"], lw=1.2, faces="t")
        svg.line(F(0, .006, hh - 3), F(1, .006, hh - 3), shade(PAL["frame"], .7), lw=1.2)
    svg.poly([F(0, 0, 0), F(0, 1, 0), F(0, 1, 11), F(0, 0, 11)], shade(bb, .93), lw=1.4)
    svg.poly([F(0, 0, 0), F(1, 0, 0), F(1, 0, 11), F(0, 0, 11)], bb, lw=1.4)

def caps(svg):
    c = PAL["wall_cap"]
    # cut ends of the walls (left end faces +v, right end faces +u), down to the bottom of the slab
    svg.poly([F(-T, 1, -SLAB), F(0, 1, -SLAB), F(0, 1, HW), F(-T, 1, HW)], shade(c, LEFT_FACE), lw=LW)
    svg.poly([F(1, -T, -SLAB), F(1, 0, -SLAB), F(1, 0, HW), F(1, -T, HW)], shade(c, RIGHT_FACE), lw=LW)
    svg.poly([F(-T, -T, HW), F(1, -T, HW), F(1, 0, HW), F(0, 0, HW), F(0, 1, HW), F(-T, 1, HW)], c, lw=LW)
    # the inner corner line
    svg.line(F(0, 0, 0), F(0, 0, HW), shade(PAL["wall_side"], .8), lw=1.4)


def left_g(svg, u=0.0):
    t, _ = F.plane_u(u)
    svg.group(f'transform="{t}"')


def right_g(svg, v=0.0):
    t, _ = F.plane_v(v)
    svg.group(f'transform="{t}"')


# ------------------------------------------------------------------------------------------------ windows
def city(svg, night, x0, x1, seed=7):
    """Sky, clouds and a soft skyline in left-wall coordinates (drawn inside a pane clip)."""
    rnd = random.Random(seed)
    top, bot = hy(HW), hy(0)
    if night:
        g = svg.linear(0, top, 0, hy(60), [(0, PAL["night_sky"], 1), (1, PAL["night_sky_low"], 1)])
    else:
        g = svg.linear(0, top, 0, hy(60), [(0, PAL["sky_high"], 1), (.55, PAL["sky"], 1), (1, PAL["sky_low"], 1)])
    svg.rect(x0, top, x1 - x0, bot - top, g, stroke=False)
    if night:
        for _ in range(26):
            x, y = rnd.uniform(x0, x1), rnd.uniform(hy(HW - 10), hy(170))
            svg.ellipse(x, y, .9, .9, "#ffffff", stroke=False, op=rnd.uniform(.4, .85))
        mx, my = x0 + (x1 - x0) * .78, hy(250)
        svg.ellipse(mx, my, 11, 11, "#f6f1dc", stroke=False)
        svg.ellipse(mx + 5, my - 3, 10, 10, PAL["night_sky"], stroke=False)
    else:
        for cx, cy, s in [(x0 + 40, hy(238), 1.0), (x0 + 230, hy(262), .8), (x0 + 400, hy(228), 1.15),
                          (x0 + 520, hy(258), .7), (x0 + 150, hy(205), .6)]:
            svg.path(blob(cx, cy, [(9 * s, 0, 0), (12 * s, 14 * s, -4 * s), (8 * s, 29 * s, 0), (6 * s, -9 * s, 2)]),
                     PAL["cloud"], stroke=False, op=.92)
    # skyline: far layer, then near layer
    far = PAL["night_city_far"] if night else PAL["city_far"]
    near = PAL["night_city"] if night else PAL["city"]
    lit = []
    for layer, col, hmin, hmax in [(0, far, 105, 175), (1, near, 70, 130)]:
        x = x0 - 10
        while x < x1:
            w = rnd.uniform(22, 46)
            h = rnd.uniform(hmin, hmax)
            d = rr(x, hy(h), x + w - 3, bot, 0)
            svg.path(d, col, stroke=False)
            if layer == 0 and rnd.random() < .35:      # a little roof detail
                svg.rect(x + w * .3, hy(h + 12), 3, hy(0) - hy(12), col, stroke=False)
            if layer == 1 and not night:
                for k in range(int((h - 60) / 22)):
                    svg.rect(x + 4, hy(h - 10 - k * 22), w - 11, 3.2, shade(col, 1.18), stroke=False, op=.8)
            if night:
                for k in range(int((h - 50) / 20)):
                    for j in range(int((w - 6) / 9)):
                        if rnd.random() < (.07 if layer == 0 else .1):
                            lit.append((x + 4 + j * 9, hy(h - 10 - k * 20)))
            x += w + rnd.uniform(0, 6)
    return lit


def window_bay(svg, v0, v1, h0, h1, split=2, transom=None):
    """Frame of one window bay on the left wall: outer frame, mullions and an optional transom (local coords)."""
    X0, X1 = xl(v1), xl(v0)
    fw = 5.0
    panes = []
    ys = [(h0, transom - 5), (transom + 5, h1)] if transom else [(h0, h1)]
    for (a, b) in ys:
        for k in range(split):
            px0 = X0 + (X1 - X0) * k / split + (fw if k == 0 else fw / 2)
            px1 = X0 + (X1 - X0) * (k + 1) / split - (fw if k == split - 1 else fw / 2)
            panes.append((px0, hy(b) + (fw if b == h1 else 0), px1, hy(a) - (fw if a == h0 else 0)))
    d = rr(X0, hy(h1), X1, hy(h0), 1.5) + "".join(rr(*p, 0) for p in panes)
    return d, panes


def windows_left(svg, night, bays, h0=36, h1=272, transom=232, sill=True):
    """bays: [(v0, v1, split)]; draws view, frames, glass glints and sills. Returns floor sun panes and lit windows."""
    frames, all_panes = [], []
    for v0, v1, split in bays:
        d, panes = window_bay(svg, v0, v1, h0, h1, split, transom)
        frames.append(d)
        all_panes += panes
    cid = svg.clip("".join(f'<path d="{rr(*p)}"/>' for p in all_panes))
    left_g(svg)
    svg.group(f'clip-path="url(#{cid})"')
    lit = city(svg, night, 0, LEN_L)
    # glass glints
    for p in all_panes:
        x0, y0, x1, y1 = p
        w = x1 - x0
        if w > 20 and (y1 - y0) > 60:
            for a, b in [(.18, .32), (.42, .5)]:
                svg.poly([(x0 + w * a, y1), (x0 + w * b, y1), (x0 + w * b + 40, y0), (x0 + w * a + 40, y0)],
                         "#ffffff", stroke=False, op=.10 if night else .2)
    svg.end()
    for d in frames:
        svg.path(d, PAL["frame"], lw=1.6, extra='fill-rule="evenodd"')
    svg.end()
    if sill:
        for v0, v1, _ in bays:
            box(svg, F, 0, .014, v0 - .004, v1 + .004, h0 - 7, h0, PAL["frame"], lw=1.3)
    # floor light: pane extents back in floor units
    sun = []
    for v0, v1, split in bays:
        for k in range(split):
            a = v0 + (v1 - v0) * k / split + .006
            b = v0 + (v1 - v0) * (k + 1) / split - .006
            sun.append((a, b, h0, transom - 5 if transom else h1))
    return sun, lit, cid


def curtains(svg, bays, col, h0=24, h1=286):
    """Soft curtains gathered at both sides of each window bay, on a thin rod (left wall, meeting room)."""
    t, _ = F.plane_u(.016)
    svg.group(f'transform="{t}"')
    for v0, v1, _ in bays:
        X0, X1 = xl(v1) - 10, xl(v0) + 10
        svg.line((X0 - 6, hy(h1)), (X1 + 6, hy(h1)), PAL["wood_dark"], lw=2.4)
        for xa, sgn in ((X0, 1), (X1, -1)):
            w = 22
            xb = xa + sgn * w
            top, bot = hy(h1 - 3), hy(h0)
            d = (f"M{f(xa)} {f(top)}L{f(xb)} {f(top)}Q{f(xb - sgn * 6)} {f((top + bot) / 2)} {f(xb + sgn * 3)} {f(bot)}"
                 f"L{f(xa)} {f(bot)}Z")
            svg.path(d, col, lw=1.3)
            for k in (.33, .66):
                xk = xa + sgn * w * k
                svg.line((xk, top + 4), (xk + sgn * 1.5, bot - 3), shade(col, .84), lw=1.3)
    svg.end()


def lit_windows(svg, lit, cid):
    if not lit:
        return
    left_g(svg)
    svg.group(f'clip-path="url(#{cid})"')
    for x, y in lit:
        svg.rect(x, y, 4.2, 3.4, PAL["lit_window"], stroke=False, op=.9)
    svg.end()
    svg.end()


# ------------------------------------------------------------------------------------------------ wall items
def door_right(svg, u0, u1, h=190, leaf=None):
    """Door on the right wall: protruding frame, painted leaf with a round window and a handle."""
    leaf = leaf or PAL["sage"]
    fr = PAL["frame"]
    d = .010
    # leaf (in the wall plane)
    right_g(svg)
    X0, X1 = xr(u0), xr(u1)
    svg.path(rr(X0, hy(h), X1, hy(0), 0), leaf, lw=1.6)
    svg.path(rr(X0 + 6, hy(h - 12), X1 - 6, hy(h * .58), 2), shade(leaf, 1.08), lw=1.2)
    svg.path(rr(X0 + 6, hy(h * .5), X1 - 6, hy(14), 2), shade(leaf, 1.08), lw=1.2)
    svg.ellipse(X1 - 9, hy(h * .47), 2.6, 2.6, PAL["mustard"], lw=1.2)
    svg.end()
    # frame: two jambs and a head, protruding a little
    box(svg, F, u0 - .012, u0, 0, d, 0, h + 9, fr, lw=1.4)
    box(svg, F, u1, u1 + .012, 0, d, 0, h + 9, fr, lw=1.4)
    box(svg, F, u0 - .012, u1 + .012, 0, d, h, h + 9, fr, lw=1.4)


def door_left(svg, v0, v1, h=190, leaf=None):
    """Door on the left wall (for the meeting room and lounge; the page's DOOR spot is in front of it)."""
    leaf = leaf or PAL["sage"]
    fr = PAL["frame"]
    d = .010
    left_g(svg)
    X0, X1 = xl(v1), xl(v0)
    svg.path(rr(X0, hy(h), X1, hy(0), 0), shade(leaf, .93), lw=1.6)
    svg.path(rr(X0 + 7, hy(h - 12), X1 - 7, hy(h * .58), 2), shade(leaf, 1.02), lw=1.2)
    svg.path(rr(X0 + 7, hy(h * .5), X1 - 7, hy(14), 2), shade(leaf, 1.02), lw=1.2)
    svg.ellipse(X1 - 10, hy(h * .47), 2.6, 2.6, PAL["mustard"], lw=1.2)
    svg.end()
    box(svg, F, 0, d, v1, v1 + .012, 0, h + 9, fr, lw=1.4)
    box(svg, F, 0, d, v0 - .012, v0, 0, h + 9, fr, lw=1.4)
    box(svg, F, 0, d, v0 - .012, v1 + .012, h, h + 9, fr, lw=1.4)


def task_board(svg, u0, u1, h0, h1, seed=5):
    """A kanban board: frame, three columns with colored header tabs and sticky notes (no text)."""
    d = .008
    box(svg, F, u0, u1, 0, d, h0, h1, PAL["wood"], lw=1.4, faces="tu")
    t, _ = F.plane_v(d)
    svg.group(f'transform="{t}"')
    X0, X1 = xr(u0), xr(u1)
    svg.path(rr(X0, hy(h1), X1, hy(h0), 2), PAL["wood"], lw=1.6)
    svg.path(rr(X0 + 4, hy(h1 - 5), X1 - 4, hy(h0 + 5), 1), PAL["paper"], lw=1.2)
    rnd = random.Random(seed)
    cols = [PAL["sky_accent"], PAL["mustard"], PAL["sage"]]
    notes = [PAL["mustard"], PAL["rose"], PAL["sky_accent"], PAL["sage"], PAL["lavender"]]
    cw = (X1 - X0 - 8) / 3
    for c in range(3):
        cx0 = X0 + 4 + c * cw
        if c:
            svg.line((cx0, hy(h1 - 8)), (cx0, hy(h0 + 8)), shade(PAL["paper"], .82), lw=1.2)
        svg.path(rr(cx0 + 5, hy(h1 - 9), cx0 + cw - 5, hy(h1 - 18), 2), cols[c], lw=1.1)
        n = [4, 3, 2][c]
        for k in range(n):
            r, q = divmod(k, 2)
            nx = cx0 + 6 + q * (cw - 12) / 2 + rnd.uniform(-1, 1)
            ny = hy(h1 - 24 - r * 25) + rnd.uniform(-1, 1)
            col = notes[rnd.randrange(len(notes))]
            svg.path(rr(nx, ny, nx + (cw - 12) / 2 - 3, ny + 15, 1), col, lw=1.1)
            svg.line((nx + 3, ny + 5), (nx + (cw - 12) / 2 - 7, ny + 5), shade(col, .7), lw=1, op=.6)
    # marker tray
    svg.end()
    box(svg, F, u0 + .03, u1 - .03, 0, .02, h0 - 4, h0, PAL["frame"], lw=1.2)


def clock(svg, u, h, r=12):
    right_g(svg)
    x, y = xr(u), hy(h)
    svg.ellipse(x, y, r, r, PAL["frame"], lw=1.6)
    svg.ellipse(x, y, r - 3, r - 3, PAL["paper"], stroke=False)
    svg.line((x, y), (x, y - r * .6), PAL["dark"], lw=1.4)
    svg.line((x, y), (x + r * .45, y + 1), PAL["dark"], lw=1.4)
    svg.end()


def coat_hooks(svg, u0, u1, h):
    """A peg rail by the door with a tote bag and a scarf."""
    box(svg, F, u0, u1, 0, .006, h - 5, h + 5, PAL["wood"], lw=1.2)
    for k in range(3):
        x, y = F(u0 + (u1 - u0) * (k + .5) / 3, .012, h)
        svg.ellipse(x, y, 2.4, 2.4, PAL["wood_dark"], lw=1)
    right_g(svg, .012)
    x0 = xr(u0 + (u1 - u0) * .5 / 3)
    y = hy(h)
    c = PAL["mustard"]
    svg.path(f"M{f(x0 - 4)} {f(y + 2)}L{f(x0 - 9)} {f(y + 14)}M{f(x0 + 4)} {f(y + 2)}L{f(x0 + 9)} {f(y + 14)}", "none",
             stroke=shade(c, .7), lw=1.4)
    svg.path(rr(x0 - 12, y + 13, x0 + 12, y + 38, 3), c, lw=1.3)
    svg.path(rr(x0 - 6, y + 20, x0 + 6, y + 27, 1.5), shade(c, 1.2), stroke=False)
    x2 = xr(u0 + (u1 - u0) * 2.5 / 3)
    s2 = PAL["rose"]
    for dx, ln in ((-3.2, 30), (2.6, 24)):        # a striped scarf over the peg, two ends hanging
        svg.path(rr(x2 + dx - 2.8, y - 1, x2 + dx + 2.8, y + ln, 1), s2, lw=1.1)
        for k in (.45, .7):
            svg.line((x2 + dx - 2.2, y + ln * k), (x2 + dx + 2.2, y + ln * k), PAL["paper"], lw=1.3)
    svg.end()


def sill_plant(svg, v, kind, h=36):
    """A small pot on a window sill (left wall)."""
    x, y = F(.008, v, h)
    if kind == 0:
        svg.path(f"M{f(x - 5)} {f(y - 8)}L{f(x + 5)} {f(y - 8)}L{f(x + 4)} {f(y)}L{f(x - 4)} {f(y)}Z", PAL["pot"], lw=1.1)
        for k in range(5):
            a = math.pi + (k + .5) * math.pi / 5
            svg.ellipse(x + math.cos(a) * 4, y - 10 + math.sin(a) * 4, 3.4, 1.8, PAL["sage"], lw=.9,
                        extra=f'transform="rotate({f(math.degrees(a))} {f(x + math.cos(a) * 4)} {f(y - 10 + math.sin(a) * 4)})"')
    else:
        svg.path(f"M{f(x - 4.5)} {f(y - 9)}L{f(x + 4.5)} {f(y - 9)}L{f(x + 3.5)} {f(y)}L{f(x - 3.5)} {f(y)}Z",
                 PAL["frame"], lw=1.1)
        svg.path(rr(x - 2.6, y - 22, x + 2.6, y - 8, 2.6), PAL["leaf"], lw=1)
        svg.path(rr(x + 1.5, y - 18, x + 6, y - 12, 2.2), PAL["leaf"], lw=.9)

def sconce(svg, u=None, v=None, h=200, night=False):
    """A small wall lamp: back plate, short arm and a dome shade; returns its glow center in pixels."""
    if v is None:
        right_g(svg)
        x = xr(u)
    else:
        left_g(svg)
        x = xl(v)
    svg.path(rr(x - 3, hy(h) - 9, x + 3, hy(h) + 5, 1.5), PAL["frame"], lw=1.1)
    svg.end()
    p0 = F(u, .002, h) if v is None else F(.002, v, h)
    cx, cy = F(u, .022, h + 4) if v is None else F(.022, v, h + 4)
    svg.line(p0, (cx, cy - 2), shade(PAL["dark"], 1.3), lw=1.6)
    c = PAL["mustard"]
    svg.path(f"M{f(cx - 10)} {f(cy + 4)}C{f(cx - 10)} {f(cy - 10)} {f(cx + 10)} {f(cy - 10)} {f(cx + 10)} {f(cy + 4)}Z",
             c, lw=1.3)
    svg.path(f"M{f(cx + 3)} {f(cy + 4)}C{f(cx + 5)} {f(cy - 3)} {f(cx + 5)} {f(cy - 6)} {f(cx + 4)} {f(cy - 6.4)}"
             f"C{f(cx + 8)} {f(cy - 4)} {f(cx + 10)} {f(cy)} {f(cx + 10)} {f(cy + 4)}Z", shade(c, RIGHT_FACE),
             stroke=False)
    svg.ellipse(cx, cy + 4, 10, 2.6, PAL["paper"], lw=1.1)
    return (cx, cy + 8)

def leaf_cluster(svg, cx, cy, n, r, seed, cols=None, spread=1.0):
    rnd = random.Random(seed)
    cols = cols or [PAL["leaf"], PAL["leaf_dark"]]
    for i in range(n):
        a = rnd.uniform(-math.pi, 0) if i < n * .7 else rnd.uniform(-math.pi * 1.1, .1)
        d = rnd.uniform(.2, 1) * r * spread
        x, y = cx + math.cos(a) * d * 1.3, cy + math.sin(a) * d
        rot = math.degrees(a) + rnd.uniform(-30, 30)
        c = cols[i % len(cols)]
        svg.ellipse(x, y, r * .55, r * .3, c, lw=1.1, extra=f'transform="rotate({f(rot)} {f(x)} {f(y)})"')


def plant_shelf(svg, u0, u1, h, items, seed=1):
    """Floating shelf on the right wall with small things on it. items: [(kind, u)]"""
    dv = .034
    box(svg, F, u0, u1, 0, dv, h - 6, h, PAL["wood"], lw=1.3)
    rnd = random.Random(seed)
    for kind, u in items:
        base = F(u, dv * .5, h)
        x, y = base
        if kind == "pothos":
            pot = PAL["paper"]
            svg.path(f"M{f(x - 8)} {f(y - 14)}L{f(x + 8)} {f(y - 14)}L{f(x + 6)} {f(y)}L{f(x - 6)} {f(y)}Z", pot,
                     lw=1.2)
            # trailing vines down over the shelf edge
            for k, (dx, ln) in enumerate([(-7, 34), (2, 48), (8, 26)]):
                pts_ = [(x + dx + math.sin(t * .35 + k) * 2.5, y - 10 + t * 1.0) for t in range(0, ln + 1, 2)]
                svg.pline(pts_, PAL["leaf_dark"], lw=1.2)
                for t in range(4, ln, 7):
                    lx, ly = x + dx + math.sin(t * .35 + k) * 2.5, y - 10 + t
                    svg.ellipse(lx + (3 if t % 2 else -3), ly, 3.6, 2.4, PAL["leaf"], lw=1)
            leaf_cluster(svg, x, y - 15, 9, 7, seed + 3)
        elif kind == "cactus":
            svg.path(f"M{f(x - 6)} {f(y - 10)}L{f(x + 6)} {f(y - 10)}L{f(x + 5)} {f(y)}L{f(x - 5)} {f(y)}Z", PAL["pot"],
                     lw=1.2)
            svg.path(rr(x - 4, y - 28, x + 4, y - 9, 4), PAL["sage"], lw=1.2)
            svg.path(rr(x + 3, y - 23, x + 9, y - 15, 3), PAL["sage"], lw=1.1)
        elif kind == "books":
            for j, (c, hh) in enumerate([(PAL["sky_accent"], 22), (PAL["coral"], 19), (PAL["mustard"], 24),
                                         (PAL["lavender"], 20)]):
                bx = x - 9 + j * 5
                svg.path(rr(bx, y - hh, bx + 4.6, y, .8), c, lw=1.1)
        elif kind == "vase":
            svg.ellipse(x, y - 9, 7, 9, PAL["teal"], lw=1.2)
            svg.path(rr(x - 3, y - 22, x + 3, y - 15, 1), PAL["teal"], lw=1.1)
            for k in range(3):
                a = -math.pi / 2 + (k - 1) * .5
                svg.line((x, y - 20), (x + math.cos(a) * 14, y - 20 + math.sin(a) * 14), PAL["leaf_dark"], lw=1.1)
                svg.ellipse(x + math.cos(a) * 15, y - 20 + math.sin(a) * 15, 2.6, 2.6, PAL["coral"], lw=1)
        elif kind == "succulent":
            svg.path(f"M{f(x - 7)} {f(y - 9)}L{f(x + 7)} {f(y - 9)}L{f(x + 5)} {f(y)}L{f(x - 5)} {f(y)}Z",
                     PAL["frame"], lw=1.2)
            for k in range(5):
                a = math.pi + k * math.pi / 4
                svg.ellipse(x + math.cos(a) * 5, y - 11 + math.sin(a) * 3, 4, 2.4, PAL["sage"], lw=1,
                            extra=f'transform="rotate({f(math.degrees(a))} {f(x + math.cos(a) * 5)} '
                                  f'{f(y - 11 + math.sin(a) * 3)})"')


def frame_art(svg, u0, u1, h0, h1, kind="hills"):
    """A framed picture on the right wall (abstract and calm)."""
    right_g(svg)
    X0, X1 = xr(u0), xr(u1)
    svg.path(rr(X0, hy(h1), X1, hy(h0), 1.5), PAL["wood"], lw=1.4)
    svg.path(rr(X0 + 4, hy(h1 - 5), X1 - 4, hy(h0 + 5), 0), PAL["paper"], lw=1)
    cid = svg.clip(f'<path d="{rr(X0 + 4, hy(h1 - 5), X1 - 4, hy(h0 + 5), 0)}"/>')
    svg.group(f'clip-path="url(#{cid})"')
    w, top, bot = X1 - X0, hy(h1 - 5), hy(h0 + 5)
    if kind == "hills":
        svg.ellipse(X0 + w * .7, top + (bot - top) * .35, 6, 6, PAL["mustard"], stroke=False)
        svg.ellipse(X0 + w * .3, bot + 10, w * .5, (bot - top) * .5, PAL["sage"], stroke=False)
        svg.ellipse(X0 + w * .8, bot + 14, w * .45, (bot - top) * .45, PAL["teal"], stroke=False, op=.8)
    else:
        svg.ellipse(X0 + w * .38, top + (bot - top) * .55, w * .22, w * .22, PAL["coral"], stroke=False, op=.85)
        svg.ellipse(X0 + w * .62, top + (bot - top) * .45, w * .2, w * .2, PAL["lavender"], stroke=False, op=.85)
    svg.end()
    svg.end()


def glow(svg, c, rx, ry, op=.55, color=NIGHT_GLOW):
    svg.ellipse(c[0], c[1], rx, ry, svg.radial(color, op, 0), stroke=False)


def floor_glow(svg, u, v, ru, rv, op=.35, color=NIGHT_GLOW):
    pts_ = floor_ellipse(F, u, v, ru, rv, n=32)
    cx = sum(p[0] for p in pts_) / len(pts_)
    cy = sum(p[1] for p in pts_) / len(pts_)
    rx = (max(p[0] for p in pts_) - min(p[0] for p in pts_)) / 2
    ry = (max(p[1] for p in pts_) - min(p[1] for p in pts_)) / 2
    svg.ellipse(cx, cy, rx, ry, svg.radial(color, op, 0), stroke=False)


def night_overlay(svg, op=.35):
    svg.rect(0, 0, RW, RH, NIGHT_TINT, stroke=False, op=op, extra='style="mix-blend-mode:multiply"')


def floor_clip(svg):
    return svg.clip(f'<polygon points="{" ".join(f"{f(x)},{f(y)}" for x, y in [F(0, 0), F(1, 0), F(1, 1), F(0, 1)])}"/>')


# ------------------------------------------------------------------------------------------------ rooms
def tint_filter(svg, op=.38):
    """NIGHT_TINT as a multiply at op, done as a color matrix so it can wrap groups (lit windows stay out)."""
    i = svg.uid("t")
    c = [int(NIGHT_TINT[k:k + 2], 16) / 255 for k in (1, 3, 5)]
    r, g, b = (1 - op * (1 - x) for x in c)
    svg.defs.append(f'<filter id="{i}" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" '
                    f'values="{r:.3f} 0 0 0 0 0 {g:.3f} 0 0 0 0 0 {b:.3f} 0 0 0 0 0 1 0"/></filter>')
    return f"url(#{i})"


class Night:
    """Wraps drawing in the night tint; lit city windows and glows go between and after the tinted groups."""

    def __init__(self, svg, night):
        self.svg, self.night = svg, night
        self.flt = tint_filter(svg) if night else None
        self.open()

    def open(self):
        if self.night:
            self.svg.group(f'filter="{self.flt}"')

    def close(self):
        if self.night:
            self.svg.end()


def office(night):
    svg = Svg(RW, RH, lw=LW, bg=PAL["backdrop"])
    nt = Night(svg, night)
    shell(svg, PAL["floor"], mix(PAL["floor"], PAL["wood_dark"], .45), night)
    planks(svg, PAL["floor"], PAL["floor_line"])
    fc = floor_clip(svg)
    walls(svg)
    bays = [(.035, .305, 2), (.345, .615, 2), (.655, .925, 2)]
    sun, lit, wc = windows_left(svg, night, bays)
    if not night:
        sun_patches(svg, sun, fc)
    baseboards(svg, (mix(PAL["wall"], PAL["sage"], .2), 92))
    for v, k in [(.12, 0), (.5, 1), (.56, 0), (.84, 1)]:
        sill_plant(svg, v, k)
    task_board(svg, .07, .31, 128, 232)
    door_right(svg, .40, .51)
    coat_hooks(svg, .545, .615, 150)
    clock(svg, .595, 240)
    plant_shelf(svg, .64, .90, 178, [("pothos", .68), ("books", .77), ("succulent", .85)])
    plant_shelf(svg, .67, .87, 232, [("vase", .72), ("cactus", .82)], seed=2)
    s1 = sconce(svg, u=.355, h=190)
    s2 = sconce(svg, u=.955, h=190)
    caps(svg)
    nt.close()
    if night:
        lit_windows(svg, lit, wc)
        for c, u in [(s1, .355), (s2, .955)]:
            glow(svg, c, 70, 60, .5)
            floor_glow(svg, u, .09, .12, .10, .28)
        glow(svg, F(.455, .02, 6), 34, 8, .45)
    return svg

def meeting(night):
    svg = Svg(RW, RH, lw=LW, bg=PAL["backdrop"])
    nt = Night(svg, night)
    shell(svg, PAL["carpet"], mix(PAL["carpet"], PAL["navy"], .35), night)
    carpet(svg)
    fc = floor_clip(svg)
    walls(svg)
    bays = [(.04, .33, 2), (.37, .66, 2)]
    sun, lit, wc = windows_left(svg, night, bays)
    if not night:
        sun_patches(svg, sun, fc, col="#ffffff", op=.38)
    curtains(svg, bays, mix(PAL["lavender"], PAL["paper"], .55))
    door_left(svg, .80, .91)
    baseboards(svg)
    acoustic(svg)
    screen = wall_screen(svg, .30, .66, 100, 214, night)
    s1 = sconce(svg, u=.13, h=150)
    s2 = sconce(svg, u=.82, h=150)
    plant_shelf(svg, .80, .95, 112, [("succulent", .84), ("books", .91)], seed=4)
    caps(svg)
    nt.close()
    if night:
        lit_windows(svg, lit, wc)
        glow(svg, screen, 150, 90, .32, PAL["screen_glow"])
        for c, u in [(s1, .13), (s2, .82)]:
            glow(svg, c, 60, 52, .45)
            floor_glow(svg, u, .08, .1, .09, .22)
    return svg

def acoustic(svg, u0=.22, u1=.74, h1=262):
    """Acoustic slat wall behind the screen: a felt backing with light oak slats, plus round felt dots."""
    box(svg, F, u0, u1, 0, .008, 11, h1, PAL["navy"], lw=1.4, faces="tu")
    t, _ = F.plane_v(.008)
    svg.group(f'transform="{t}"')
    X0, X1 = xr(u0), xr(u1)
    felt = mix(PAL["navy"], PAL["sage"], .45)
    svg.path(rr(X0, hy(h1), X1, hy(11), 0), felt, lw=1.6)
    slat = mix(PAL["wood"], PAL["paper"], .35)
    n = int((X1 - X0) / 7.4)
    for k in range(n):
        x = X0 + 3 + k * (X1 - X0 - 6) / n
        svg.rect(x, hy(h1 - 3), 4.2, hy(14) - hy(h1 - 3), slat, stroke=False)
        svg.rect(x + 3, hy(h1 - 3), 1.2, hy(14) - hy(h1 - 3), shade(slat, RIGHT_FACE), stroke=False)
    svg.end()
    right_g(svg)
    for (u, h, r, c) in [(.10, 210, 15, PAL["sage"]), (.155, 178, 10, PAL["lavender"]), (.84, 214, 13, PAL["sky_accent"]),
                         (.89, 186, 9, PAL["sage"])]:
        x = xr(u)
        svg.ellipse(x, hy(h), r, r, mix(c, PAL["paper"], .25), lw=1.3)
        svg.ellipse(x - r * .25, hy(h) - r * .25, r * .45, r * .45, mix(c, PAL["paper"], .5), stroke=False)
    svg.end()

def wall_screen(svg, u0, u1, h0, h1, night):
    """Large wall screen with a calm slide: soft bars and a line chart, no text."""
    d = .01
    box(svg, F, u0, u1, .008, .008 + d, h0, h1, PAL["dark"], lw=1.4, faces="tu")
    t, _ = F.plane_v(.008 + d)
    svg.group(f'transform="{t}"')
    X0, X1 = xr(u0), xr(u1)
    svg.path(rr(X0, hy(h1), X1, hy(h0), 3), PAL["dark"], lw=1.6)
    scr = PAL["screen"]
    svg.path(rr(X0 + 5, hy(h1 - 5), X1 - 5, hy(h0 + 5), 1.5), scr, stroke=False)
    w = X1 - X0 - 10
    top, bot = hy(h1 - 5), hy(h0 + 5)
    hh = bot - top
    svg.path(rr(X0 + 14, top + 10, X0 + 14 + w * .35, top + 15, 2), shade(scr, 1.6), stroke=False)
    for i, (c, k) in enumerate([(PAL["sage"], .45), (PAL["sky_accent"], .65), (PAL["mustard"], .55),
                                (PAL["rose"], .8), (PAL["lavender"], .6)]):
        bx = X0 + 16 + i * w * .1
        svg.path(rr(bx, bot - 10 - hh * .55 * k, bx + w * .065, bot - 10, 1.5), c, stroke=False)
    pts_ = [(X0 + 16 + w * .56 + i * w * .07, bot - 18 - hh * .45 * v) for i, v in
            enumerate([.2, .35, .3, .55, .5, .75])]
    svg.pline(pts_, PAL["screen_glow"], lw=2)
    for p in pts_:
        svg.ellipse(p[0], p[1], 2.2, 2.2, PAL["screen_glow"], stroke=False)
    svg.end()
    return F((u0 + u1) / 2, .03, (h0 + h1) / 2)


def lounge(night):
    svg = Svg(RW, RH, lw=LW, bg=PAL["backdrop"])
    nt = Night(svg, night)
    shell(svg, PAL["floor"], mix(PAL["floor"], PAL["wood_dark"], .45), night)
    planks(svg, PAL["floor"], PAL["floor_line"], seed=8)
    fc = floor_clip(svg)
    walls(svg)
    bays = [(.035, .265, 2), (.625, .76, 1)]
    sun, lit, wc = windows_left(svg, night, bays)
    if not night:
        sun_patches(svg, sun, fc)
    door_left(svg, .80, .91, leaf=PAL["coral"])
    baseboards(svg)
    neon = wall_sign(svg, night)
    frame_art(svg, .08, .2, 150, 222)
    frame_art(svg, .23, .31, 168, 222, kind="dots")
    game_shelf(svg)
    tvc = tv_corner(svg, night)
    caps(svg)
    nt.close()
    lit_windows(svg, lit, wc)
    nt.open()
    # baked furniture, back to front
    rug(svg)
    floor_lamp(svg, .70, .035)
    arcade(svg, .30, PAL["coral"], PAL["mustard"], night)
    arcade(svg, .47, PAL["teal"], PAL["lavender"], night)
    pingpong(svg)
    beanbag(svg, .72, .38, PAL["mustard"])
    beanbag(svg, .88, .42, PAL["sage"])
    beanbag(svg, .76, .54, PAL["rose"])
    foosball(svg)
    big_plant(svg, .05, .66)
    nt.close()
    if night:
        glow(svg, neon, 90, 70, .45, PAL["rose"])
        glow(svg, tvc, 120, 80, .35, PAL["screen_glow"])
        for v in (.30, .47):
            glow(svg, F(.115, v + .05, 108), 40, 36, .45, PAL["screen_glow"])
        glow(svg, F(.70, .035, 165), 60, 54, .55)
        floor_glow(svg, .70, .08, .1, .08, .3)
    return svg

def wall_sign(svg, night):
    """A soft neon-style sign on the solid wall behind the arcades: a little game controller, no text."""
    left_g(svg)
    cx, cy = (xl(.30) + xl(.57)) / 2, hy(212)
    svg.path(rr(cx - 62, cy - 40, cx + 62, cy + 40, 10), mix(PAL["navy"], PAL["wall_side"], .25), lw=1.6)
    c = PAL["rose"]
    body = (f"M{f(cx - 34)} {f(cy - 12)}Q{f(cx)} {f(cy - 20)} {f(cx + 34)} {f(cy - 12)}"
            f"Q{f(cx + 50)} {f(cy + 18)} {f(cx + 34)} {f(cy + 22)}Q{f(cx + 22)} {f(cy + 24)} {f(cx + 14)} {f(cy + 8)}"
            f"H{f(cx - 14)}Q{f(cx - 22)} {f(cy + 24)} {f(cx - 34)} {f(cy + 22)}Q{f(cx - 50)} {f(cy + 18)} "
            f"{f(cx - 34)} {f(cy - 12)}Z")
    svg.path(body, "none", stroke=shade(c, 1.35) if night else c, lw=3.2)
    svg.line((cx - 26, cy), (cx - 14, cy), PAL["screen_glow"], lw=3)
    svg.line((cx - 20, cy - 6), (cx - 20, cy + 6), PAL["screen_glow"], lw=3)
    svg.ellipse(cx + 18, cy - 3, 3, 3, PAL["mustard"], stroke=False)
    svg.ellipse(cx + 26, cy + 4, 3, 3, PAL["sage"], stroke=False)
    svg.end()
    return F(.01, .435, 212)


def game_shelf(svg):
    """Shelf of board games on the right wall."""
    for h in (128, 186):
        box(svg, F, .36, .62, 0, .04, h - 6, h, PAL["wood"], lw=1.3)
    right_g(svg, .02)
    rnd = random.Random(4)
    cols = [PAL["coral"], PAL["sky_accent"], PAL["mustard"], PAL["sage"], PAL["lavender"], PAL["rose"]]
    for h in (128, 186):
        x = xr(.375)
        while x < xr(.60):
            if rnd.random() < .5:   # stacked flat boxes
                y = hy(h)
                for k in range(rnd.randint(2, 3)):
                    hh = rnd.uniform(6, 9)
                    w = rnd.uniform(26, 34)
                    svg.path(rr(x, y - hh, x + w, y, 1), cols[rnd.randrange(6)], lw=1.1)
                    y -= hh
                x += 36
            else:
                for k in range(rnd.randint(2, 4)):
                    hh = rnd.uniform(26, 38)
                    svg.path(rr(x, hy(h) - hh, x + 6.5, hy(h), 1), cols[rnd.randrange(6)], lw=1.1)
                    x += 7
                x += 6
    svg.end()


def tv_corner(svg, night):
    """Low media console against the right wall and a TV on the wall above, facing the bean bags."""
    box(svg, F, .74, .96, 0, .06, 0, 48, PAL["wood"], lw=1.6)
    right_g(svg, .06)
    for k in range(3):
        x0 = xr(.74 + .22 * k / 3) + 4
        x1 = xr(.74 + .22 * (k + 1) / 3) - 4
        svg.path(rr(x0, hy(42), x1, hy(8), 2), shade(PAL["wood"], .64), lw=1.1)
        svg.ellipse((x0 + x1) / 2, hy(25), 1.6, 1.6, PAL["frame"], stroke=False)
    svg.end()
    # a console box and a little plant on top
    box(svg, F, .76, .80, .01, .045, 48, 56, PAL["paper"], lw=1.2)
    x, y = F(.925, .03, 48)
    svg.path(f"M{f(x - 7)} {f(y - 12)}L{f(x + 7)} {f(y - 12)}L{f(x + 5)} {f(y)}L{f(x - 5)} {f(y)}Z", PAL["pot"], lw=1.2)
    leaf_cluster(svg, x, y - 14, 8, 8, 21)
    # TV
    u0, u1, h0, h1 = .745, .925, 84, 170
    box(svg, F, u0, u1, 0, .012, h0, h1, PAL["dark"], lw=1.4, faces="tu")
    t, _ = F.plane_v(.012)
    svg.group(f'transform="{t}"')
    X0, X1 = xr(u0), xr(u1)
    svg.path(rr(X0, hy(h1), X1, hy(h0), 2.5), PAL["dark"], lw=1.6)
    top, bot = hy(h1 - 4), hy(h0 + 4)
    g = svg.linear(0, top, 0, bot, [(0, PAL["sky_accent"], 1), (1, PAL["lavender"], 1)])
    svg.path(rr(X0 + 4, top, X1 - 4, bot, 1), g, stroke=False)
    w = X1 - X0 - 8
    svg.ellipse(X0 + 4 + w * .3, bot - 4, w * .3, 16, PAL["sage"], stroke=False)
    svg.ellipse(X0 + 4 + w * .75, bot, w * .35, 22, PAL["teal"], stroke=False, op=.85)
    svg.ellipse(X0 + 4 + w * .72, top + 14, 7, 7, PAL["mustard"], stroke=False)
    svg.end()
    return F((u0 + u1) / 2, .05, (h0 + h1) / 2)


def rug(svg):
    pts_ = rounded_floor_rect(.62, .97, .30, .62, .04)
    svg.poly(pts_, shade(PAL["rug"], .9), lw=1.6)
    svg.poly(rounded_floor_rect(.64, .95, .32, .60, .03), PAL["rug"], stroke=False)
    svg.poly(rounded_floor_rect(.665, .925, .345, .575, .02), "none", stroke=shade(PAL["rug"], .82), lw=1.3)


def rounded_floor_rect(u0, u1, v0, v1, r, n=6):
    out = []
    for cu, cv, a0 in [(u1 - r, v0 + r, -90), (u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180)]:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            out.append(F(cu + r * math.cos(a), cv + r * math.sin(a)))
    return out


def shadow(svg, uv, op=.13):
    svg.poly(floor_poly(F, uv, n=4), "#5a4630", stroke=False, op=op)


def legs(svg, u0, u1, v0, v1, h, col, t=.008, inset=.012):
    for (u, v) in [(u1 - inset, v0 + inset), (u0 + inset, v1 - inset), (u1 - inset, v1 - inset)]:
        box(svg, F, u - t, u, v - t, v, 0, h, col, lw=1.2)


def arcade(svg, v0, body, accent, night):
    """Arcade cabinet against the window wall, facing into the room (+u). Footprint as the old game room."""
    v1 = v0 + .10
    shadow(svg, [(.03, v0), (.17, v0), (.17, v1 + .01), (.03, v1 + .01)])
    # cabinet body
    box(svg, F, .03, .11, v0, v1, 0, 150, body, lw=1.6)
    # screen bay on the front face (u = .11)
    t, _ = F.plane_u(.11, v1, v0)
    svg.group(f'transform="{t}"')
    W_ = xl(0) * 0 + (F(.11, v0)[0] - F(.11, v1)[0])
    svg.path(rr(4, hy(130), W_ - 4, hy(86), 3), PAL["dark"], lw=1.4)
    scr = shade(PAL["screen_glow"], .92) if night else PAL["screen_glow"]
    svg.path(rr(8, hy(125), W_ - 8, hy(92), 2), scr, stroke=False)
    svg.path(rr(12, hy(110), W_ * .45, hy(104), 1), PAL["paper"], stroke=False, op=.8)
    svg.ellipse(W_ * .7, hy(100), 3, 3, accent, stroke=False)
    # marquee
    svg.path(rr(3, hy(149), W_ - 3, hy(137), 2), accent, lw=1.3)
    svg.path(rr(10, hy(145), W_ - 10, hy(141), 1), shade(accent, 1.25), stroke=False)
    svg.end()
    # control panel
    box(svg, F, .11, .15, v0 + .01, v1 - .01, 0, 70, shade(body, .95), top=PAL["dark"], lw=1.4)
    for k, c in [(.03, PAL["mustard"]), (.05, PAL["coral"]), (.07, PAL["sky_accent"])]:
        x, y = F(.13, v0 + k, 70)
        svg.ellipse(x, y - 1, 3.4, 2.2, c, lw=1)
    x, y = F(.125, v0 + .02, 70)
    svg.line((x, y), (x, y - 9), PAL["dark"], lw=2)
    svg.ellipse(x, y - 10, 3, 3, PAL["coral"], lw=1)


def pingpong(svg):
    u0, u1, v0, v1 = .33, .60, .42, .60
    shadow(svg, [(u0 + .01, v0 + .01), (u1 + .02, v0 + .01), (u1 + .02, v1 + .02), (u0 + .01, v1 + .02)], .12)
    lg = PAL["dark"]
    for (u, v) in [(u0 + .02, v0 + .02), (u1 - .02, v0 + .02), (u0 + .02, v1 - .02), (u1 - .02, v1 - .02)]:
        box(svg, F, u - .007, u + .003, v - .007, v + .003, 0, 52, lg, lw=1.2)
    top = PAL["teal"]
    box(svg, F, u0, u1, v0, v1, 52, 58, top, lw=1.6)
    w = PAL["paper"]
    svg.line(F(u0 + .006, (v0 + v1) / 2, 58), F(u1 - .006, (v0 + v1) / 2, 58), w, lw=1.4)
    svg.poly([F(u0 + .006, v0 + .006, 58), F(u1 - .006, v0 + .006, 58), F(u1 - .006, v1 - .006, 58),
              F(u0 + .006, v1 - .006, 58)], "none", stroke=w, lw=1.4)
    # net across the middle
    um = (u0 + u1) / 2
    svg.poly([F(um, v0 - .012, 58), F(um, v1 + .012, 58), F(um, v1 + .012, 72), F(um, v0 - .012, 72)], w,
             stroke=shade(w, .7), lw=1.2, op=.75)
    svg.line(F(um, v0 - .012, 72), F(um, v1 + .012, 72), shade(w, .8), lw=1.6)
    # paddles and ball
    for (u, v, c) in [(.38, .47, PAL["coral"]), (.55, .56, PAL["sky_accent"])]:
        x, y = F(u, v, 58)
        svg.ellipse(x, y - 1, 7, 4, c, lw=1.1)
    x, y = F(.52, .47, 92)
    svg.ellipse(x, y, 4, 4, PAL["mustard"], lw=1.2)
    xs, ys = F(.52, .47, 58)
    svg.ellipse(xs, ys, 4, 2, "#000000", stroke=False, op=.12)


def beanbag(svg, u, v, col):
    x, y = F(u, v)
    svg.ellipse(x, y + 4, 40, 12, "#5a4630", stroke=False, op=.12)
    d = (f"M{f(x - 38)} {f(y + 2)}Q{f(x - 44)} {f(y - 30)} {f(x - 16)} {f(y - 44)}Q{f(x + 4)} {f(y - 54)} "
         f"{f(x + 22)} {f(y - 40)}Q{f(x + 46)} {f(y - 22)} {f(x + 38)} {f(y + 2)}Q{f(x)} {f(y + 16)} {f(x - 38)} "
         f"{f(y + 2)}Z")
    svg.path(d, col, lw=1.6)
    # shadow side and a soft dent on top
    d2 = (f"M{f(x + 6)} {f(y + 10)}Q{f(x + 30)} {f(y + 6)} {f(x + 38)} {f(y + 2)}Q{f(x + 46)} {f(y - 22)} "
          f"{f(x + 22)} {f(y - 40)}Q{f(x + 32)} {f(y - 14)} {f(x + 6)} {f(y + 10)}Z")
    svg.path(d2, shade(col, RIGHT_FACE), stroke=False)
    svg.ellipse(x - 4, y - 30, 17, 8, shade(col, .9), stroke=False)
    svg.path(f"M{f(x - 24)} {f(y - 36)}Q{f(x - 14)} {f(y - 46)} {f(x - 2)} {f(y - 46)}", "none",
             stroke=shade(col, 1.25), lw=2.4)


def foosball(svg):
    u0, u1, v0, v1 = .20, .34, .74, .84
    shadow(svg, [(u0, v0 + .01), (u1 + .02, v0 + .01), (u1 + .02, v1 + .02), (u0, v1 + .02)], .12)
    wd = PAL["wood"]
    for (u, v) in [(u0 + .015, v0 + .015), (u1 - .015, v0 + .015), (u0 + .015, v1 - .015), (u1 - .015, v1 - .015)]:
        box(svg, F, u - .008, u + .004, v - .008, v + .004, 0, 40, shade(wd, .8), lw=1.2)
    box(svg, F, u0, u1, v0, v1, 40, 62, wd, top=PAL["wood_dark"], lw=1.6)
    svg.poly([F(u0 + .01, v0 + .01, 62), F(u1 - .01, v0 + .01, 62), F(u1 - .01, v1 - .01, 62),
              F(u0 + .01, v1 - .01, 62)], PAL["sage"], lw=1.2)
    svg.line(F((u0 + u1) / 2, v0 + .01, 62.5), F((u0 + u1) / 2, v1 - .01, 62.5), PAL["paper"], lw=1.1, op=.8)
    for i, u in enumerate([.23, .26, .29, .32]):
        c = PAL["coral"] if i in (0, 2) else PAL["navy"]
        for vv in (.775, .805):
            x, y = F(u, vv, 62)
            svg.path(rr(x - 2.2, y - 9, x + 2.2, y, 1.5), c, lw=1)
        svg.line(F(u, v0 - .022, 66), F(u, v1 + .022, 66), PAL["metal"], lw=2.2)
        x, y = F(u, v1 + .026, 66)
        svg.ellipse(x, y, 2.6, 2.6, PAL["dark"], stroke=False)


def floor_lamp(svg, u, v):
    x, y = F(u, v)
    svg.ellipse(x, y, 9, 3.5, PAL["dark"], lw=1.2)
    svg.line((x, y - 2), (x, y - 150 * S), PAL["dark"], lw=2.2)
    t, b = y - 176 * S, y - 146 * S
    svg.path(f"M{f(x - 14)} {f(b)}L{f(x + 14)} {f(b)}L{f(x + 9)} {f(t)}L{f(x - 9)} {f(t)}Z", PAL["paper"], lw=1.4)
    svg.path(f"M{f(x + 4)} {f(b)}L{f(x + 14)} {f(b)}L{f(x + 9)} {f(t)}L{f(x + 3)} {f(t)}Z",
             shade(PAL["paper"], RIGHT_FACE), stroke=False)

def big_plant(svg, u, v):
    x, y = F(u, v)
    svg.ellipse(x, y + 1, 18, 6, "#5a4630", stroke=False, op=.13)
    svg.path(f"M{f(x - 15)} {f(y - 26)}L{f(x + 15)} {f(y - 26)}L{f(x + 11)} {f(y)}L{f(x - 11)} {f(y)}Z", PAL["paper"],
             lw=1.5)
    svg.path(f"M{f(x + 3)} {f(y - 26)}L{f(x + 15)} {f(y - 26)}L{f(x + 11)} {f(y)}L{f(x + 2)} {f(y)}Z",
             shade(PAL["paper"], RIGHT_FACE), stroke=False)
    rnd = random.Random(9)
    for i in range(16):
        a = rnd.uniform(-math.pi * .95, -math.pi * .05)
        d = rnd.uniform(14, 40)
        lx, ly = x + math.cos(a) * d * .9, y - 30 + math.sin(a) * d * 1.2
        svg.line((x, y - 26), (lx, ly), PAL["leaf_dark"], lw=1.2)
        svg.ellipse(lx, ly, 10, 5, PAL["leaf"] if i % 3 else PAL["leaf_dark"], lw=1.1,
                    extra=f'transform="rotate({f(math.degrees(a))} {f(lx)} {f(ly)})"')


ROOMS = {"office": office, "meet": meeting, "game": lounge}


def build(svg_dir):
    for name, fn in ROOMS.items():
        for night in (False, True):
            fn(night).save(f"{svg_dir}/{name}-{'night' if night else 'day'}.svg")
