#!/usr/bin/env python3
"""Character generator for the agent office (see STYLE.md and NOTES-chars.md).

Rebuild everything (frames, masks, manifest, sheets) with one command, from the repo root:

    python3 office/tools/art/chars.py

Options: --only id1,id2 (draw a subset, no clean-up of the manifest), --work DIR (scratch folder for svg/png),
--no-sheets.  Needs node + playwright (render.cjs) and Python with PIL and numpy.

Each character is data (skin, hair, headwear, garments, accessories) drawn by shared part functions in two views:
front 3/4 ("front-left": facing the viewer, turned to screen right) and rear 3/4 ("rear-right": back to the viewer,
turned to screen left).  front-right and rear-left are mirrors.  Every part is drawn once for the color frame and once
for the mask frame (hair #ff0000, main top garment #00ff00, everything else #000000).
"""
import argparse, json, math, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from style import PAL, shade, OUTLINE, HILITE  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CHARS = os.path.join(ROOT, "office", "assets", "chars")
MASKS = os.path.join(ROOT, "office", "assets", "masks")
DOCS = os.path.join(ROOT, "docs", "images")
W, H = 72, 200
LW = 1.1            # outline width at character scale (STYLE.md)
SHADOW = 0.84       # left-front plane vs right-front plane (0.72 / 0.86 in STYLE.md)
PIVOT = (36.0, 63.0)  # head group scales about the neck so every figure's top reaches the top rows

MASKCOL = {"hair": "#ff0000", "top": "#00ff00", "o": "#000000"}


# ----------------------------------------------------------------------------------------------- path helpers
def f(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def P(*pts):
    """Polyline / polygon from points: P((x,y),...) -> 'M.. L.. Z'."""
    return "M" + " L".join("%s %s" % (f(x), f(y)) for x, y in pts) + " Z"


def ell(cx, cy, rx, ry=None):
    ry = rx if ry is None else ry
    return "M%s %s A%s %s 0 1 0 %s %s A%s %s 0 1 0 %s %s Z" % (
        f(cx - rx), f(cy), f(rx), f(ry), f(cx + rx), f(cy), f(rx), f(ry), f(cx - rx), f(cy))


def rect(x, y, w, h, r=0):
    if not r:
        return P((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    r = min(r, w / 2, h / 2)
    return ("M%s %s H%s Q%s %s %s %s V%s Q%s %s %s %s H%s Q%s %s %s %s V%s Q%s %s %s %s Z" % tuple(map(f, (
        x + r, y, x + w - r, x + w, y, x + w, y + r, y + h - r, x + w, y + h, x + w - r, y + h,
        x + r, x, y + h, x, y + h - r, y + r, x, y, x + r, y))))


_TOK = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?")


def xform(d, fn, mirror=False):
    """Apply fn(x,y)->(x,y) to every point of an absolute path (M L C Q S T A H V Z)."""
    out, toks, i, cmd = [], _TOK.findall(d), 0, None
    nums = {"M": 2, "L": 2, "C": 6, "Q": 4, "S": 4, "T": 2, "A": 7, "H": 1, "V": 1, "Z": 0}
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; out.append(t); i += 1
            if cmd == "Z":
                continue
        n = nums[cmd.upper()]
        a = [float(x) for x in toks[i:i + n]]; i += n
        if cmd == "A":
            x, y = fn(a[5], a[6])
            sweep = (1 - int(a[4])) if mirror else int(a[4])
            out.append(" ".join(map(f, (a[0], a[1], -a[2] if mirror else a[2]))) + " %d %d " % (int(a[3]), sweep)
                       + f(x) + " " + f(y))
        elif cmd == "H":
            out.append(f(fn(a[0], 0)[0]))
        elif cmd == "V":
            out.append(f(fn(0, a[0])[1]))
        else:
            pts = [fn(a[k], a[k + 1]) for k in range(0, n, 2)]
            out.append(" ".join(f(x) + " " + f(y) for x, y in pts))
    return " ".join(out).replace(" Z", "Z")


def mx(d, cx):
    return xform(d, lambda x, y: (2 * cx - x, y), mirror=True)


def mv(d, dx, dy):
    return xform(d, lambda x, y: (x + dx, y + dy))


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(lerp(x, y, t)) for x, y in zip(a, b))


def bumps(pts, amp=1.6, closed=False):
    """Scalloped curve through points (curly hair edges): each segment bulges outward (to its left)."""
    seq = pts + ([pts[0]] if closed else [])
    d = "M%s %s" % (f(seq[0][0]), f(seq[0][1]))
    for (x0, y0), (x1, y1) in zip(seq, seq[1:]):
        mxp, myp = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1
        nx, ny = dy / ln, -dx / ln
        d += " Q%s %s %s %s" % (f(mxp + nx * amp * 2), f(myp + ny * amp * 2), f(x1), f(y1))
    return d + ("Z" if closed else "")


def arc_pts(cx, cy, rx, ry, a0, a1, n):
    """Points on an ellipse from angle a0 to a1 (degrees, 0 = right, 90 = down)."""
    return [(cx + rx * math.cos(math.radians(lerp(a0, a1, k / n))), cy + ry * math.sin(math.radians(lerp(a0, a1, k / n))))
            for k in range(n + 1)]


# ----------------------------------------------------------------------------------------------- figure
class Fig:
    """Collects drawing items with a z order; emits a color svg and a mask svg from the same shapes."""

    def __init__(self, view):
        self.view = view
        self.items, self.defs, self.mdefs = [], [], []
        self.seq, self.z, self.head, self.nclip = 0, 0, False, 0

    def _add(self, color, mask):
        self.items.append((self.z, self.seq, self.head, color, mask)); self.seq += 1

    def at(self, z, head=False):
        self.z, self.head = z, head
        return self

    def shape(self, d, fill, role="o", shadow=(), hi=(), lw=LW, lc=None, sc=None, hc=None, mask=True, op=None,
              mfill=None, rule=None):
        """A filled part with its own outline (fill x 0.55), optional shadow and highlight areas clipped to it."""
        lc = lc or (shade(fill, OUTLINE) if fill.startswith("#") else "#555")
        o = ' opacity="%s"' % f(op) if op is not None else ""
        fr = ' fill-rule="evenodd"' if rule else ""
        if shadow or hi:
            self.nclip += 1
            cid = "c%d" % self.nclip
            self.defs.append('<clipPath id="%s"><path d="%s"%s/></clipPath>' % (cid, d, ' clip-rule="evenodd"' if rule else ""))
            s = '<path d="%s" fill="%s"%s/><g clip-path="url(#%s)">' % (d, fill, fr, cid)
            for sd in ([shadow] if isinstance(shadow, str) else shadow):
                s += '<path d="%s" fill="%s"/>' % (sd, sc or shade(fill if fill.startswith("#") else "#888888", SHADOW))
            for hd in ([hi] if isinstance(hi, str) else hi):
                s += '<path d="%s" fill="%s"/>' % (hd, hc or shade(fill if fill.startswith("#") else "#888888", HILITE))
            s += "</g>"
            if lw:
                s += '<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>' % (d, lc, f(lw))
            color = "<g%s>%s</g>" % (o, s) if o else s
        else:
            st = ' stroke="%s" stroke-width="%s" stroke-linejoin="round"' % (lc, f(lw)) if lw else ""
            color = '<path d="%s" fill="%s"%s%s%s/>' % (d, fill, fr, st, o)
        m = None
        if mask:
            mc = mfill or MASKCOL[role]
            st = ' stroke="%s" stroke-width="%s" stroke-linejoin="round"' % (mc, f(lw)) if lw else ""
            m = '<path d="%s" fill="%s"%s%s/>' % (d, mc, fr, st)
        self._add(color, m)

    def line(self, d, color, lw=0.9, role=None, cap="round", op=None):
        o = ' opacity="%s"' % f(op) if op is not None else ""
        self._add('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="%s" stroke-linejoin="round"%s/>'
                  % (d, color, f(lw), cap, o),
                  None if role is None else '<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="%s"/>'
                  % (d, MASKCOL[role], f(lw), cap))

    def fill(self, d, color, op=None, role=None):
        """Flat area with no outline (shading, pattern, small details)."""
        o = ' opacity="%s"' % f(op) if op is not None else ""
        self._add('<path d="%s" fill="%s"%s/>' % (d, color, o),
                  None if role is None else '<path d="%s" fill="%s"/>' % (d, MASKCOL[role]))

    def raw(self, color, mask=None):
        self._add(color, mask)

    def svg(self, which, head_scale=1.0):
        px, py = PIVOT
        tf = "translate(%s %s) scale(%s) translate(%s %s)" % (f(px), f(py), "%.4f" % head_scale, f(-px), f(-py))
        body, open_g = [], False
        for z, seq, head, c, m in sorted(self.items, key=lambda t: (t[0], t[1])):
            s = c if which == "color" else m
            if s is None:
                continue
            if head and not open_g:
                body.append('<g transform="%s">' % tf); open_g = True
            if not head and open_g:
                body.append("</g>"); open_g = False
            body.append(s)
        if open_g:
            body.append("</g>")
        defs = self.defs if which == "color" else self.mdefs
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H)
                + ("<defs>%s</defs>" % "".join(defs) if defs else "") + "".join(body) + "</svg>")


