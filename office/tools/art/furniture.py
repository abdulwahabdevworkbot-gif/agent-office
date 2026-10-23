"""Furniture sprites for the office (see STYLE.md and NOTES-rooms.md).

Rebuild all room, furniture and fx art with one command, from the repo root:

    python3 office/tools/art/build_rooms.py

Every sprite keeps the old file name, canvas size and the spot its footprint has in the canvas, so the page's
layout numbers stay valid. Each one is drawn on the real room floor with P() and then mapped into its canvas:

- the meeting table and meeting chairs mchair-0..7 sit where MEET puts them (canvas = MEET box);
- desk chairs are drawn at floor (.5, .5); the page pins their seat point (MEET["chair-<facing>"] ax, ay);
- desks, plants and the rest are drawn with the iso axes frozen at the room center, so one sprite fits every
  spot; their footprints were matched to the old sprites by overlay.

Lines are LW_ROOM room pixels wide whatever the sprite scale, so furniture reads the same as the room.
"""
import math, random
from isokit import (Svg, Frame, box, floor_poly, floor_ellipse, PAL, shade, mix, f, S, RW, RH, LEFT_FACE,
                    RIGHT_FACE, OUTLINE, HILITE)

LW_ROOM = 1.3          # furniture outline width in room pixels (room shell 2 px, characters ~0.65 px)
SEAT = 38              # seat height (h units); the page's SEAT_LIFT is 3.37 % of the room height = 38 h
FACE = {'front-left': (0, 1), 'front-right': (1, 0), 'rear-left': (-1, 0), 'rear-right': (0, -1)}

# the page's layout numbers this art must match (office.html MEET)
MEET = {"table": (35.01, 50.8, 29.18), "mchair-0": (47.35, 46.98, 5.37), "mchair-1": (54.11, 51.33, 5.24),
        "mchair-2": (60.94, 55.6, 5.04), "mchair-3": (33.29, 47.07, 5.57), "mchair-4": (32.82, 57.02, 5.57),
        "mchair-5": (40.25, 61.72, 5.44), "mchair-6": (47.68, 66.34, 5.37), "mchair-7": (61.07, 65.99, 5.11)}
DESK_CHAIR = {"front-left": (5.37, .48, .618), "front-right": (5.37, .53, .618), "rear-left": (5.37, .48, .551),
              "rear-right": (5.31, .524, .555)}
SEATS = [(.36, .33, 'front-left'), (.52, .33, 'front-left'), (.68, .33, 'front-left'), (.21, .50, 'front-right'),
         (.36, .67, 'rear-right'), (.52, .67, 'rear-right'), (.68, .67, 'rear-right'), (.83, .50, 'rear-left')]
# canvas sizes (unchanged from the old sprites)
SIZE = {"chair-front-left": (56, 98), "chair-front-right": (56, 99), "chair-rear-left": (56, 85),
        "chair-rear-right": (56, 86), "coffee": (160, 204), "desk-lf": (240, 301), "desk-lr": (240, 292),
        "desk-rf": (240, 301), "desk-rr": (240, 293), "filing": (160, 282), "mchair-0": (64, 101),
        "mchair-1": (63, 100), "mchair-2": (60, 101), "mchair-3": (67, 101), "mchair-4": (67, 88),
        "mchair-5": (65, 88), "mchair-6": (64, 88), "mchair-7": (61, 87), "money": (160, 257),
        "monstera": (160, 229), "printer": (160, 182), "snake": (160, 250), "table": (350, 217),
        "whiteboard": (160, 212)}
# page width (% of the room) each furnish() sprite is shown at (office.html F_MAIN / F_BOSS)
PAGE_W = {"desk": 10.5, "coffee": 5, "filing": 5.2, "money": 5.2, "monstera": 6.2, "snake": 5, "printer": 6.9,
          "whiteboard": 8.1}


def sprite_svg(name, k):
    w, h = SIZE[name]
    return Svg(w, h, lw=LW_ROOM * k)


def shadow(svg, F, uv, op=.13, n=4):
    svg.poly(floor_poly(F, uv, n=n), "#3d3226", stroke=False, op=op)