# ----------------------------------------------------------------------------------------------- build geometry
# Two builds share one skeleton: waist / seat line at y=112, feet on the bottom rows, the near (screen-left) side is
# the shaded side plane in both views.
BUILD = {
    "m": dict(nl=(30.6, 63.0), nr=(41.4, 63.0), sl=(19.4, 70.4), sr=(52.6, 70.4), wl=(22.8, 112.5), wr=(49.4, 112.5),
              arm=8.6, wrist=7.2, leg_l=(23.0, 36.8), leg_r=(36.0, 48.8), ank_l=(25.2, 35.6), ank_r=(38.0, 47.6)),
    "f": dict(nl=(31.4, 63.4), nr=(40.6, 63.4), sl=(21.6, 71.0), sr=(50.4, 71.0), wl=(25.2, 103.0), wr=(46.8, 103.0),
              hl=(23.6, 113.0), hr=(48.6, 113.0),
              arm=7.2, wrist=5.8, leg_l=(24.4, 36.6), leg_r=(36.0, 47.8), ank_l=(26.6, 34.6), ank_r=(38.6, 46.2)),
}
BUILD["b"] = dict(BUILD["m"], sl=(17.6, 70.6), sr=(54.4, 70.6), wl=(21.4, 112.5), wr=(50.8, 112.5), arm=9.4, wrist=7.8,
                  leg_l=(22.0, 36.8), leg_r=(36.0, 50.0))


def torso_d(b, hem=None, flare=0.0, neck_dip=2.2):
    """Torso outline.  hem: y of the bottom (default waist); flare: extra width at the hem for robes and tunics."""
    nl, nr, sl, sr = b["nl"], b["nr"], b["sl"], b["sr"]
    wl, wr = b["wl"], b["wr"]
    d = "M%s %s C%s %s %s %s %s %s " % tuple(map(f, (nl[0], nl[1], nl[0] - 4.5, nl[1] + 1.3, sl[0] + 1.5, sl[1] - 4.6, sl[0], sl[1])))
    if "hl" in b and (hem is None or hem > b["wl"][1]):
        hl, hr = b["hl"], b["hr"]
        d += "C%s %s %s %s %s %s " % tuple(map(f, (sl[0] - 0.8, sl[1] + 6, wl[0] - 1.6, wl[1] - 14, wl[0], wl[1])))
        bot = hem if hem else hl[1]
        if hem and hem > hl[1] + 2:
            d += "C%s %s %s %s %s %s L%s %s " % tuple(map(f, (wl[0] - 0.6, wl[1] + 4, hl[0], hl[1] - 5, hl[0], hl[1],
                                                               hl[0] - flare, bot)))
            d += "L%s %s L%s %s " % tuple(map(f, (hr[0] + flare, bot, hr[0], hr[1])))
        else:
            d += "C%s %s %s %s %s %s " % tuple(map(f, (wl[0] - 0.6, wl[1] + 4, hl[0], hl[1] - 5, hl[0] - flare, bot)))
            d += "L%s %s " % (f(hr[0] + flare), f(bot))
        d += "C%s %s %s %s %s %s " % tuple(map(f, (hr[0], hr[1] - 5, wr[0] + 0.6, wr[1] + 4, wr[0], wr[1])))
        d += "C%s %s %s %s %s %s " % tuple(map(f, (wr[0] + 1.6, wr[1] - 14, sr[0] + 0.8, sr[1] + 6, sr[0], sr[1])))
    else:
        bot = hem if hem else wl[1]
        if hem and hem > wl[1] + 2:
            d += "C%s %s %s %s %s %s L%s %s L%s %s L%s %s " % tuple(map(f, (
                sl[0] - 0.8, sl[1] + 4, wl[0] - 1.6, wl[1] - 25, wl[0], wl[1], wl[0] - flare, bot,
                wr[0] + flare, bot, wr[0], wr[1])))
        else:
            d += "C%s %s %s %s %s %s L%s %s " % tuple(map(f, (sl[0] - 0.8, sl[1] + 4, wl[0] - 1.6, wl[1] - 25,
                                                             wl[0] - flare, bot, wr[0] + flare, bot)))
        d += "C%s %s %s %s %s %s " % tuple(map(f, (wr[0] + 1.6, wr[1] - 25, sr[0] + 0.8, sr[1] + 4, sr[0], sr[1])))
    d += "C%s %s %s %s %s %s " % tuple(map(f, (sr[0] - 1.5, sr[1] - 4.6, nr[0] + 4.5, nr[1] + 1.3, nr[0], nr[1])))
    d += "C%s %s %s %s %s %sZ" % tuple(map(f, (nr[0] - 3, nr[1] + neck_dip, nl[0] + 3, nl[1] + neck_dip, nl[0], nl[1])))
    return d