def rounded_rect_uv(u0, u1, v0, v1, r, n=5):
    out = []
    for cu, cv, a0 in [(u1 - r, v0 + r, -90), (u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180)]:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            out.append((cu + r * math.cos(a), cv + r * math.sin(a)))
    return out


def hull(points):
    pts_ = sorted(set((round(x, 3), round(y, 3)) for x, y in points))
    if len(pts_) < 3:
        return pts_

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts_:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts_):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def extrude(svg, F, uv, h0, h1, col, top=None, lw=None):
    """A convex floor shape (u, v points, counter-clockwise or not) raised from h0 to h1, shaded per side normal."""
    n = len(uv)
    cu = sum(p[0] for p in uv) / n
    cv = sum(p[1] for p in uv) / n
    sides = []
    for i in range(n):
        a, b = uv[i], uv[(i + 1) % n]
        nu, nv = (b[1] - a[1]), -(b[0] - a[0])
        mu, mv = (a[0] + b[0]) / 2 - cu, (a[1] + b[1]) / 2 - cv
        if nu * mu + nv * mv < 0:
            nu, nv = -nu, -nv
        ln = math.hypot(nu, nv) or 1
        nu, nv = nu / ln, nv / ln
        if nu + nv <= 0.02:
            continue
        t = math.atan2(nv, nu) / (math.pi / 2)        # 0 -> facing +u (right-front), 1 -> facing +v (left-front)
        t = max(0, min(1, t))
        fac = RIGHT_FACE + (LEFT_FACE - RIGHT_FACE) * t
        sides.append(([F(a[0], a[1], h0), F(b[0], b[1], h0), F(b[0], b[1], h1), F(a[0], a[1], h1)], shade(col, fac)))
    for q, c in sides:
        svg.poly(q, c, stroke=c, lw=.6)
    allp = [F(u, v, h0) for u, v in uv] + [F(u, v, h1) for u, v in uv]
    side_mid = shade(col, (RIGHT_FACE + LEFT_FACE) / 2)
    svg.poly(hull(allp), "none", stroke=shade(side_mid, OUTLINE), lw=lw)
    svg.poly([F(u, v, h1) for u, v in uv], top or col, lw=lw)