def arm_d(b, side, length=104.0, top_w=None, bot_w=None, wide=0.0):
    """Arm or sleeve as a rounded column hanging from the shoulder.  side: 'n' near (screen-left), 'f' far."""
    tw = top_w or b["arm"]
    bw = bot_w or b["wrist"]
    if side == "n":
        cx, cy = b["sl"][0], b["sl"][1] + 1.5
        bx = cx - 0.9
    else:
        cx, cy = b["sr"][0] + 0.2, b["sr"][1] + 1.5
        bx = cx + 0.9
    l0, r0 = cx - tw / 2, cx + tw / 2
    l1, r1 = bx - bw / 2 - wide, bx + bw / 2 + wide
    top = cy - tw / 2 - 0.5
    return ("M%s %s C%s %s %s %s %s %s L%s %s Q%s %s %s %s L%s %s Q%s %s %s %s L%s %s C%s %s %s %s %s %sZ" % tuple(map(f, (
        cx, top, cx + tw * 0.42, top, r0, cy - tw * 0.18, r0, cy + 1.5,
        r1, length - 1.2, r1, length, r1 - 1.2, length, l1 + 1.2, length, l1, length, l1, length - 1.2,
        l0, cy + 1.5, l0, cy - tw * 0.18, cx - tw * 0.42, top, cx, top))))


def hand_pos(b, side, length=104.0):
    if side == "n":
        return b["sl"][0] - 0.9, length + 2.6
    return b["sr"][0] + 1.1, length + 2.4


def leg_d(b, side, top=110.0, bottom=None, ank=None):
    if side == "n":
        x0, x1 = b["leg_l"]; a0, a1 = ank or b["ank_l"]; bot = bottom or 189.5
    else:
        x0, x1 = b["leg_r"]; a0, a1 = ank or b["ank_r"]; bot = bottom or 186.5
    return P((x0, top), (x1, top), (a1, bot), (a0, bot))


# ----------------------------------------------------------------------------------------------- body parts
def skin_tones(c):
    return dict(base=c, sh=shade(c, 0.88), line=shade(c, OUTLINE), blush=mix(c, "#ff6f7d", 0.42),
                lip=mix(shade(c, 0.62), "#b2434f", 0.45), dark=shade(c, 0.74))


def draw_neck(fig, ch, view):
    s = skin_tones(ch["skin"])
    fig.at(35)
    d = P((31.4, 52), (40.6, 52), (41.0, 66.5), (31.0, 66.5))
    fig.shape(d, s["base"], shadow=[P((30, 50), (43, 50), (43, 58.5), (30, 60.5)) if view == "front"
                                    else P((30, 50), (34, 50), (34, 68), (30, 68))], sc=s["sh"])


def draw_hand(fig, ch, b, side, length=104.0, z=None):
    s = skin_tones(ch["skin"])
    x, y = hand_pos(b, side, length)
    r = 3.5 if ch["build"] != "f" else 3.1
    if side == "f":
        r -= 0.25
    fig.shape(ell(x, y, r, r * 1.05), s["base"], shadow=[P((x - 9, y - 9), (x - 0.6, y - 9), (x - 1.6, y + 9), (x - 9, y + 9))],
              sc=s["sh"])


def shoes(fig, ch, view, kind="shoe", color=None, y_n=199.6, y_f=196.6):
    """Feet: near foot on the bottom row, far foot 3 px higher; front view toes point right, rear view left."""
    b = BUILD[ch["build"]]
    c = color or PAL["shoe"]
    fig.at(22)
    small = ch["build"] == "f"
    for side in ("f", "n"):
        a0, a1 = b["ank_l"] if side == "n" else b["ank_r"]
        bot = y_n if side == "n" else y_f
        cx = (a0 + a1) / 2
        if kind == "babouche":
            ln, ht = 8.5, 6.2
        elif small:
            ln, ht = 7.2, 7.0
        else:
            ln, ht = 8.8, 8.4
        x0 = a0 - 1.2
        top = bot - ht
        toe = a1 + ln - 3.0
        d = ("M%s %s L%s %s C%s %s %s %s %s %s C%s %s %s %s %s %s L%s %s C%s %s %s %s %s %sZ" % tuple(map(f, (
            x0 + 0.4, top, a1 - 1.0, top, toe - 2.2, top + 0.4, toe + 1.2, top + ht * 0.45, toe + 1.2, bot - 2.6,
            toe + 1.2, bot - 0.7, toe - 0.6, bot, toe - 2.4, bot, x0 + 1.2, bot, x0 - 0.2, bot, x0, bot - 1.4, x0, bot - 2.8))))
        if view == "rear":
            d = mx(d, cx)
        if kind == "sneaker":
            fig.shape(d, c, shadow=[P((0, bot - 2.2), (72, bot - 2.2), (72, 201), (0, 201))], sc=PAL["paper"],
                      hi=[], lc=shade(c, 0.6))
            fig.line("M%s %s L%s %s" % (f(x0), f(bot - 2.2), f(toe + 1), f(bot - 2.2)) if view == "front" else
                     "M%s %s L%s %s" % (f(2 * cx - toe - 1), f(bot - 2.2), f(2 * cx - x0), f(bot - 2.2)), shade(c, 0.7), 0.6)
        else:
            sole = shade(c, 0.7)
            fig.shape(d, c, shadow=[P((0, bot - 1.5), (72, bot - 1.5), (72, 201), (0, 201))], sc=sole,
                      hi=[ell(toe - 3.2 if view == "front" else 2 * cx - toe + 3.2, top + 2.6, 1.8, 1.0)])


def trousers(fig, ch, view, color, top=110.0, cuff=None, wide=0.0, ank_y=None):
    b = BUILD[ch["build"]]
    fig.at(20)
    sh = shade(color, SHADOW)
    for side in ("f", "n"):
        x0, x1 = b["leg_l"] if side == "n" else b["leg_r"]
        a0, a1 = b["ank_l"] if side == "n" else b["ank_r"]
        bot = (ank_y or 191.5) if side == "n" else (ank_y or 191.5) - 3
        a0 -= wide; a1 += wide
        d = P((x0, top), (x1, top), (a1, bot), (a0, bot))
        shd = [P((x0 - 2, top), (x0 + 3.2, top), (a0 + 2.6, bot + 1), (a0 - 2, bot + 1))]
        if side == "f":
            shd = [P((x0 - 2, top), (x1 + 2, top), (x1 + 2, top + 9), (x0 - 2, top + 9))] + shd
        fig.shape(d, color, shadow=shd, sc=sh)
        if cuff:
            fig.fill(P((a0, bot - 2.2), (a1, bot - 2.2), (a1, bot), (a0, bot)), shade(color, 0.78))
    # crease and seam hints
    fig.line("M36.4 %s L36.2 %s" % (f(top + 3), f(top + 10)), shade(color, 0.7), 0.7)


def bare_legs(fig, ch, view, top=140.0):
    b = BUILD[ch["build"]]
    s = skin_tones(ch["skin"])
    fig.at(19)
    for side in ("f", "n"):
        a0, a1 = b["ank_l"] if side == "n" else b["ank_r"]
        bot = 193.5 if side == "n" else 190.5
        cx = (a0 + a1) / 2
        d = P((cx - 3.6, top), (cx + 3.6, top), (cx + 2.7, bot), (cx - 2.7, bot))
        fig.shape(d, s["base"], shadow=[P((cx - 5, top), (cx - 1.4, top), (cx - 1.6, bot + 1), (cx - 5, bot + 1))], sc=s["sh"])


# ----------------------------------------------------------------------------------------------- head and face
HEAD_FRONT = ("M35.5 7 C48 7 58 16.5 58 30 C58 41 54.6 51.4 47.6 57.4 C44.6 60.1 42 61.4 39.6 61.4 "
              "C36 61.4 30.5 59.8 25.5 56 C18.5 50.8 13.2 41.5 13.2 30 C13.2 16.5 23 7 35.5 7Z")
HEAD_REAR = mx(HEAD_FRONT, 35.6)
EAR_F = (15.2, 41.0)
EAR_R = (19.6, 41.5)


def draw_head(fig, ch, view):
    s = skin_tones(ch["skin"])
    fig.at(60, head=True)
    if view == "front":
        fig.shape(HEAD_FRONT, s["base"], shadow=[
            "M10 20 C14 34 19 46 31 60 L10 64Z",            # left side plane
        ], sc=s["sh"])
    else:
        fig.shape(HEAD_REAR, s["base"], shadow=["M30 0 L80 0 L80 80 L30 80Z"], sc=s["sh"])


def draw_ear(fig, ch, view, z=61):
    s = skin_tones(ch["skin"])
    fig.at(z, head=True)
    x, y = EAR_F if view == "front" else EAR_R
    fig.shape(ell(x, y, 3.0, 4.4), s["base"], shadow=[ell(x + 0.9, y + 0.3, 1.3, 2.4)], sc=s["sh"])
    if ch.get("earring"):
        kind, col = ch["earring"]
        if kind == "hoop":
            fig.line("M%s %s A3 3.4 0 1 0 %s %s" % (f(x - 1.5), f(y + 4.2), f(x + 1.2), f(y + 4.3)), col, 1.0)
        else:
            fig.shape(ell(x, y + 4.3, 1.1), col, lw=0.6)


def draw_face(fig, ch):
    s = skin_tones(ch["skin"])
    fig.at(62, head=True)
    eye = "#2e2733"
    fem = ch["build"] == "f"
    # cheeks
    fig.fill(ell(28.6, 47.4, 3.2, 2.0), s["blush"], op=0.55)
    fig.fill(ell(50.4, 47.4, 2.6, 1.9), s["blush"], op=0.55)
    # eyes
    ey = 40.6
    for x, rx in ((33.2, 2.05), (46.6, 1.85)):
        fig.fill(ell(x, ey, rx, 2.75), eye)
        fig.fill(ell(x + 0.7, ey - 1.0, 0.75), "#ffffff")
        if fem:
            fig.line("M%s %s Q%s %s %s %s" % (f(x + rx - 0.3), f(ey - 1.9), f(x + rx + 1.0), f(ey - 2.4), f(x + rx + 1.6), f(ey - 3.4)),
                     eye, 0.9)
    # brows
    bc = ch.get("brow") or shade(ch.get("hair_color") or "#3b2a20", 0.8)
    fig.line("M30.3 34.6 Q33 33.0 35.8 34.0", bc, 1.25 if not fem else 1.05)
    fig.line("M44.4 33.9 Q46.8 33.0 49.0 34.2", bc, 1.25 if not fem else 1.05)
    # nose
    fig.line("M42.6 44.4 Q43.9 46.4 42.3 47.0", s["dark"], 0.95)
    # mouth
    if ch.get("mustache"):
        pass
    fig.line("M37.4 51.2 Q40.6 53.8 44.0 51.0", s["lip"], 1.15)
    if ch.get("freckles"):
        for x, y in ((27.5, 45.2), (29.4, 46.6), (31.0, 45.4), (48.6, 45.5), (50.4, 46.4)):
            fig.fill(ell(x, y, 0.5), shade(ch["skin"], 0.72))
    if ch.get("age") == "old":
        fig.line("M24.8 41.5 Q25.6 43.4 27.2 44.0", s["dark"], 0.6, op=0.7)
        fig.line("M35.8 48.6 Q35.0 50.6 36.0 52.0", s["dark"], 0.6, op=0.6)


def draw_glasses(fig, ch, view):
    col = ch["glasses"]
    fig.at(66, head=True)
    if view == "front":
        fig.shape(rect(28.6, 37.2, 9.0, 7.0, 2.6), "#ffffff", lc=col, lw=1.05, op=None, mask=False,
                  shadow=(), hi=()) if False else None
        for x0, w in ((28.4, 9.4), (42.6, 8.2)):
            fig.fill(rect(x0, 37.0, w, 7.2, 2.6), "#ffffff", op=0.28)
            fig.line(rect(x0, 37.0, w, 7.2, 2.6), col, 1.05)
        fig.line("M37.8 39.6 Q40.2 38.6 42.6 39.6", col, 1.0)
        fig.line("M28.4 39.4 L17.6 38.2", col, 1.0)
    else:
        fig.line("M14.2 38.4 L21.2 38.8", col, 1.0)
        fig.line("M13.6 37.2 L13.2 43.2", col, 1.1)