# ------------------------------------------------------------------------------------------------ chairs
def chair(svg, F, uc, vc, facing, s=.03, col=None):
    """Office chair with a five-star base, a cushion seat and a rounded backrest (old meeting_room.py geometry)."""
    col = col or PAL["fabric"]
    du, dv = FACE[facing]
    base = PAL["dark"]
    k = F.k
    svg.poly(floor_poly(F, rounded_rect_uv(uc - s * 1.15, uc + s * 1.15, vc - s * 1.15, vc + s * 1.15, s * 1.1), n=1),
             "#3d3226", stroke=False, op=.12)
    arms = []
    for i in range(5):
        a = math.radians(54 + 72 * i)
        arms.append((uc + math.cos(a) * s * 1.1, vc + math.sin(a) * s * 1.1))
    arms.sort(key=lambda p: p[0] + p[1])
    hub = F(uc, vc, 7)
    for (u, v) in arms:
        e = F(u, v, 5)
        svg.line(hub, e, shade(base, OUTLINE), lw=3.4 * k)
        svg.line(hub, e, shade(base, 1.25), lw=1.8 * k)
        x, y = F(u, v, 2)
        svg.ellipse(x, y, 2.1 * k, 1.6 * k, base, lw=.7 * k)
    a, b = F(uc, vc, 8), F(uc, vc, SEAT - 8)
    svg.line(a, b, shade(PAL["metal"], OUTLINE), lw=4.2 * k)
    svg.line(a, b, PAL["metal"], lw=2.6 * k)

    def back():
        t = .009
        if du:
            bu = uc - du * s * 1.02
            uv = (bu - t / 2, bu + t / 2)
            face_u = bu + t / 2                     # +u face is the visible one
            o, d = F(face_u, vc + s * .92, 0), F(face_u, vc - s * .92, 0)
        else:
            bv = vc - dv * s * 1.02
            face_v = bv + t / 2
            o, d = F(uc - s * .92, face_v, 0), F(uc + s * .92, face_v, 0)
        kk = (d[1] - o[1]) / (d[0] - o[0])
        wdt = d[0] - o[0]
        h0, h1 = SEAT + 7, SEAT + 56
        y0, y1 = -h0 * S * k, -h1 * S * k
        r = min(abs(wdt) * .3, 8 * k)
        facing_us = (du > 0) or (dv > 0)
        front = col if facing_us else shade(col, .78)
        # thickness: the same panel shifted toward the back, darker
        if du:
            off = (F(face_u - t, vc, 0)[0] - o[0], F(face_u - t, vc, 0)[1] - F(face_u, vc, 0)[1])
        else:
            off = (F(uc, face_v - t, 0)[0] - F(uc, face_v, 0)[0], F(uc, face_v - t, 0)[1] - F(uc, face_v, 0)[1])
        x0, x1 = min(0, wdt), max(0, wdt)
        path = (f"M{f(x0)} {f(y0)}V{f(y1 + r)}Q{f(x0)} {f(y1)} {f(x0 + r)} {f(y1)}H{f(x1 - r)}"
                f"Q{f(x1)} {f(y1)} {f(x1)} {f(y1 + r)}V{f(y0)}Z")
        fc = shade(front, RIGHT_FACE if du else LEFT_FACE)
        svg.group(f'transform="matrix(1 {kk:.5f} 0 1 {f(o[0] + off[0])} {f(o[1] + off[1])})"')
        svg.path(path, shade(fc, .8))
        svg.end()
        svg.group(f'transform="matrix(1 {kk:.5f} 0 1 {f(o[0])} {f(o[1])})"')
        svg.path(path, fc)
        if facing_us:      # cushion seam and a soft highlight
            svg.path(f"M{f(x0 + 3 * k)} {f(y1 + 6 * k)}Q{f((x0 + x1) / 2)} {f(y1 + 3 * k)} {f(x1 - 3 * k)} {f(y1 + 6 * k)}",
                     "none", stroke=shade(fc, HILITE), lw=1.6 * k)
        svg.end()
        # post from the seat to the backrest
        if du:
            p0, p1 = F(uc - du * s * .9, vc, SEAT - 4), F(uc - du * s * 1.02, vc, h0 + 4)
        else:
            p0, p1 = F(uc, vc - dv * s * .9, SEAT - 4), F(uc, vc - dv * s * 1.02, h0 + 4)
        svg.line(p0, p1, shade(base, OUTLINE), lw=3.6 * k)
        svg.line(p0, p1, shade(base, 1.2), lw=2 * k)

    behind = du < 0 or dv < 0
    if not behind:
        back()
    seat = rounded_rect_uv(uc - s, uc + s, vc - s, vc + s, s * .3)
    extrude(svg, F, seat, SEAT - 7, SEAT, col, top=shade(col, 1.06))
    if behind:
        back()


def mchair(i):
    name = f"mchair-{i}"
    x, y, w = MEET[name]
    cw, ch = SIZE[name]
    k = cw / (w * RW / 100)
    F = Frame(k, -k * x * RW / 100, -k * y * RH / 100)
    svg = sprite_svg(name, k)
    u, v, fc = SEATS[i]
    chair(svg, F, u, v, fc)
    return svg


def desk_chair(facing):
    name = f"chair-{facing}"
    w, ax, ay = DESK_CHAIR[facing]
    cw, ch = SIZE[name]
    k = cw / (w * RW / 100)
    F0 = Frame()
    sx, sy = F0(.5, .5, SEAT)
    F = Frame(k, ax * cw - k * sx, ay * ch - k * sy)
    svg = sprite_svg(name, k)
    chair(svg, F, .5, .5, facing)
    return svg