# ----------------------------------------------------------------------------------------------- upper body
def upper(fig, ch, view, color, role="top", sleeve="long", hem=None, flare=0.0, neck="crew", sleeve_color=None,
          sleeve_role=None, cuff=None, wide=0.0, sleeve_len=None, open_front=None, z=40, details=None, neck_dip=2.2,
          shadow_w=4.2, hilite=True):
    """Torso + both arms of one garment.  sleeve: long | short | rolled | cap | none | wide."""
    b = BUILD[ch["build"]]
    s = skin_tones(ch["skin"])
    sc = sleeve_color or color
    sr_ = sleeve_role or role
    d = torso_d(b, hem=hem, flare=flare, neck_dip=neck_dip)
    x_side = b["sl"][0] + shadow_w
    shd = [P((0, 0), (x_side, 0), (x_side + (1.5 if hem else 0.5), (hem or 113) + 2), (0, (hem or 113) + 2))]
    # soft shadow under the collar / chin
    shd.append("M28 60 C33 66.5 39 66.5 45 60 L45 58 L28 58Z")
    his = []
    if hilite:
        his = ["M%s %s C%s %s %s %s %s %s L%s %s Z" % tuple(map(f, (b["nl"][0] - 1, b["nl"][1] + 0.6, b["nl"][0] - 4.5, b["nl"][1] + 1.6,
                                                                   b["sl"][0] + 3.5, b["sl"][1] - 3.6, b["sl"][0] + 2.6, b["sl"][1] - 1.2,
                                                                   b["nl"][0] + 1, b["nl"][1] + 3.6)))]
    length = sleeve_len or 104.0
    # far arm
    fig.at(z - 25)
    if sleeve not in ("none",):
        slen = {"short": 84.0, "cap": 77.0, "rolled": 95.0}.get(sleeve, length)
        draw_hand(fig, ch, b, "f", length)
        if slen < length:
            fig.shape(arm_d(b, "f", length, top_w=b["arm"] - 1.4, bot_w=b["wrist"] - 0.4), s["base"],
                      shadow=[P((0, 0), (b["sr"][0] - 0.6, 0), (b["sr"][0] - 0.6, 200), (0, 200))], sc=s["sh"])
        fig.shape(arm_d(b, "f", slen, wide=wide if sleeve == "wide" else 0), sc, role=sr_,
                  shadow=[P((0, 0), (b["sr"][0] + 0.3, 0), (b["sr"][0] + 1.2, 200), (0, 200))])
        if sleeve == "rolled":
            fig.shape(rect(b["sr"][0] - 3.0, slen - 3.6, 7.2, 3.6, 1.4), shade(sc, 0.92), role=sr_, lw=0.9)
    else:
        draw_hand(fig, ch, b, "f", length)
        fig.shape(arm_d(b, "f", length, top_w=b["arm"] - 1.4, bot_w=b["wrist"] - 0.4), s["base"],
                  shadow=[P((0, 0), (b["sr"][0] - 0.6, 0), (b["sr"][0] - 0.6, 200), (0, 200))], sc=s["sh"])
    # torso
    fig.at(z)
    fig.shape(d, color, role=role, shadow=shd, hi=his)
    if details:
        details(fig, ch, view, b)
    # near arm
    fig.at(z + 10)
    if sleeve != "none":
        slen = {"short": 84.0, "cap": 77.0, "rolled": 95.0}.get(sleeve, length)
        draw_hand(fig, ch, b, "n", length)
        if slen < length:
            fig.shape(arm_d(b, "n", length, top_w=b["arm"] - 1.4, bot_w=b["wrist"] - 0.4), s["base"],
                      shadow=[P((0, 0), (b["sl"][0] - 1.6, 0), (b["sl"][0] - 2.0, 200), (0, 200))], sc=s["sh"])
        ad = arm_d(b, "n", slen, wide=wide if sleeve == "wide" else 0)
        fig.shape(ad, sc, role=sr_, shadow=[P((0, 0), (b["sl"][0] - 1.0, 0), (b["sl"][0] - 1.8, 200), (0, 200))],
                  hi=[ell(b["sl"][0] + 0.6, b["sl"][1] - 1.6, 2.6, 1.3)])
        if sleeve == "rolled":
            fig.shape(rect(b["sl"][0] - 4.6, slen - 3.6, 8.0, 3.6, 1.4), shade(sc, 0.92), role=sr_, lw=0.9)
        if cuff:
            fig.fill(P((b["sl"][0] - 5.5, slen - 2.4), (b["sl"][0] + 4.2, slen - 2.4), (b["sl"][0] + 4.2, slen - 0.6),
                       (b["sl"][0] - 5.5, slen - 0.6)), cuff)
    else:
        draw_hand(fig, ch, b, "n", length)
        fig.shape(arm_d(b, "n", length, top_w=b["arm"] - 1.4, bot_w=b["wrist"] - 0.4), s["base"],
                  shadow=[P((0, 0), (b["sl"][0] - 1.6, 0), (b["sl"][0] - 2.0, 200), (0, 200))], sc=s["sh"])


def placket(fig, color, top=66.0, bottom=111.0, x=38.4, buttons=4):
    fig.line("M%s %s L%s %s" % (f(x), f(top), f(x + 0.3), f(bottom)), shade(color, 0.72), 0.75)
    for k in range(buttons):
        y = top + 6 + k * (bottom - top - 8) / max(1, buttons - 1)
        fig.fill(ell(x + 1.3, y, 0.65), shade(color, 0.62))


def collar(fig, color, role="top", kind="shirt", y=63.4):
    """Shirt collar points around the neck (front view)."""
    if kind == "shirt":
        fig.shape("M30.4 %s L37.4 %s L33.6 %s Z" % (f(y - 1.2), f(y + 6.2), f(y + 7.0)), color, role=role, lw=0.9,
                  hi=[], shadow=[])
        fig.shape("M42.2 %s L38.2 %s L42.8 %s Z" % (f(y - 1.2), f(y + 6.2), f(y + 6.6)), color, role=role, lw=0.9)
    elif kind == "mandarin":
        fig.shape("M30.0 %s C34 %s 39 %s 42.2 %s L42.4 %s C38.6 %s 34 %s 30.0 %s Z" % tuple(map(f, (
            y - 0.6, y + 1.2, y + 1.2, y - 0.6, y + 2.6, y + 4.2, y + 4.2, y + 2.4))), color, role=role, lw=0.9)


def tie(fig, color, y=64.0, length=96.0, x=38.8):
    d = "M%s %s L%s %s L%s %s L%s %s Z" % tuple(map(f, (x - 1.6, y + 3.4, x + 1.6, y + 3.4, x + 1.0, y + 6.4, x - 1.0, y + 6.4)))
    fig.shape(d, color, lw=0.8)
    d2 = "M%s %s L%s %s L%s %s L%s %s L%s %s Z" % tuple(map(f, (x - 1.1, y + 6.2, x + 1.1, y + 6.2, x + 2.4, length - 3,
                                                              x + 0.2, length, x - 2.0, length - 3)))
    fig.shape(d2, color, lw=0.8, hi=[P((x - 3, y + 6), (x, y + 6), (x - 0.4, length), (x - 3, length))], hc=shade(color, 1.12))


# ----------------------------------------------------------------------------------------------- hair
def hair_tones(c):
    return dict(base=c, sh=shade(c, 0.8), hi=shade(c, 1.22) if c != PAL["hair"][0] else "#4a4448")


def hshape(fig, d, c, shadow=(), hi=(), role="hair", lw=LW):
    t = hair_tones(c)
    fig.shape(d, c, role=role, shadow=shadow, hi=hi, sc=t["sh"], hc=t["hi"], lw=lw)


HI_TOP = "M21 14 C26 8.6 32 7 38.5 7.4 C33 9.4 28 12 24.4 16.4Z"