# ------------------------------------------------------------------------------------------------ table
def table():
    x, y, w = MEET["table"]
    cw, ch = SIZE["table"]
    k = cw / (w * RW / 100)
    F = Frame(k, -k * x * RW / 100, -k * y * RH / 100)
    svg = sprite_svg("table", k)
    u0, u1, v0, v1 = .28, .76, .40, .60
    shadow(svg, F, rounded_rect_uv(u0 + .01, u1 + .015, v0 + .015, v1 + .02, .04), .12, n=1)
    leg = mix(PAL["metal"], PAL["paper"], .3)
    for (u, v) in [(.30, .42), (.74, .42), (.30, .58), (.74, .58)]:
        box(svg, F, u - .007, u + .007, v - .007, v + .007, 0, 59, leg)
    top = mix(PAL["wood"], PAL["paper"], .38)
    extrude(svg, F, rounded_rect_uv(u0, u1, v0, v1, .035), 58, 67, top)
    # a soft highlight line along the back edge
    svg.pline([F(u, v0 + .006, 67) for u in (u0 + .04, u1 - .04)], shade(top, HILITE), lw=1.6 * k)
    # notebooks, a laptop and a small plant, all flat and calm
    for (u, v, c) in [(.37, .45, PAL["sky_accent"]), (.63, .55, PAL["sage"])]:
        svg.poly([F(u - .022, v - .016, 67.5), F(u + .022, v - .016, 67.5), F(u + .022, v + .016, 67.5),
                  F(u - .022, v + .016, 67.5)], c)
        svg.poly([F(u - .018, v - .012, 68), F(u + .018, v - .012, 68), F(u + .018, v + .012, 68),
                  F(u - .018, v + .012, 68)], PAL["paper"], stroke=False)
    # laptop: base and an open lid facing +v
    lu, lv = .53, .46
    svg.poly([F(lu - .03, lv - .02, 68), F(lu + .03, lv - .02, 68), F(lu + .03, lv + .02, 68), F(lu - .03, lv + .02, 68)],
             PAL["metal"])
    svg.poly([F(lu - .03, lv - .02, 68), F(lu + .03, lv - .02, 68), F(lu + .03, lv - .024, 92),
              F(lu - .03, lv - .024, 92)], PAL["dark"])
    svg.poly([F(lu - .026, lv - .0195, 70.5), F(lu + .026, lv - .0195, 70.5), F(lu + .026, lv - .0235, 89.5),
              F(lu - .026, lv - .0235, 89.5)], PAL["screen_glow"], stroke=False)
    # centerpiece
    px, py = F(.45, .53, 67)
    svg.path(f"M{f(px - 6 * k)} {f(py - 9 * k)}L{f(px + 6 * k)} {f(py - 9 * k)}L{f(px + 4.5 * k)} {f(py)}"
             f"L{f(px - 4.5 * k)} {f(py)}Z", PAL["paper"])
    rnd = random.Random(2)
    for j in range(7):
        a = math.pi + (j + .5) * math.pi / 7 + rnd.uniform(-.2, .2)
        lx, ly = px + math.cos(a) * 7 * k, py - 11 * k + math.sin(a) * 6 * k
        svg.ellipse(lx, ly, 4.5 * k, 2.4 * k, PAL["leaf"] if j % 2 else PAL["leaf_dark"], lw=.9 * k,
                    extra=f'transform="rotate({f(math.degrees(a))} {f(lx)} {f(ly)})"')
    # glasses of water
    for (u, v) in [(.33, .55), (.70, .44)]:
        gx, gy = F(u, v, 67)
        svg.path(f"M{f(gx - 3 * k)} {f(gy - 9 * k)}L{f(gx + 3 * k)} {f(gy - 9 * k)}L{f(gx + 2.4 * k)} {f(gy)}"
                 f"L{f(gx - 2.4 * k)} {f(gy)}Z", mix(PAL["glass"], PAL["paper"], .3), op=.9)
    return svg


# ------------------------------------------------------------------------------------------------ desks
DESK = dict(Lu=.078, Lv=.175, ht=71)


def desk_frame(name, back_top):
    """Desk frame: iso axes frozen at the room center, the desktop's back corner (top face) at canvas back_top."""
    k = SIZE[name][0] / (PAGE_W["desk"] * RW / 100)
    F0 = Frame(k, 0, 0, linear_at=(.5, .5))
    bx, by = F0(0, 0, DESK["ht"])
    return Frame(k, back_top[0] - bx, back_top[1] - by, linear_at=(.5, .5)), k