def hair_short(fig, ch, view, c, style="short"):
    if view == "front":
        fig.at(64, head=True)
        if style == "short":
            d = ("M14.2 38.6 C11.2 30 11.6 19 19.6 11.4 C25 6.4 31 4.4 37 4.4 C46 4.4 54 9 58 17 C59.7 20.6 60.1 26 58.6 31.6 "
                 "C57.6 27.2 55.4 23.6 51.8 21.2 C45.4 17.2 35.6 18.8 28.6 23.4 C24.2 26.6 21.6 31.6 21.4 37.6 L18.4 38.6Z")
        elif style == "side":
            d = ("M14.2 38.6 C11 30 11.4 18.6 19.4 11 C25 6 31.4 4 37.6 4 C47 4 55 9.4 58.4 18 C59.6 21.6 59.8 26.4 58.6 31.4 "
                 "C57.6 26 54.6 21.6 49 19.4 C43 17.4 34.6 17.6 29.6 20 L27.2 21.2 C24 24 21.6 30 21.4 37.4 L18.4 38.6Z")
        else:  # crop: close to the skull
            d = ("M14.6 37.6 C12.4 30 12.8 19.4 20.2 12.4 C25.4 7.6 31 6 36.6 6 C45.6 6 53.6 10.4 57 17.8 C58.4 21.2 58.6 25.6 57.8 29.6 "
                 "C56.6 26 54 23 50.8 21.6 C45 19.4 36 20.4 29.2 23.4 C24.6 25.6 22 30.6 21.6 36.6 L18.4 37.4Z")
        hshape(fig, d, c, shadow=["M8 22 C12 30 16 34 22 36 L22 44 L8 44Z", "M28 23 C36 19.6 46 19.4 52 22 L56 30 L56 26 C52 20 40 18 28 23Z"],
               hi=[HI_TOP])
        if style == "side":
            fig.line("M29.6 20.2 C28 15 29.6 10 33 6.6", hair_tones(c)["sh"], 0.8)
    else:
        fig.at(64, head=True)
        top = 4.4 if style != "crop" else 6.0
        d = ("M15.6 39.6 C11.6 30.6 12.4 18 20.4 11 C26 6.4 31.4 %s 37 %s C47 %s 55.6 10 58.6 20 C60.6 27.6 59.6 37 56 45 "
             "C53 51 48 54.4 42.6 55 C38 55.4 33 54.6 29.6 53 C26 51.4 23.6 47.6 22.8 43.6 C22.2 40.2 21 38.4 18.6 38.2Z" % (
                 f(top), f(top), f(top)))
        hshape(fig, d, c, shadow=["M8 30 C14 40 18 46 24 54 L8 60Z", "M30 51 C38 54 46 53 54 47 L58 56 L28 56Z"],
               hi=["M26 10.6 C32 6.6 40 6.2 46 8.6 C40 8.6 33 9.6 28.4 12.6Z"])
        fig.line("M40 20 C44 26 48 34 49 42", hair_tones(c)["sh"], 0.8, op=0.8)


def hair_long(fig, ch, view, c, length=98.0, bangs="curtain", wave=False):
    t = hair_tones(c)
    if view == "front":
        # back mass behind head and shoulders
        fig.at(8, head=True)
        L = length
        if wave:
            back = bumps([(12.6, 30), (11.0, 48), (12.4, 64), (11.4, 80), (13.6, L - 4)], amp=-1.2)
            back = ("M36 4 C22 4 10.6 14 10.6 30 " + back[back.index("Q"):] +
                    " C20 %s 30 %s 40 %s C48 %s 56 %s 60 %s " % tuple(map(f, (L + 1.5, L + 3, L + 3, L + 2.4, L + 1.4, L - 4))) +
                    bumps([(60, L - 4), (61.6, 80), (60.2, 64), (61.4, 48), (60.6, 30)], amp=-1.2)[len("M60 %s" % f(L - 4)):] +
                    " C60.6 14 50 4 36 4Z")
        else:
            back = ("M36 4 C22 4 10.6 14 10.6 30 C10.6 52 11.6 %s 13.4 %s C22 %s 50 %s 59 %s C60.8 %s 61.6 52 61.4 30 "
                    "C61.4 14 50 4 36 4Z" % tuple(map(f, (L - 20, L - 2, L + 2.6, L + 2.6, L - 2, L - 20))))
        hshape(fig, back, c, shadow=[P((0, 0), (72, 0), (72, 200), (0, 200))])
        # cap and face-framing locks
        fig.at(64, head=True)
        if bangs == "curtain":
            d = ("M13.6 56 C10.6 42 10.8 22 19.4 12 C25 6 31.4 4 37.4 4 C47.6 4 55.6 10 58.8 19.6 C60.8 26 61.2 36 60.6 46 "
                 "L60.2 62 C58.8 64.2 56.6 64.2 55.6 62 L56.2 44 C56.4 34 55.4 27.6 52 23.6 C49.4 21 46 20 43.4 19.6 "
                 "C40.6 22 36 24.6 30.6 26 C25.4 27.6 22.4 32 21.6 39 L21.2 52 C19.8 56 16 57.6 13.6 56Z")
            shd = ["M8 30 L22 34 L22 60 L8 60Z", "M43.4 19.6 C47 21 51 22.6 53 25 L56.4 34 L56.6 62 L54 62 L54 30Z"]
        elif bangs == "straight":
            d = ("M13.2 58 C10 42 10.6 22 19.4 12 C25 6 31.4 4 37.4 4 C47.6 4 55.6 10 58.8 19.6 C60.8 26 61.2 36 60.8 46 "
                 "L60.6 60 C59 62 56.6 62 55.8 60 L56 36 L56 28.4 C49 29.6 40 29.6 30 28.6 L24.6 28 C22.4 32 21.6 38 21.4 44 "
                 "L21 54 C19.4 58 15.6 59.6 13.2 58Z")
            shd = ["M8 30 L21.8 34 L21.8 62 L8 62Z", "M24 26 L57 26 L57 29.4 L24 29.4Z"]
        else:  # side part sweeping right
            d = ("M13.6 56 C10.6 42 10.8 22 19.4 12 C25 6 31.4 4 37.4 4 C47.6 4 55.6 10 58.8 19.6 C60.8 26 61.2 36 60.6 46 "
                 "L60.2 62 C58.8 64.2 56.6 64.2 55.6 62 L56.2 44 C56.4 36 55 30 52.6 27 C46 24 38 21.6 30 22.6 "
                 "C25.4 25 22.4 31 21.6 39 L21.2 52 C19.8 56 16 57.6 13.6 56Z")
            shd = ["M8 30 L22 34 L22 60 L8 60Z"]
        hshape(fig, d, c, shadow=shd, hi=[HI_TOP])
    else:
        fig.at(80, head=True)
        L = length
        if wave:
            d = ("M36 4 C22 4 11 14 11 30 C10.4 40 12.4 46 12.6 50 " +
                 bumps([(12.6, 50), (11.4, 66), (12.8, 82), (13.6, L - 2)], amp=-1.2)[len("M12.6 50"):] +
                 " C24 %s 48 %s 58.6 %s " % (f(L + 3), f(L + 3), f(L - 2)) +
                 bumps([(58.6, L - 2), (60, 82), (59, 66), (60.2, 50)], amp=-1.2)[len("M58.6 %s" % f(L - 2)):] +
                 " C60.8 42 61.4 36 61 30 C61 14 50 4 36 4Z")
        else:
            d = ("M36 4 C22 4 11 14 11 30 C10.6 50 12 %s 13.6 %s C24 %s 48 %s 58.6 %s C60.4 %s 61.4 50 61 30 "
                 "C61 14 50 4 36 4Z" % tuple(map(f, (L - 20, L - 2, L + 2.8, L + 2.8, L - 2, L - 20))))
        hshape(fig, d, c, shadow=["M0 0 L20 0 C16 30 16 70 22 120 L0 120Z", "M0 %s L72 %s L72 130 L0 130Z" % (f(L - 6), f(L - 6))],
               hi=["M25 10 C31 6.2 40 6 46 8.6 C40 8.8 32 10 27.4 12.8Z"])
        fig.line("M38 14 C42 30 44 60 45 %s" % f(L - 8), t["sh"], 0.8, op=0.7)
        fig.line("M28 18 C26 36 26 64 28 %s" % f(L - 10), t["sh"], 0.8, op=0.6)


# ----------------------------------------------------------------------------------------------- headwear
def headwear_ghutra(fig, ch, view, cloth=None, pattern=None):
    """Gulf ghutra (white) or shemagh (red-and-white checks) with the black double-cord agal."""
    c = cloth or PAL["thobe"]
    sh = "#dde2ea"
    lc = "#8f97a6"
    fill = c
    if pattern:
        pid = "shm%s" % view
        fig.defs.append('<pattern id="%s" width="3.2" height="3.2" patternUnits="userSpaceOnUse" patternTransform="rotate(8)">'
                        '<rect width="3.2" height="3.2" fill="%s"/><rect width="1.7" height="1.7" fill="%s"/>'
                        '<rect x="1.6" y="1.6" width="0.9" height="0.9" fill="%s"/></pattern>' % (pid, c, pattern, pattern))
        fill = "url(#%s)" % pid
        sh = shade(pattern, 0.6)
    agal = PAL["agal"]
    if view == "front":
        # cloth falling behind the shoulders (left) and in front of the right shoulder
        fig.at(9, head=False)
        back = "M9.6 26 C7.6 50 9 78 12.4 104 L24 104 L22 60 Z"
        fig.shape(back, fill, lc=lc, sc=sh, shadow=["M0 0 L72 0 L72 200 L0 200Z"] if not pattern else [], mfill=None)
        fig.at(64, head=True)
        d = ("M41 1.6 C50 2.6 57 7.6 59.6 15 C61.6 21 61.6 32 60.6 44 L59.6 62 L57.4 74 L52.6 73 L54.2 58 "
             "C55.4 48 56.6 36 55.4 28 C54.6 23 51 20.4 46 19.8 C40 19.2 33 19.8 28 21.4 C24.6 22.6 22.4 26.4 21.6 32 "
             "L20.6 46 C20 52 19.6 58 20.2 64 L13.6 66 C10 54 9 40 10.2 28 C11.4 16 18 8.6 27 5 C31 3.4 36 2 41 1.6Z")
        fig.shape(d, fill, lc=lc, sc=sh, hc="#ffffff",
                  shadow=["M8 24 C14 30 18 40 20 64 L8 66Z", "M28 21.4 C36 19.4 46 19.4 52 21.4 L52 23.4 C46 21.6 36 21.4 28 23.4Z"]
                  if not pattern else [])
        if pattern:  # shemagh border band near the face edge
            fig.line("M21.6 32 C22.4 26.4 24.6 22.6 28 21.4 C33 19.8 40 19.2 46 19.8 C51 20.4 54.6 23 55.4 28", pattern, 1.4, op=0.9)
        # folds
        fig.line("M14 30 C14 44 15 56 17 64", lc if not pattern else shade(pattern, 0.55), 0.7, op=0.7)
        fig.line("M58.4 30 C58.6 44 57.8 58 56 72", lc if not pattern else shade(pattern, 0.55), 0.7, op=0.7)
        # agal: two cords around the crown
        for dy, w in ((0, 2.2), (3.4, 2.2)):
            fig.line("M11.2 %s C16 %s 28 %s 40 %s C49 %s 56.4 %s 60.6 %s" % tuple(map(f, (
                12.4 + dy, 15.2 + dy, 17.6 + dy, 17.4 + dy, 17.2 + dy, 14.6 + dy, 12.0 + dy))), agal, w, role="o", cap="round")
        fig.line("M12 12.6 C16.4 15.1 28 17.3 40 17.1", "#4a4a55", 0.6)
    else:
        fig.at(64, head=True)
        d = ("M36 1.8 C24 1.8 13.6 8 10.6 20 C8.4 30 9.2 44 11.6 56 L60.4 56 C62.4 44 62.8 30 60.8 20 C58 8.6 48 1.8 36 1.8Z")
        fig.shape(d, fill, lc=lc, sc=sh, shadow=["M0 0 L22 0 C18 20 18 40 20 60 L0 60Z"] if not pattern else [])
        fig.at(80, head=False)
        tail = "M11.4 50 C11 70 14 90 20 104 C30 110 44 110 54 104 C58.6 90 61 70 60.6 50Z"
        fig.shape(tail, fill, lc=lc, sc=sh, shadow=["M0 0 L24 0 C22 40 26 80 30 120 L0 120Z"] if not pattern else [])
        fig.line("M36 56 C36 72 36 90 35 108", lc if not pattern else shade(pattern, 0.55), 0.7, op=0.7)
        fig.line("M24 56 C23 72 24 90 26 106", lc if not pattern else shade(pattern, 0.55), 0.7, op=0.6)
        fig.at(81, head=True)
        for dy in (0, 3.4):
            fig.line("M10.8 %s C16 %s 28 %s 38 %s C48 %s 56 %s 61 %s" % tuple(map(f, (
                13.6 + dy, 16.6 + dy, 18.4 + dy, 18.2 + dy, 17.8 + dy, 16 + dy, 13.4 + dy))), agal, 2.2, role="o")


def headwear_hijab(fig, ch, view, c, drape=88.0, pin=None):
    """Wrapped hijab framing the face and covering neck and shoulders."""
    if view == "front":
        fig.at(9, head=True)
        fig.shape("M10 30 C9 46 11 60 16 70 L40 70 L40 20Z", c, shadow=["M0 0 L72 0 L72 200 L0 200Z"])
        fig.at(64, head=True)
        outer = ("M41 66.6 C50 66.6 57.4 61.4 60.4 52 C63 42 63.2 26 58.4 16 C54 7.4 45.4 3.4 36.4 3.4 C24.4 3.4 12.8 10.8 10.6 25 "
                 "C9 36 11 50 17.6 60 C22.8 66 31.6 67.2 41 66.6Z")
        inner = ("M39.6 62.2 C45.4 62.2 51.4 57.2 54.4 50 C56.4 44 56.8 36 55.8 29 C54.8 22.6 50.4 19.4 43.4 19 "
                 "C36.4 18.8 29.6 20.6 26.6 25 C24 29 23.8 38 25.2 45 C27 53 32.6 62.2 39.6 62.2Z")
        sc = shade(c, SHADOW)
        fig.shape(outer + " " + inner, c, shadow=["M8 20 C14 32 18 46 24 62 L8 70Z"], hi=[HI_TOP], sc=sc)
        fig.line(inner, shade(c, OUTLINE), LW)
        fig.line("M26.6 25.6 C30 21.4 37 20 44 20.4", shade(c, 0.78), 0.8)
        fig.at(78, head=False)
        dr = ("M17 60 C22 67.6 31 70.4 41 69.6 C49 69 55.6 65.4 59.6 58.6 C61.6 66 61 74 57.6 80 C52 %s 44 %s 37 %s "
              "C29 %s 21 %s 17.4 82 C14.6 76 14.6 68 17 60Z" % tuple(map(f, (drape - 1, drape + 1, drape + 1, drape, drape - 3))))
        fig.shape(dr, c, shadow=["M0 0 L25 0 L27 100 L0 100Z"], sc=shade(c, SHADOW))
        fig.line("M24 72 C30 78 40 80 50 76", shade(c, 0.74), 0.8, op=0.9)
        if pin:
            fig.shape(ell(55.6, 60.6, 1.2), pin, lw=0.6)
    else:
        fig.at(64, head=True)
        d = ("M36 3.4 C23 3.4 12.6 11 10.6 24 C9 36 10.6 50 14.4 60 L58 60 C61.4 50 63 36 61.4 24 C59.4 11 49 3.4 36 3.4Z")
        fig.shape(d, c, shadow=["M0 0 L21 0 C17 20 17 44 20 64 L0 64Z"], hi=["M26 9.6 C32 6.4 40 6 46 8.2 C40 8.6 32 9.8 28 12Z"])
        fig.at(80, head=False)
        dr = "M13.4 52 C11.6 64 13 78 18 %s C28 %s 46 %s 55 %s C60 78 61 64 59 52Z" % tuple(map(f, (drape + 4, drape + 8, drape + 8, drape + 4)))
        fig.shape(dr, c, shadow=["M0 0 L23 0 C21 40 23 80 26 120 L0 120Z"])
        fig.line("M30 60 C30 72 31 84 32 %s" % f(drape + 4), shade(c, 0.74), 0.8, op=0.8)