def monitor(svg, F, u, v0, v1, h0, facing_us=True, k=1.0):
    """A wide monitor on a stand, standing along v (panel in the plane u = const)."""
    vm = (v0 + v1) / 2
    hs = h0 + 10
    stand = PAL["metal"]
    # foot and neck
    svg.poly([F(u - .012, vm - .014, h0 + .5), F(u + .006, vm - .014, h0 + .5), F(u + .006, vm + .014, h0 + .5),
              F(u - .012, vm + .014, h0 + .5)], shade(stand, 1.05))
    box(svg, F, u - .005, u, vm - .004, vm + .004, h0, hs + 8, stand)
    pu = u + .002
    th = .006
    frame_c = PAL["dark"]
    top = hs + 42
    if facing_us:
        box(svg, F, pu - th, pu, v0, v1, hs, top, frame_c, side=shade(frame_c, 1.05))
        svg.poly([F(pu, v0 + .006, hs + 4), F(pu, v1 - .006, hs + 4), F(pu, v1 - .006, top - 4),
                  F(pu, v0 + .006, top - 4)], PAL["screen"], stroke=False)
        # calm code lines on the screen
        rnd = random.Random(int(v0 * 1000))
        cols = [PAL["screen_glow"], PAL["sage"], PAL["mustard"], PAL["rose"], PAL["lavender"]]
        hh = top - 10
        while hh > hs + 9:
            a = v1 - .012 - rnd.uniform(0, .02)
            ln = rnd.uniform(.025, (v1 - v0) * .6)
            svg.line(F(pu, a, hh), F(pu, max(v0 + .012, a - ln), hh), cols[rnd.randrange(5)], lw=2.2 * k, op=.9)
            hh -= 6.5
        svg.poly([F(pu, v1 - .012, top - 6), F(pu, v1 - .03, top - 6), F(pu, v1 - .055, hs + 6),
                  F(pu, v1 - .037, hs + 6)], "#ffffff", stroke=False, op=.10)
    else:
        box(svg, F, pu - th, pu, v0, v1, hs, top, shade(frame_c, 1.25))
        svg.poly([F(pu, vm - .03, hs + 10), F(pu, vm + .03, hs + 10), F(pu, vm + .03, top - 12),
                  F(pu, vm - .03, top - 12)], shade(frame_c, 1.12), lw=.8 * k)


def mug(svg, F, u, v, h, col, k):
    x, y = F(u, v, h)
    svg.path(f"M{f(x - 4.4 * k)} {f(y - 9 * k)}L{f(x + 4.4 * k)} {f(y - 9 * k)}L{f(x + 4 * k)} {f(y)}"
             f"L{f(x - 4 * k)} {f(y)}Z", col)
    svg.path(f"M{f(x + 4 * k)} {f(y - 7 * k)}q{f(4 * k)} {f(1 * k)} {f(.3 * k)} {f(5 * k)}", "none",
             stroke=shade(col, OUTLINE), lw=1.4 * k)
    svg.ellipse(x, y - 9 * k, 4.4 * k, 1.6 * k, shade(col, .55), lw=.8 * k)


def tiny_plant(svg, F, u, v, h, k, seed=4):
    x, y = F(u, v, h)
    svg.path(f"M{f(x - 5 * k)} {f(y - 8 * k)}L{f(x + 5 * k)} {f(y - 8 * k)}L{f(x + 4 * k)} {f(y)}"
             f"L{f(x - 4 * k)} {f(y)}Z", PAL["pot"])
    rnd = random.Random(seed)
    for j in range(6):
        a = math.pi + (j + .5) * math.pi / 6 + rnd.uniform(-.25, .25)
        lx, ly = x + math.cos(a) * 5.5 * k, y - 10 * k + math.sin(a) * 6 * k
        svg.ellipse(lx, ly, 4 * k, 2.2 * k, PAL["leaf"] if j % 2 else PAL["leaf_dark"], lw=.9 * k,
                    extra=f'transform="rotate({f(math.degrees(a))} {f(lx)} {f(ly)})"')