# ----------------------------------------------------------------------------------------------- assembly
def draw(ch, view):
    fig = Fig(view)
    b = BUILD[ch["build"]]
    ch.setdefault("hair_color", (ch.get("hair") or (None, None))[1])
    # legs and feet
    bot = ch.get("bottom")
    if bot:
        kind, col = bot[0], bot[1]
        opts = bot[2] if len(bot) > 2 else {}
        if kind == "trousers":
            trousers(fig, ch, view, col, **opts)
        elif kind == "legs":
            bare_legs(fig, ch, view, **opts)
        elif callable(kind):
            kind(fig, ch, view, col, **opts)
    sh = ch.get("shoes", ("shoe", PAL["shoe"]))
    if sh:
        shoes(fig, ch, view, sh[0], sh[1])
    # upper body
    top = ch["top"]
    top(fig, ch, view)
    draw_neck(fig, ch, view)
    draw_head(fig, ch, view)
    hw = ch.get("headwear")
    hr = ch.get("hair")
    ear = ch.get("ear", "over")
    if hr:
        style, col = hr[0], hr[1]
        opts = hr[2] if len(hr) > 2 else {}
        style(fig, ch, view, col, **opts)
    if view == "front":
        draw_face(fig, ch)
    if ear != "hidden" and not hw:
        draw_ear(fig, ch, view, z=65 if ear == "over" else 61)
    for fn in ch.get("extras", []):
        fn(fig, ch, view)
    if hw:
        hw(fig, ch, view)
    if ch.get("glasses"):
        draw_glasses(fig, ch, view)
    return fig


def render(svgdir, pngdir):
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NODE_PATH=root)
    subprocess.run(["node", os.path.join(HERE, "render.cjs"), svgdir, pngdir], check=True, env=env)


def write_svgs(chars, svgdir, scales):
    if os.path.isdir(svgdir):
        shutil.rmtree(svgdir)
    os.makedirs(svgdir)
    for ch in chars:
        for view in ("front", "rear"):
            fig = draw(dict(ch), view)
            s = scales.get(ch["id"], 1.0)
            for which in ("color", "mask"):
                with open(os.path.join(svgdir, "%s__%s__%s.svg" % (ch["id"], view, which)), "w") as fh:
                    fh.write(fig.svg(which, s))


def top_row(png):
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(png).convert("RGBA"))[..., 3]
    rows = np.where(a.max(1) > 64)[0]
    return int(rows[0]) if len(rows) else 0


def build(chars, work, sheets=True, clean=True):
    from PIL import Image, ImageOps
    import numpy as np
    svgdir, pngdir = os.path.join(work, "svg"), os.path.join(work, "png")
    # pass 1: natural size, measure each figure's top; pass 2: scale the head group so the top reaches the top rows
    write_svgs(chars, svgdir, {})
    render(svgdir, pngdir)
    py = PIVOT[1]
    scales = {}
    for ch in chars:
        t = min(top_row(os.path.join(pngdir, "%s__%s__color.png" % (ch["id"], v))) for v in ("front", "rear"))
        s = (py - 0.6) / (py - t + 0.4) if t != 0 else 1.0
        scales[ch["id"]] = max(0.84, min(1.12, s))
    write_svgs(chars, svgdir, scales)
    render(svgdir, pngdir)
    os.makedirs(CHARS, exist_ok=True); os.makedirs(MASKS, exist_ok=True)
    report = []
    for ch in chars:
        for view, names in (("front", ("front-left", "front-right")), ("rear", ("rear-right", "rear-left"))):
            col = Image.open(os.path.join(pngdir, "%s__%s__color.png" % (ch["id"], view))).convert("RGBA")
            msk = np.array(Image.open(os.path.join(pngdir, "%s__%s__mask.png" % (ch["id"], view))).convert("RGBA")).astype(int)
            idx = np.full(msk.shape[:2], 3, np.uint8)            # 3 = transparent
            on = msk[..., 3] >= 96
            red = on & (msk[..., 0] > 127) & (msk[..., 0] >= msk[..., 1])
            grn = on & (msk[..., 1] > 127) & ~red
            idx[on] = 0; idx[red] = 1; idx[grn] = 2
            m = Image.fromarray(idx, "P")
            m.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 0] + [0] * (256 * 3 - 12))
            m.info["transparency"] = 3
            for k, name in enumerate(names):
                c = col if k == 0 else ImageOps.mirror(col)
                mm = m if k == 0 else ImageOps.mirror(m)
                out = os.path.join(CHARS, "%s-%s.webp" % (ch["id"], name))
                save_webp(c, out)
                mp = os.path.join(MASKS, "%s-%s.png" % (ch["id"], name))
                mm.save(mp, optimize=True, transparency=3)
            report.append((ch["id"], view, scales[ch["id"]], bool(red.any()), bool(grn.any())))
    return scales, report


def save_webp(im, out):
    import io
    import numpy as np
    from PIL import Image
    a = io.BytesIO(); im.save(a, "WEBP", lossless=True, quality=100, method=6)
    b = io.BytesIO(); im.save(b, "WEBP", quality=90, method=6, alpha_quality=100)
    best = a
    if b.tell() < a.tell() * 0.85:
        x = np.array(im).astype(float)
        y = np.array(Image.open(io.BytesIO(b.getvalue())).convert("RGBA")).astype(float)
        vis = x[..., 3] > 0
        err = np.abs(x[..., :3] - y[..., :3])[vis]
        if err.size and np.percentile(err, 99.5) < 14:
            best = b
    with open(out, "wb") as fh:
        fh.write(best.getvalue())