def desk(kind):
    """kind 'lf': screens toward the viewer (user on the +u side); 'lr': screens away (user on the -u side)."""
    name = "desk-" + kind
    back_top = {"lf": (162, 76), "lr": (162, 60)}[kind]
    F, k = desk_frame(name, back_top)
    svg = sprite_svg(name, k)
    Lu, Lv, ht = DESK["Lu"], DESK["Lv"], DESK["ht"]
    # soft shadow on the floor under the desk
    shadow(svg, F, [(.004, .01), (Lu + .02, .01), (Lu + .02, Lv + .012), (.004, Lv + .012)], .12, n=1)
    leg = mix(PAL["metal"], PAL["paper"], .25)
    # T-legs under both short ends: foot bar along u, column, then a crossbar under the top
    for vb in (.022, Lv - .022):
        box(svg, F, -.008, Lu + .008, vb - .006, vb + .006, 0, 6, leg)
        box(svg, F, Lu / 2 - .006, Lu / 2 + .006, vb - .006, vb + .006, 6, ht - 6, leg)
    box(svg, F, Lu / 2 - .004, Lu / 2 + .004, .022, Lv - .022, ht - 12, ht - 6, shade(leg, .9))
    # desktop: white top with a light oak edge
    top = PAL["desk"]
    box(svg, F, 0, Lu, 0, Lv, ht - 6, ht, mix(PAL["wood"], PAL["paper"], .35), top=top)
    svg.pline([F(.006, .008, ht), F(.006, Lv - .008, ht)], shade(top, HILITE), lw=1.4 * k)
    if kind == "lf":
        monitor(svg, F, .016, .035, .15, ht, True, k)
        # keyboard and mouse in front of the screen, a mug on the left
        svg.poly([F(.042, .055, ht + .5), F(.058, .055, ht + .5), F(.058, .118, ht + .5), F(.042, .118, ht + .5)],
                 mix(PAL["metal"], PAL["paper"], .5))
        for j in range(3):
            uu = .046 + j * .004
            svg.line(F(uu, .06, ht + 1), F(uu, .113, ht + 1), shade(PAL["metal"], .9), lw=.9 * k, op=.8)
        x, y = F(.05, .036, ht)
        svg.ellipse(x, y - 1.5 * k, 3.2 * k, 2 * k, PAL["paper"], lw=.9 * k)
        mug(svg, F, .045, .155, ht, PAL["coral"], k)
    else:
        # notebook and pen on the near side, a small plant at the end, monitor seen from the back
        svg.poly([F(.022, .11, ht + .5), F(.048, .11, ht + .5), F(.048, .145, ht + .5), F(.022, .145, ht + .5)],
                 PAL["sky_accent"])
        svg.poly([F(.025, .114, ht + 1), F(.045, .114, ht + 1), F(.045, .141, ht + 1), F(.025, .141, ht + 1)],
                 PAL["paper"], stroke=False)
        tiny_plant(svg, F, .05, .03, ht, k)
        monitor(svg, F, .058, .04, .155, ht, False, k)
    return svg


def mirrored(svg_fn, name):
    """Mirror image of a desk (desk-rf from desk-lf, desk-rr from desk-lr) on its own canvas."""
    s = svg_fn()
    w, h = SIZE[name]
    m = Svg(w, h, lw=s.lw)
    m.defs = s.defs
    m.body = [f'<g transform="translate({w} 0) scale(-1 1)">'] + s.body + ["</g>"]
    return m


SPRITES = {
    "table": table,
    **{f"mchair-{i}": (lambda i=i: mchair(i)) for i in range(8)},
    **{f"chair-{fc}": (lambda fc=fc: desk_chair(fc)) for fc in FACE},
    "desk-lf": lambda: desk("lf"),
    "desk-lr": lambda: desk("lr"),
    "desk-rf": lambda: mirrored(lambda: desk("lf"), "desk-rf"),
    "desk-rr": lambda: mirrored(lambda: desk("lr"), "desk-rr"),
}


def build(svg_dir, only=None):
    for name, fn in SPRITES.items():
        if only and name not in only:
            continue
        fn().save(f"{svg_dir}/{name}.svg")
