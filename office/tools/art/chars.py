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
from style import PAL, PEOPLE, shade, OUTLINE, HILITE  # noqa: E402

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
# One skeleton for everyone: the waist / seat line sits at y=112, feet on the bottom rows.  In both base views the
# broad face of the body (chest or back) faces down-right and the narrow side plane faces down-left, so the side plane
# on the screen-left is the shaded one (STYLE.md: left-front x0.72, right-front x0.86).
BUILD = {
    "m": dict(nl=(30.4, 62.6), nr=(41.6, 62.6), sl=(17.4, 70.2), sr=(54.6, 70.2), wl=(20.8, 113.0), wr=(51.2, 113.0),
              arm=10.0, wrist=8.4, hand=3.9, leg_n=(21.0, 37.2, 23.4, 36.0), leg_f=(35.6, 51.0, 37.6, 49.4)),
    "f": dict(nl=(31.2, 63.0), nr=(40.8, 63.0), sl=(19.8, 70.6), sr=(52.2, 70.6), wl=(23.6, 102.5), wr=(48.4, 102.5),
              hl=(21.8, 114.0), hr=(50.2, 114.0),
              arm=8.6, wrist=7.0, hand=3.5, leg_n=(22.8, 37.0, 25.2, 35.4), leg_f=(35.6, 49.2, 37.8, 47.6)),
}
BUILD["b"] = dict(BUILD["m"], sl=(15.8, 70.2), sr=(56.2, 70.2), wl=(19.2, 113.0), wr=(52.8, 113.0), arm=11.0, wrist=9.2,
                  hand=4.2, leg_n=(20.0, 37.4, 22.6, 36.2), leg_f=(35.6, 52.2, 37.8, 50.4))
ANK_N, ANK_F = 191.0, 188.0      # ankle line of the near and far leg
FOOT_N, FOOT_F = 199.6, 196.6    # sole line of the near and far foot
FRONT_X = 38.8                   # chest centre line in the front view (the body is turned to screen right)


def torso_d(b, hem=None, flare=0.0, neck_dip=2.2, hem_curve=1.2):
    """Torso outline.  hem: y of the bottom (default waist or hip); flare: extra width at the hem (robes, tunics)."""
    nl, nr, sl, sr = b["nl"], b["nr"], b["sl"], b["sr"]
    wl, wr = b["wl"], b["wr"]
    d = "M%s %s C%s %s %s %s %s %s " % tuple(map(f, (nl[0], nl[1], nl[0] - 4.5, nl[1] + 1.3, sl[0] + 1.5, sl[1] - 4.8, sl[0], sl[1])))
    if "hl" in b:
        hl, hr = b["hl"], b["hr"]
        bot = hem or hl[1]
        d += "C%s %s %s %s %s %s " % tuple(map(f, (sl[0] - 0.8, sl[1] + 6, wl[0] - 1.4, wl[1] - 14, wl[0], wl[1])))
        if bot > hl[1] + 2:
            d += "C%s %s %s %s %s %s L%s %s " % tuple(map(f, (wl[0] - 0.6, wl[1] + 4, hl[0], hl[1] - 5, hl[0], hl[1], hl[0] - flare, bot)))
            d += "Q%s %s %s %s L%s %s " % tuple(map(f, ((hl[0] + hr[0]) / 2, bot + hem_curve, hr[0] + flare, bot, hr[0], hr[1])))
        else:
            d += "C%s %s %s %s %s %s " % tuple(map(f, (wl[0] - 0.6, wl[1] + 4, hl[0], hl[1] - 5, hl[0] - flare, bot)))
            d += "Q%s %s %s %s " % tuple(map(f, ((hl[0] + hr[0]) / 2, bot + hem_curve, hr[0] + flare, bot)))
        d += "C%s %s %s %s %s %s " % tuple(map(f, (hr[0], hr[1] - 5, wr[0] + 0.6, wr[1] + 4, wr[0], wr[1])))
        d += "C%s %s %s %s %s %s " % tuple(map(f, (wr[0] + 1.4, wr[1] - 14, sr[0] + 0.8, sr[1] + 6, sr[0], sr[1])))
    else:
        bot = hem or wl[1]
        if bot > wl[1] + 2:
            d += "C%s %s %s %s %s %s L%s %s " % tuple(map(f, (sl[0] - 0.8, sl[1] + 4, wl[0] - 1.6, wl[1] - 25, wl[0], wl[1], wl[0] - flare, bot)))
            d += "Q%s %s %s %s L%s %s " % tuple(map(f, ((wl[0] + wr[0]) / 2, bot + hem_curve, wr[0] + flare, bot, wr[0], wr[1])))
        else:
            d += "C%s %s %s %s %s %s " % tuple(map(f, (sl[0] - 0.8, sl[1] + 4, wl[0] - 1.6, wl[1] - 25, wl[0] - flare, bot)))
            d += "Q%s %s %s %s " % tuple(map(f, ((wl[0] + wr[0]) / 2, bot + hem_curve, wr[0] + flare, bot)))
        d += "C%s %s %s %s %s %s " % tuple(map(f, (wr[0] + 1.6, wr[1] - 25, sr[0] + 0.8, sr[1] + 4, sr[0], sr[1])))
    d += "C%s %s %s %s %s %s " % tuple(map(f, (sr[0] - 1.5, sr[1] - 4.8, nr[0] + 4.5, nr[1] + 1.3, nr[0], nr[1])))
    d += "C%s %s %s %s %s %sZ" % tuple(map(f, (nr[0] - 3, nr[1] + neck_dip, nl[0] + 3, nl[1] + neck_dip, nl[0], nl[1])))
    return d


def arm_geo(b, side):
    if side == "n":
        return b["sl"][0], b["sl"][1] + 1.6, -0.9
    return b["sr"][0] + 0.2, b["sr"][1] + 1.6, 0.9


def arm_d(b, side, length=104.0, top_w=None, bot_w=None, wide=0.0):
    """Arm or sleeve: a rounded column hanging from the shoulder.  side 'n' = near (screen-left), 'f' = far."""
    tw = top_w or b["arm"]
    bw = bot_w or b["wrist"]
    cx, cy, lean = arm_geo(b, side)
    bx = cx + lean
    l0, r0 = cx - tw / 2, cx + tw / 2
    l1, r1 = bx - bw / 2 - wide, bx + bw / 2 + wide
    top = cy - tw / 2 - 0.4
    return ("M%s %s C%s %s %s %s %s %s L%s %s Q%s %s %s %s L%s %s Q%s %s %s %s L%s %s C%s %s %s %s %s %sZ" % tuple(map(f, (
        cx, top, cx + tw * 0.44, top, r0, cy - tw * 0.2, r0, cy + 1.5,
        r1, length - 1.4, r1, length, r1 - 1.4, length, l1 + 1.4, length, l1, length, l1, length - 1.4,
        l0, cy + 1.5, l0, cy - tw * 0.2, cx - tw * 0.44, top, cx, top))))


def hand_xy(b, side, length=104.0):
    cx, cy, lean = arm_geo(b, side)
    return cx + lean * 1.1, length + b["hand"] - 0.6


def legs_geo(b, side):
    x0, x1, a0, a1 = b["leg_n"] if side == "n" else b["leg_f"]
    return x0, x1, a0, a1, (ANK_N if side == "n" else ANK_F)


# ----------------------------------------------------------------------------------------------- skin, hands, legs, feet
def skin_tones(c):
    return dict(base=c, sh=shade(c, 0.88), line=shade(c, OUTLINE), blush=mix(c, "#ff6f7d", 0.42),
                lip=mix(shade(c, 0.6), "#b2434f", 0.45), dark=shade(c, 0.74))


def draw_neck(fig, ch, view):
    s = skin_tones(ch["skin"])
    fig.at(35)
    d = P((31.6, 52), (40.4, 52), (40.8, 66.5), (31.2, 66.5))
    fig.shape(d, s["base"], shadow=[P((30, 50), (43, 50), (43, 59), (30, 61)) if view == "front"
                                    else P((30, 50), (34.2, 50), (34.2, 68), (30, 68))], sc=s["sh"])


def draw_hand(fig, ch, side, length=104.0):
    b = BUILD[ch["build"]]
    s = skin_tones(ch["skin"])
    x, y = hand_xy(b, side, length)
    r = b["hand"] - (0.3 if side == "f" else 0)
    fig.shape(ell(x, y, r, r * 1.06), s["base"], shadow=[P((x - 9, y - 9), (x - 0.8, y - 9), (x - 1.8, y + 9), (x - 9, y + 9))],
              sc=s["sh"])


def draw_bare_arm(fig, ch, side, length=104.0):
    b = BUILD[ch["build"]]
    s = skin_tones(ch["skin"])
    cx = arm_geo(b, side)[0]
    fig.shape(arm_d(b, side, length, top_w=b["arm"] - 1.6, bot_w=b["wrist"] - 0.8), s["base"],
              shadow=[P((0, 0), (cx - 1.6, 0), (cx - 2.2, 200), (0, 200))], sc=s["sh"])


def shoes(fig, ch, view, kind="shoe", color=None, z=21):
    """Near foot on the bottom row, far foot 3 px higher; toes point screen-right in front, screen-left in rear."""
    b = BUILD[ch["build"]]
    c = color or PAL["shoe"]
    s = skin_tones(ch["skin"])
    small = ch["build"] == "f"
    for side in ("f", "n"):
        fig.at(z + (0.5 if side == "n" else 0))
        x0_, x1_, a0, a1, ank = legs_geo(b, side)
        bot = FOOT_N if side == "n" else FOOT_F
        cx = (a0 + a1) / 2
        ht = 8.6 if not small else 7.6
        ln = 6.4 if not small else 5.0
        if kind in ("sandal", "babouche", "flat"):
            ht -= 2.2
        x0 = a0 - 1.0
        top = bot - ht
        toe = a1 + ln
        d = ("M%s %s Q%s %s %s %s L%s %s C%s %s %s %s %s %s C%s %s %s %s %s %s L%s %s Q%s %s %s %sZ" % tuple(map(f, (
            x0, top + 1.2, x0, top, x0 + 1.2, top, a1 - 0.6, top, a1 + 3.4, top, toe, top + ht * 0.36, toe, bot - 2.6,
            toe + 0.2, bot - 0.6, toe - 1.2, bot, toe - 3.0, bot, x0 + 1.4, bot, x0, bot, x0, bot - 1.4))))
        flip = (lambda p: mx(p, cx)) if view == "rear" else (lambda p: p)
        tx = (lambda x: 2 * cx - x) if view == "rear" else (lambda x: x)
        if kind == "sandal":
            fig.shape(flip(d), s["base"], shadow=[flip(P((0, bot - 1.6), (72, bot - 1.6), (72, 201), (0, 201)))], sc=c,
                      lc=shade(c, 0.6))
            fig.fill(flip(P((x0 + 0.6, top + 2.2), (a1 + 2.4, top + 2.2), (a1 + 3.2, top + 4.4), (x0 + 0.6, top + 4.4))), c)
        elif kind == "sneaker":
            fig.shape(flip(d), c, shadow=[flip(P((0, bot - 2.4), (72, bot - 2.4), (72, 201), (0, 201)))], sc="#f4f2ee",
                      lc=shade(c, 0.58), hi=[])
            fig.line(flip("M%s %s L%s %s" % (f(x0 + 0.6), f(bot - 2.4), f(toe - 0.4), f(bot - 2.4))), shade(c, 0.62), 0.7)
            fig.line(flip("M%s %s L%s %s" % (f(a1 - 1), f(top + 2.6), f(a1 + 2.6), f(top + 4.2))), shade(c, 0.5), 0.8)
        else:
            sole = shade(c, 0.72)
            fig.shape(flip(d), c, shadow=[flip(P((0, bot - 1.6), (72, bot - 1.6), (72, 201), (0, 201)))], sc=sole,
                      hi=[ell(tx(toe - 3.2), top + 2.4, 1.9, 1.0)], hc=shade(c, 1.3))


def trousers(fig, ch, view, color, top=110.0, wide=0.0, gather=False, cuff=None, seam=False, crease=True, hem=0.0):
    b = BUILD[ch["build"]]
    sh = shade(color, SHADOW)
    for side in ("f", "n"):
        fig.at(20 if side == "n" else 19)
        x0, x1, a0, a1, ank = legs_geo(b, side)
        ank += hem
        a0 -= wide; a1 += wide
        if gather:   # shalwar: full leg gathered into a cuff at the ankle
            d = ("M%s %s L%s %s C%s %s %s %s %s %s L%s %s C%s %s %s %s %s %sZ" % tuple(map(f, (
                x0, top, x1, top, x1 + 2.6, top + 40, a1 + 3.2, ank - 14, a1 + 0.6, ank - 2.4, a0 - 0.6, ank - 2.4,
                a0 - 3.4, ank - 14, x0 - 2.4, top + 40, x0, top))))
        else:
            d = P((x0, top), (x1, top), (a1, ank), (a0, ank))
        shd = [P((x0 - 6, top), (x0 + 3.4, top), (a0 + 2.8, ank + 1), (a0 - 6, ank + 1))]
        if side == "f":
            shd.append(P((x0 - 2, top), (x1 + 4, top), (x1 + 4, top + 10), (x0 - 2, top + 13)))
        fig.shape(d, color, shadow=shd, sc=sh)
        if gather:
            fig.shape(rect(a0 - 0.4, ank - 3.0, a1 - a0 + 0.8, 3.0, 1.0), shade(color, 0.92), lw=0.8)
        if cuff:
            fig.fill(P((a0, ank - 2.4), (a1, ank - 2.4), (a1, ank), (a0, ank)), shade(color, 0.8))
        if seam and side == "n":
            fig.line("M%s %s L%s %s" % (f(x1 - 3.4), f(top + 14), f(a1 - 2.8), f(ank - 1)), shade(color, 1.18), 0.6, op=0.8)
    if crease:
        fig.line("M36.6 %s L36.4 %s" % (f(top + 4), f(top + 11)), shade(color, 0.66), 0.7)


def bare_legs(fig, ch, view, top=140.0, color=None):
    """Lower legs below a skirt.  color: tights."""
    b = BUILD[ch["build"]]
    s = skin_tones(ch["skin"])
    c = color or s["base"]
    for side in ("f", "n"):
        fig.at(20 if side == "n" else 19)
        x0, x1, a0, a1, ank = legs_geo(b, side)
        cx = (a0 + a1) / 2
        bot = ank + 2.4
        d = P((cx - 4.2, top), (cx + 4.2, top), (cx + 3.2, bot), (cx - 3.2, bot))
        fig.shape(d, c, shadow=[P((cx - 6, top), (cx - 1.6, top), (cx - 1.4, bot + 1), (cx - 6, bot + 1))],
                  sc=shade(c, 0.86 if color else 0.88))


def skirt(fig, ch, view, color, hem=150.0, flare=4.0, top=100.0, pleats=0, role="o", z=30, pattern=None):
    b = BUILD[ch["build"]]
    fig.at(z)
    l, r = (b["hl"][0], b["hr"][0]) if "hl" in b else (b["wl"][0], b["wr"][0])
    d = ("M%s %s L%s %s L%s %s Q%s %s %s %s Z" % tuple(map(f, (
        l + 0.6, top, r - 0.6, top, r + flare, hem, (l + r) / 2, hem + 2.6, l - flare, hem))))
    fig.shape(d, color, role=role, shadow=[P((0, 0), (l + 3.8, 0), (l - flare + 5.2, 200), (0, 200))])
    if pattern:
        pattern(fig, d)
    for k in range(pleats):
        x = lerp(l + 5, r - 4, (k + 0.5) / pleats)
        xb = lerp(l - flare + 5, r + flare - 4, (k + 0.5) / pleats)
        fig.line("M%s %s L%s %s" % (f(x), f(top + 10), f(xb), f(hem)), shade(color, 0.76), 0.7)


def belt(fig, color, y=110.4, buckle="#d8c48a", x0=None, x1=None, b=None):
    x0 = x0 if x0 is not None else (b["wl"][0] - 0.6 if b else 20)
    x1 = x1 if x1 is not None else (b["wr"][0] + 0.6 if b else 52)
    fig.shape(P((x0, y), (x1, y), (x1, y + 2.8), (x0, y + 2.8)), color, lw=0.8)
    if buckle:
        fig.shape(rect(FRONT_X - 1.6, y - 0.3, 3.4, 3.4, 0.6), buckle, lw=0.7)


# ----------------------------------------------------------------------------------------------- head and face
HEAD_FRONT = ("M35.6 6.6 C48.4 6.6 58.6 16.4 58.6 30 C58.6 41.2 55 51.6 47.8 57.6 C44.8 60.3 42.2 61.6 39.8 61.6 "
              "C36 61.6 30.4 60 25.2 56.2 C18 51 12.6 41.6 12.6 30 C12.6 16.4 22.8 6.6 35.6 6.6Z")
HEAD_REAR = mx(HEAD_FRONT, 35.6)
EAR_F = (14.6, 41.6)
EAR_R = (19.4, 42.0)
EYE_Y = 41.4
EYES = ((33.4, 2.3), (47.0, 2.05))


def draw_head(fig, ch, view):
    s = skin_tones(ch["skin"])
    fig.at(60, head=True)
    if view == "front":
        fig.shape(HEAD_FRONT, s["base"], shadow=["M9 18 C13 34 18 46 31 61 L9 66Z"], sc=s["sh"])
    else:
        fig.shape(HEAD_REAR, s["base"], shadow=["M27 0 L80 0 L80 80 L27 80Z"], sc=s["sh"])


def draw_ear(fig, ch, view, z=61):
    s = skin_tones(ch["skin"])
    fig.at(z, head=True)
    x, y = EAR_F if view == "front" else EAR_R
    fig.shape(ell(x, y, 3.1, 4.5), s["base"], shadow=[ell(x + 0.9, y + 0.3, 1.3, 2.5)], sc=s["sh"])
    ear_jewel(fig, ch, x, y)


def ear_jewel(fig, ch, x, y):
    if ch.get("earring"):
        kind, col = ch["earring"]
        if kind == "hoop":
            fig.line("M%s %s A3.2 3.6 0 1 0 %s %s" % (f(x - 1.6), f(y + 4.0), f(x + 1.3), f(y + 4.2)), col, 1.05)
        else:
            fig.shape(ell(x, y + 4.4, 1.15), col, lw=0.6)


def draw_face(fig, ch):
    s = skin_tones(ch["skin"])
    fz = ch.get("face", {})
    fig.at(62, head=True)
    eye = "#2e2733"
    fem = ch["gender"] == "f"
    fig.fill(ell(28.8, 48.0, 3.3, 2.1), s["blush"], op=0.55)
    fig.fill(ell(50.8, 48.0, 2.7, 2.0), s["blush"], op=0.55)
    ey = EYE_Y
    for x, rx in EYES:
        if fz.get("closed"):
            fig.line("M%s %s Q%s %s %s %s" % (f(x - rx), f(ey), f(x), f(ey + 1.6), f(x + rx), f(ey)), eye, 1.2)
            continue
        fig.fill(ell(x, ey, rx, 3.05), eye)
        fig.fill(ell(x + 0.75, ey - 1.05, 0.8), "#ffffff")
        if fem:
            fig.line("M%s %s Q%s %s %s %s" % (f(x + rx - 0.4), f(ey - 2.1), f(x + rx + 1.0), f(ey - 2.6), f(x + rx + 1.7), f(ey - 3.6)),
                     eye, 0.95)
    bc = fz.get("brow") or mix(ch.get("hair_color") or "#3b2a20", "#2a2020", 0.35)
    bw = 1.05 if fem else 1.3
    fig.line("M30.4 35.0 Q33.2 33.3 36.2 34.4", bc, bw)
    fig.line("M44.6 34.2 Q47.2 33.2 49.6 34.6", bc, bw)
    fig.line("M43.0 45.2 Q44.3 47.2 42.7 47.8", s["dark"], 0.95)
    if fz.get("lips"):
        fig.fill("M38.0 51.6 Q41 50.6 44.2 51.4 Q41.2 54.6 38.0 51.6Z", fz["lips"], op=0.9)
    fig.line("M37.8 51.6 Q41 54.3 44.2 51.4", s["lip"], 1.15)
    if fz.get("freckles"):
        for x, y in ((26.8, 45.4), (28.8, 46.8), (30.6, 45.6), (49.2, 45.8), (51.0, 46.8)):
            fig.fill(ell(x, y, 0.55), shade(ch["skin"], 0.74))
    if ch.get("age") == "old":
        fig.line("M25.0 41.8 Q25.8 43.6 27.4 44.2", s["dark"], 0.65, op=0.8)
        fig.line("M36.0 48.8 Q35.0 50.8 36.2 52.4", s["dark"], 0.65, op=0.7)


def draw_glasses(fig, ch, view):
    kind, col = ch["glasses"]
    fig.at(70, head=True)
    if view == "front":
        r = 3.0 if kind == "round" else 2.0
        for x0, w in ((28.6, 9.6), (42.8, 8.4)):
            fig.fill(rect(x0, 37.4, w, 7.6, r), "#ffffff", op=0.26)
            fig.line(rect(x0, 37.4, w, 7.6, r), col, 1.1)
        fig.line("M38.2 40.0 Q40.5 38.9 42.8 40.0", col, 1.0)
        fig.line("M28.6 39.8 L17.4 38.6", col, 1.05)
    else:
        fig.line("M14.6 38.6 L21.6 39.0", col, 1.05)
        fig.line("M13.4 37.4 L13.0 43.6", col, 1.15)


# ----------------------------------------------------------------------------------------------- facial hair
def facial_hair(fig, ch, view, kind, c, role="hair"):
    """beard kinds: stubble, mustache, goatee, short, full.  Drawn over the face, in hair tones."""
    t = hair_tones(c)
    if view == "rear":
        if False:
            fig.at(63, head=True)
            d = "M12.4 34 C12 44 15 52 21 58 C24 61 28 62.6 31.6 62.4 L28 50 C24 46 20.4 41 19 34Z"
            fig.shape(d, c, role=role, sc=t["sh"], shadow=["M0 40 L72 40 L72 80 L0 80Z"])
        return
    fig.at(63, head=True)
    if kind == "stubble":
        fig.fill("M21.6 44 C23 52 30 59.6 39.8 60.4 C46 60.4 51.6 56 54.4 49 C52 53 47 55.4 43 55 C40 56.4 37 56 35 55 "
                 "C29 54 25 50 21.6 44Z", t["sh"], op=0.35)
        return
    if kind in ("mustache", "goatee", "full", "short"):
        md = "M36.2 50.4 C37.6 48.4 40 48.2 41.2 49.2 C42.6 48.2 45 48.4 46.0 50.2 C44.6 50.8 43 50.6 41.2 50.0 C39.4 50.8 37.8 51.0 36.2 50.4Z"
    if kind == "goatee":
        fig.shape(md, c, role=role, lw=0.8, lc=shade(c, 0.6))
        fig.shape("M38.2 54.6 C39.6 55.6 42.8 55.6 44.4 54.4 C45 56.6 44 59.6 41.4 60.6 C39.4 60.2 38 57.8 38.2 54.6Z", c, role=role,
                  lw=0.8, lc=shade(c, 0.6))
    elif kind == "mustache":
        fig.shape(md, c, role=role, lw=0.8, lc=shade(c, 0.6))
    elif kind in ("short", "full"):
        drop = 3.4 if kind == "full" else 0.8
        d = ("M19.4 36 C19 44 21 50 25 55 C29 60 34 %s 39.8 %s C46 %s 52 58 55 50 C56.4 46 57 41 57.4 36.6 "
             "L54.4 40 C53.6 45 51 49 47 50.4 C44 48.4 39 47.6 35.6 49 C31 49 27.6 46 25.4 41 L23 35.4Z" % (
                 f(62 + drop), f(63 + drop), f(62.6 + drop)))
        fig.shape(d, c, role=role, sc=t["sh"], hc=t["hi"], shadow=["M10 30 C18 46 24 54 34 70 L10 70Z"],
                  hi=["M41 57 C43 57 45 56.6 46.6 55.8 C45.6 57.8 43.4 58.6 41 58.4Z"])
        fig.fill("M37.6 52.6 Q41 55.2 44.4 52.4 Q41.2 57.4 37.6 52.6Z", shade(ch["skin"], 0.62))
        fig.line("M37.8 52.8 Q41 55.0 44.2 52.6", mix(shade(ch["skin"], 0.5), "#a03a44", 0.4), 1.0)
        fig.shape(md, c, role=role, lw=0.8, lc=shade(c, 0.6))


# ----------------------------------------------------------------------------------------------- garments: shared torso
SLEEVE_END = {"long": 104.0, "wide": 104.0, "3q": 97.0, "elbow": 91.0, "rolled": 94.0, "short": 84.0, "cap": 78.0}


def upper(fig, ch, view, color, role="top", sleeve="long", hem=None, flare=0.0, sleeve_color=None, sleeve_role=None,
          wide=0.0, details=None, under=None, z=40, neck_dip=2.2, cuff=None, hilite=True, pattern=None,
          sleeve_pattern=None, arm_details=None):
    """Torso and both arms of the main garment.  details(fig, ch, view, b) draws on the torso, under the near arm."""
    b = BUILD[ch["build"]]
    sc = sleeve_color or color
    srole = sleeve_role or role
    d = torso_d(b, hem=hem, flare=flare, neck_dip=neck_dip)
    bot = hem or (b["hl"][1] if "hl" in b else b["wl"][1])
    xs = b["sl"][0] + 4.4
    shd = [P((0, 0), (xs, 0), (xs + 0.8 + flare * 0.4, bot + 3), (0, bot + 3)), "M27 59 C33 66.6 39 66.6 46 59 L46 57 L27 57Z"]
    his = []
    if hilite:
        nl, sl = b["nl"], b["sl"]
        his = ["M%s %s C%s %s %s %s %s %s C%s %s %s %s %s %sZ" % tuple(map(f, (
            nl[0] - 0.6, nl[1] + 0.4, nl[0] - 4.6, nl[1] + 1.6, sl[0] + 3.4, sl[1] - 3.8, sl[0] + 3.2, sl[1] - 1.0,
            sl[0] + 7, sl[1] - 3.4, nl[0] - 2, nl[1] + 3.6, nl[0] + 1, nl[1] + 3.2)))]
    end = SLEEVE_END.get(sleeve, 104.0)
    for side in ("f", "n"):
        fig.at(z - 25 if side == "f" else z + 10)
        cx = arm_geo(b, side)[0]
        draw_hand(fig, ch, side)
        if sleeve == "none" or end < 104:
            draw_bare_arm(fig, ch, side)
        if sleeve != "none":
            ad = arm_d(b, side, end, wide=wide if sleeve in ("wide", "3q", "elbow") else 0)
            fig.shape(ad, sc, role=srole, shadow=[P((0, 0), (cx - 1.0, 0), (cx - 1.8 - wide * 0.5, 200), (0, 200))],
                      hi=[ell(cx + 0.6, b["sl"][1] - 1.4, 2.8, 1.3)] if side == "n" and hilite else [])
            if sleeve_pattern:
                sleeve_pattern(fig, ad)
                fig.line(ad, shade(sc, OUTLINE), LW)
            if sleeve == "rolled":
                fig.shape(rect(cx - b["wrist"] / 2 - 0.9 + (-0.6 if side == "n" else 0.6), end - 3.4, b["wrist"] + 1.6, 3.6, 1.4),
                          shade(sc, 0.93), role=srole, lw=0.9)
            if cuff:
                lean = -0.9 if side == "n" else 0.9
                w = b["wrist"] + (wide * 2 if sleeve in ("wide",) else 0)
                fig.shape(rect(cx + lean - w / 2, end - 3.2, w, 3.2, 1.0), cuff, lw=0.8,
                          role=srole if cuff == sc else "o")
            if arm_details:
                arm_details(fig, ch, view, side, ad)
        if side == "f":
            fig.at(z)
            if under:
                under(fig, ch, view, b)
            fig.shape(d, color, role=role, shadow=shd, hi=his)
            if pattern:
                pattern(fig, d)
                fig.line(d, shade(color, OUTLINE), LW)
            if details:
                fig.at(z + 2)
                details(fig, ch, view, b)
    return b


def clip_fill(fig, clip_d, inner, role=None):
    """Draw raw svg content clipped to a path (prints and patterns on garments).  Not in the mask."""
    fig.nclip += 1
    cid = "p%d" % fig.nclip
    fig.defs.append('<clipPath id="%s"><path d="%s"/></clipPath>' % (cid, clip_d))
    fig.raw('<g clip-path="url(#%s)">%s</g>' % (cid, inner))


def stripes(color, gap=4.6, w=2.0, y0=60, y1=200, op=1.0):
    def pat(fig, d):
        inner = "".join('<rect x="0" y="%s" width="72" height="%s" fill="%s"%s/>' % (
            f(y), f(w), color, ' opacity="%s"' % f(op) if op < 1 else "") for y in frange(y0, y1, gap))
        clip_fill(fig, d, inner)
    return pat


def frange(a, b, s):
    out, x = [], a
    while x < b:
        out.append(x); x += s
    return out


def dots(colors, step=6.0, r=1.1, y0=58, y1=200, x0=8, x1=66, jitter=0.5, shape="dot"):
    def pat(fig, d):
        inner, k = "", 0
        for j, y in enumerate(frange(y0, y1, step)):
            for i, x in enumerate(frange(x0 + (step / 2 if j % 2 else 0), x1, step)):
                c = colors[k % len(colors)]; k += 1
                if shape == "flower":
                    inner += flower_svg(x, y, r, c[0], c[1])
                elif shape == "diamond":
                    inner += '<path d="M%s %s L%s %s L%s %s L%s %sZ" fill="%s"/>' % (
                        f(x), f(y - r), f(x + r), f(y), f(x), f(y + r), f(x - r), f(y), c)
                else:
                    inner += '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (f(x), f(y), f(r), c)
        clip_fill(fig, d, inner)
    return pat


def flower_svg(x, y, r, petal, center):
    s = ""
    for k in range(5):
        a = math.radians(k * 72 - 90)
        s += '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (f(x + math.cos(a) * r * 0.62), f(y + math.sin(a) * r * 0.62), f(r * 0.5), petal)
    return s + '<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (f(x), f(y), f(r * 0.32), center)


def placket(fig, color, top=68.0, bottom=111.0, x=FRONT_X, buttons=4, btn=None):
    fig.line("M%s %s L%s %s" % (f(x), f(top), f(x + 0.3), f(bottom)), shade(color, 0.7), 0.75)
    for k in range(buttons):
        y = top + 4 + k * (bottom - top - 7) / max(1, buttons - 1)
        fig.fill(ell(x + 1.3, y, 0.7), btn or shade(color, 0.6))


def shirt_collar(fig, color, role="top", y=62.4, inner=None):
    """Turn-down collar around an open neck (front view)."""
    if inner:
        fig.shape("M31.4 %s L41.0 %s L38.0 %s Z" % (f(y + 0.6), f(y + 0.6), f(y + 7.8)), inner, lw=0.8)
    fig.shape("M29.6 %s L37.4 %s L32.8 %s L28.6 %s Z" % (f(y - 0.6), f(y + 7.2), f(y + 8.2), f(y + 2.6)), color, role=role, lw=0.9,
              shadow=[], hi=[])
    fig.shape("M42.6 %s L38.6 %s L42.4 %s L44.6 %s Z" % (f(y - 0.6), f(y + 7.2), f(y + 7.8), f(y + 2.4)), color, role=role, lw=0.9)


def band_collar(fig, color, role="top", y=62.2, h=3.0):
    fig.shape("M29.8 %s C34 %s 38.6 %s 42.4 %s L42.6 %s C38.6 %s 34 %s 29.8 %s Z" % tuple(map(f, (
        y, y + 1.8, y + 1.8, y, y + h, y + h + 1.8, y + h + 1.8, y + h))), color, role=role, lw=0.9)


def rear_collar(fig, color, role="top", y=61.2, h=3.4):
    fig.shape("M29.4 %s C33 %s 39 %s 42.6 %s L43.2 %s C39 %s 33 %s 28.8 %s Z" % tuple(map(f, (
        y + 1.2, y - 0.4, y - 0.4, y + 1.2, y + 1.2 + h, y + h - 0.2, y + h - 0.2, y + 1.2 + h))), color, role=role, lw=0.9)


def neckband(fig, color, role="top", y=62.6, rear=False):
    if rear:
        fig.line("M30.2 %s C34 %s 38 %s 41.8 %s" % (f(y + 0.4), f(y - 0.6), f(y - 0.6), f(y + 0.4)), shade(color, 0.8), 1.8)
    else:
        fig.line("M30.6 %s C33 %s 39 %s 41.4 %s" % (f(y + 0.2), f(y + 3.4), f(y + 3.4), f(y + 0.2)), shade(color, 0.82), 1.8)


def tie(fig, color, y=62.6, length=100.0, x=38.0):
    fig.shape("M%s %s L%s %s L%s %s L%s %s Z" % tuple(map(f, (x - 1.7, y + 3.6, x + 1.7, y + 3.6, x + 1.1, y + 6.6, x - 1.1, y + 6.6))),
              color, lw=0.8)
    fig.shape("M%s %s L%s %s L%s %s L%s %s L%s %s Z" % tuple(map(f, (x - 1.1, y + 6.4, x + 1.1, y + 6.4, x + 2.5, length - 3,
                                                                     x + 0.3, length, x - 1.9, length - 3))),
              color, lw=0.8, hi=[P((x - 3, y + 6), (x - 0.2, y + 6), (x - 0.6, length), (x - 3, length))], hc=shade(color, 1.14))


def hem_rib(fig, color, y, b, h=3.0, role="top", flare=0.0, x_l=None, x_r=None):
    l = x_l if x_l is not None else (b["hl"][0] if "hl" in b else b["wl"][0]) - flare
    r = x_r if x_r is not None else (b["hr"][0] if "hr" in b else b["wr"][0]) + flare
    fig.shape(P((l + 0.2, y - h), (r - 0.2, y - h), (r, y), (l, y)), shade(color, 0.9), role=role, lw=0.9)


# ----------------------------------------------------------------------------------------------- garments: tops
def top_shirt(color, sleeve="rolled", tucked=True, belt_c="#5b4636", pocket=True, inner=None, buttons=5, hem=None):
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        def det(fig, ch, view, b):
            if view == "front":
                shirt_collar(fig, color, inner=inner)
                placket(fig, color, top=69.6, bottom=(hem or 111), buttons=buttons - 1)
                if pocket:
                    fig.line(P((43.4, 77.4), (49.2, 77.4), (49.0, 83.4), (43.6, 83.4)), shade(color, 0.72), 0.75)
            else:
                rear_collar(fig, color)
                fig.line("M18.6 77 Q36 80.4 53.4 77", shade(color, 0.76), 0.75)
            if tucked:
                belt(fig, belt_c, b=b, buckle="#d8c48a" if view == "front" else None)
        upper(fig, ch, view, color, sleeve=sleeve, hem=hem, details=det, cuff=None)
    return draw


def top_tee(color, neck="crew", print_=None, sleeve="short", hem=None, tucked=False):
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            neckband(fig, color, rear=view == "rear")
            if print_ and view == "front":
                print_(fig)
        upper(fig, ch, view, color, sleeve=sleeve, hem=hem or (117 if ch["build"] != "f" else 115), details=det)
    return draw


def top_sweater(color, hem=None, oversized=False, rib=True, collar=None, sleeve="long", pattern=None, neck_c=None):
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        hh = hem or (118 if ch["build"] != "f" else 117)
        def det(fig, ch, view, b):
            if collar and view == "front":
                shirt_collar(fig, collar, role="o")
            neckband(fig, neck_c or color, rear=view == "rear")
            if rib:
                hem_rib(fig, color, hh, b, flare=1.6 if oversized else 0.6)
        upper(fig, ch, view, color, sleeve=sleeve, hem=hh, flare=1.6 if oversized else 0.6,
              wide=1.2 if oversized else 0.2, cuff=shade(color, 0.9) if rib else None, pattern=pattern)
    return draw


def top_hoodie(color, strings="#f4f2ee", pocket=True):
    def draw(fig, ch, view):
        hh = 119 if ch["build"] != "f" else 117
        def under(fig, ch, view, b):
            if view == "front":   # hood bunched behind the neck
                fig.shape("M22.6 70 C21 62 25 56.4 31 56.6 L41 56.6 C47 56.4 51 61.6 49.6 69 L36 66Z", shade(color, 0.86), role="top")
        def det(fig, ch, view, b):
            if view == "front":
                fig.line("M30.6 62.8 C33 66.4 39 66.4 41.6 62.8", shade(color, 0.7), 1.0)
                fig.line("M34.6 65.6 L34.2 78", strings, 1.0); fig.line("M39.2 65.8 L39.8 77.6", strings, 1.0)
                fig.fill(ell(34.2, 78.4, 0.9, 1.2), shade(strings, 0.8)); fig.fill(ell(39.8, 78.0, 0.9, 1.2), shade(strings, 0.8))
                if pocket:
                    fig.shape("M27.6 99 L48.4 99 L50.4 112 L25.4 112 Z", color, role="top", lw=0.9, shadow=["M20 99 L29 99 L28 113 L20 113Z"])
            else:
                fig.shape("M22.4 66 C20.6 76 24 86 36 88 C48 86 51.6 76 49.6 66 C45 63 27 63 22.4 66Z", color, role="top",
                          shadow=["M18 60 L28 60 L30 90 L18 90Z"], hi=["M24 66.6 C30 64.2 42 64.2 48 66.6 C42 66.4 30 66.4 24 66.6Z"])
                fig.line("M27 70 C30 80 42 80 45 70", shade(color, 0.76), 0.8)
            hem_rib(fig, color, hh, b, flare=1.0)
        upper(fig, ch, view, color, sleeve="long", hem=hh, flare=1.0, wide=0.6, cuff=shade(color, 0.9), under=under, details=det)
    return draw


def top_cardigan(color, inner, hem=None, buttons=4, inner_neck="crew", collar=None):
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        hh = hem or (121 if ch["build"] != "f" else 119)
        def det(fig, ch, view, b):
            if view == "front":
                bot = hh
                fig.shape("M31.2 62.8 L41.2 62.8 L41.8 %s L34.8 %s Z" % (f(bot), f(bot)), inner, lw=0.9,
                          shadow=["M30 60 L35.4 60 L35.4 %s L30 %sZ" % (f(bot), f(bot))])
                if collar:
                    shirt_collar(fig, collar, role="o")
                elif inner_neck == "crew":
                    fig.line("M31.4 63.2 C33.6 66 38.6 66 41.0 63.2", shade(inner, 0.8), 1.2)
                fig.shape("M30.6 62.6 L35.6 82 L35.2 %s L27.4 %s L28.4 70Z" % (f(bot), f(bot)), color, role="top", lw=LW,
                          shadow=[P((0, 0), (30.4, 0), (30.4, 200), (0, 200))])
                fig.shape("M41.6 62.6 L40.4 82 L41.6 %s L49.8 %s L48 70Z" % (f(bot), f(bot)), color, role="top", lw=LW)
                for k in range(buttons):
                    fig.fill(ell(41.6, 86 + k * (bot - 90) / max(1, buttons - 1), 0.75), shade(color, 0.6))
            else:
                neckband(fig, color, rear=True)
            hem_rib(fig, color, hh, b, flare=1.0)
        upper(fig, ch, view, color, sleeve="long", hem=hh, flare=1.0, cuff=shade(color, 0.9), details=det)
    return draw


def top_blazer(color, inner="#f7f6f2", tie_c=None, hem=None, lapel=None, buttons=2, pocket=True, pattern=None,
               patches=None, open_=False, inner_kind="shirt"):
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        hh = hem or (121 if ch["build"] != "f" else 118)
        lp = lapel or shade(color, 1.08)
        vb = 90 if ch["build"] != "f" else 88
        def det(fig, ch, view, b):
            if view == "front":
                fig.shape("M30.6 62.6 L41.4 62.6 L38.6 %s Z" % f(vb + 2), inner, lw=0.9)
                if inner_kind == "shirt":
                    shirt_collar(fig, inner, role="o", y=62.4)
                elif inner_kind == "crew":
                    fig.line("M31.4 63.4 C33.6 66 38.6 66 41 63.4", shade(inner, 0.8), 1.2)
                if tie_c:
                    tie(fig, tie_c, length=vb + 1)
                fig.shape("M30.6 62.6 L38.2 %s L34.2 %s L27.0 71.4 L29.2 67.4 Z" % (f(vb), f(vb - 13)), lp, role="top", lw=0.95)
                fig.shape("M41.4 62.6 L39.2 %s L42.6 %s L47.0 70.8 L43.6 67.0 Z" % (f(vb), f(vb - 13)), lp, role="top", lw=0.95)
                fig.line("M38.6 %s L39.4 %s" % (f(vb), f(hh)), shade(color, 0.62), 0.9)
                for k in range(buttons):
                    fig.fill(ell(40.6, vb + 3 + k * 8, 0.85), shade(color, 0.55))
                if pocket:
                    fig.line("M42.6 104.4 L49.4 104.0", shade(color, 0.62), 1.0)
                    fig.line("M44.0 76.4 L48.8 76.0", shade(color, 0.64), 0.9)
            else:
                rear_collar(fig, shade(color, 1.06), y=60.8)
                fig.line("M36.4 66 L36.8 %s" % f(hh), shade(color, 0.7), 0.8)
        def ad(fig, ch, view, side, d):
            if patches and view == "rear" and side == "n":
                cx = arm_geo(BUILD[ch["build"]], "n")[0]
                fig.shape(ell(cx - 0.4, 90, 2.8, 4.2), patches, lw=0.8)
        upper(fig, ch, view, color, sleeve="long", hem=hh, flare=1.2, details=det, pattern=pattern, sleeve_pattern=pattern,
              cuff=None, arm_details=ad)
    return draw


def top_knit(color, yoke, motif, hem=None):
    """Nordic knit: patterned yoke around the shoulders, bands at hem and cuffs."""
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        hh = hem or 117
        def det(fig, ch, view, b):
            yk = "M20 70 C22 62 30 60.6 36 60.6 C42 60.6 50 62 52 70 L51.6 78.6 C46 82 26 82 20.4 78.6Z"
            fig.shape(yk, yoke, role="top", lw=0, shadow=[P((0, 0), (24, 0), (24, 90), (0, 90))])
            for x in frange(21.4, 52, 3.6):
                fig.fill("M%s 76.4 L%s 74.2 L%s 76.4 L%s 78.6Z" % (f(x - 1.4), f(x), f(x + 1.4), f(x)), motif)
            for x in frange(23.2, 50, 3.6):
                fig.fill(ell(x, 70.6, 0.8), motif)
            fig.line("M20.2 79.2 C26 82.6 46 82.6 51.8 79.2", shade(color, 0.7), 0.8)
            neckband(fig, yoke, rear=view == "rear")
            hem_rib(fig, yoke, hh, b, flare=1.0)
            for x in frange(23, 50, 3.6):
                fig.fill("M%s %s L%s %s L%s %s L%s %sZ" % tuple(map(f, (x - 1.2, hh - 1.5, x, hh - 2.7, x + 1.2, hh - 1.5, x, hh - 0.3))), motif)
        upper(fig, ch, view, color, sleeve="long", hem=hh, flare=1.0, wide=0.4, cuff=yoke, details=det)
    return draw


def top_qipao(color, trim, motif=None, hem=None):
    """Qipao-style blouse: mandarin collar, curved closure to the wearer's right, frog buttons, piping."""
    def draw(fig, ch, view):
        hh = hem or 116
        def det(fig, ch, view, b):
            if view == "front":
                band_collar(fig, color, h=3.6)
                fig.line("M30.0 62.6 C34 64.6 38.6 64.6 42.4 62.6", trim, 1.0)
                fig.line("M36.2 66.4 C33 70 28 72 24.4 74.6", trim, 1.2)
                for x, y in ((33.2, 69.2), (28.6, 72.4)):
                    fig.line("M%s %s L%s %s" % (f(x - 1.4), f(y - 0.6), f(x + 1.4), f(y + 0.6)), trim, 1.3)
                    fig.fill(ell(x, y, 0.8), shade(trim, 0.8))
            else:
                band_collar(fig, color, y=60.8, h=3.4)
            if motif:
                pass
        upper(fig, ch, view, color, sleeve="cap", hem=hh, details=det, pattern=motif)
    return draw


def top_guayabera(color):
    def draw(fig, ch, view):
        hh = 123
        def det(fig, ch, view, b):
            pc = shade(color, 0.74)
            if view == "front":
                shirt_collar(fig, color, y=62.4)
                placket(fig, color, top=70, bottom=hh, buttons=5)
                for x in (27.2, 31.2, 45.4, 48.6):
                    fig.line("M%s 70 L%s %s" % (f(x), f(x + 0.2), f(hh - 1)), pc, 0.75)
                for x0, y0, w in ((25.4, 80, 8.0), (43.6, 80, 6.6), (25.0, 105, 8.4), (43.8, 105, 7.0)):
                    fig.line(P((x0, y0), (x0 + w, y0), (x0 + w, y0 + 6.4), (x0, y0 + 6.4)), pc, 0.75)
                    fig.fill(ell(x0 + w / 2, y0 + 1.6, 0.6), shade(color, 0.6))
            else:
                rear_collar(fig, color)
                fig.line("M18.6 77 Q36 80.4 53.4 77", pc, 0.75)
                for x in (28.0, 36.4, 45.0):
                    fig.line("M%s 79.6 L%s %s" % (f(x), f(x + 0.2), f(hh - 1)), pc, 0.75)
        upper(fig, ch, view, color, sleeve="short", hem=hh, flare=1.4, details=det)
    return draw


def top_barong(color, embroidery, under_c="#fbfaf6"):
    """Barong tagalog: sheer embroidered shirt, untucked, over a white undershirt."""
    def draw(fig, ch, view):
        hh = 124
        def det(fig, ch, view, b):
            fig.fill(torso_d(b, hem=hh - 4) if False else "M24 72 C28 66 44 66 48 72 L49 %s L23 %sZ" % (f(hh - 3), f(hh - 3)), under_c, op=0.55)
            if view == "front":
                band_collar(fig, color, h=3.0)
                fig.shape("M34.6 66 L42.6 66 L43.6 %s L34.4 %s Z" % (f(hh - 2), f(hh - 2)), shade(color, 1.06), role="top", lw=0.7,
                          lc=shade(embroidery, 0.9))
                for y in frange(69, hh - 4, 4.4):
                    fig.line("M35.6 %s Q38.8 %s 42.4 %s" % (f(y), f(y + 2.2), f(y)), embroidery, 0.75)
                    fig.fill(ell(39.0, y + 2.6, 0.7), embroidery)
                for k in range(4):
                    fig.fill(ell(43.4, 72 + k * 9, 0.6), shade(color, 0.6))
            else:
                band_collar(fig, color, y=60.8, h=3.0)
                for y in frange(72, hh - 6, 6):
                    fig.line("M26 %s Q36 %s 46 %s" % (f(y), f(y + 2.4), f(y)), embroidery, 0.6, op=0.7)
        sk = mix(color, ch["skin"], 0.28)
        upper(fig, ch, view, color, sleeve="long", hem=hh, flare=1.2, details=det, sleeve_color=sk, cuff=color)
    return draw


def top_floral(color, petal, center, sleeve="short", hem=121):
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            if view == "front":
                fig.shape("M30.4 62.4 L37.8 72.4 L33.4 74.6 L28.0 66.4Z", color, role="top", lw=0.9)
                fig.shape("M41.8 62.4 L38.6 72.4 L42.6 73.8 L45.2 66.2Z", color, role="top", lw=0.9)
                fig.fill("M31.4 62.8 L41.0 62.8 L38.2 72Z", ch["skin"])
                placket(fig, color, top=73, bottom=hem, buttons=4, btn="#f6efe2")
            else:
                rear_collar(fig, color)
        pat = dots([(petal, center), (shade(petal, 0.9), center)], step=8.4, r=3.0, y0=66, x0=10, shape="flower")
        upper(fig, ch, view, color, sleeve=sleeve, hem=hem, flare=1.4, details=det, pattern=pat, sleeve_pattern=pat)
    return draw


# ----------------------------------------------------------------------------------------------- garments: robes and dress
ROBE_HEM = 193.0


def top_thobe(color, collar="mandarin", pocket=True, cuff=True, hem=ROBE_HEM):
    """Gulf thobe: band collar, short placket, breast pocket, cuffs; ankle length."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            lc = shade(color, 0.76)
            if view == "front":
                if collar == "mandarin":
                    band_collar(fig, color, h=3.2)
                    placket(fig, color, top=66.4, bottom=90, buttons=3, btn="#d9d4c6")
                if pocket:
                    fig.line("M43.6 77.6 L49.2 77.2 L49.0 83.4 L43.8 83.6", lc, 0.7)
                    fig.line("M45.2 76.4 L45.4 79.6", "#5a6a8a", 1.0)
                fig.line("M27 120 C27.4 150 26.6 175 25.4 %s" % f(hem - 2), lc, 0.7, op=0.8)
                fig.line("M44.6 118 C45.6 150 46.4 172 47.2 %s" % f(hem - 2), lc, 0.7, op=0.6)
            else:
                band_collar(fig, color, y=60.8, h=3.0)
                fig.line("M30 118 C30 150 29.4 176 28.6 %s" % f(hem - 2), lc, 0.7, op=0.8)
        upper(fig, ch, view, color, sleeve="long", hem=hem, flare=3.4, details=det, cuff=color if cuff else None)
    return draw


def top_dishdasha(color, tassel):
    """Omani dishdasha: collarless round neck with the farrukha tassel; ankle length."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            lc = shade(color, 0.74)
            if view == "front":
                fig.line("M30.8 63.2 C33 66.6 39 66.8 41.4 63.2", lc, 1.0)
                fig.line("M38.8 65.8 L39.0 76", lc, 0.8)
                fig.line("M39.6 66.4 C40.4 72 40.6 78 40.4 84", tassel, 1.1)
                fig.shape("M39.2 83.6 L41.6 83.6 L42.6 90.6 L38.4 90.6 Z", tassel, lw=0.7)
                fig.line("M27 120 C27.4 150 26.6 175 25.4 191", lc, 0.7, op=0.8)
                fig.line("M44.6 118 C45.6 150 46.4 172 47.2 191", lc, 0.7, op=0.6)
            else:
                fig.line("M30.0 62.2 C34 60.8 38 60.8 42.0 62.2", lc, 1.0)
                fig.line("M30 118 C30 150 29.4 176 28.6 191", lc, 0.7, op=0.8)
        upper(fig, ch, view, color, sleeve="long", hem=ROBE_HEM, flare=3.4, details=det)
    return draw


def top_jalabiya(color):
    """Sudanese jalabiya: wide round-necked robe with a short slit and wide sleeves."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            lc = shade(color, 0.76)
            if view == "front":
                fig.line("M30.6 63.0 C33 66.8 39 67.0 41.6 63.0", lc, 1.0)
                fig.line("M37.6 66.4 L37.8 78", lc, 0.9)
                fig.line("M26 118 C26 150 25 176 23.6 191", lc, 0.7, op=0.8)
                fig.line("M45 116 C46 150 47 172 48.6 191", lc, 0.7, op=0.6)
            else:
                fig.line("M30.0 62.2 C34 60.8 38 60.8 42.0 62.2", lc, 1.0)
                fig.line("M30 118 C30 150 29 176 28 191", lc, 0.7, op=0.8)
        upper(fig, ch, view, color, sleeve="wide", wide=1.6, hem=ROBE_HEM, flare=5.0, details=det)
    return draw


def top_djellaba(color, stripe=None, trim=None):
    """Moroccan djellaba: long hooded robe, wide sleeves, knotted buttons down the neck slit."""
    def draw(fig, ch, view):
        tc = trim or shade(color, 0.7)
        def under(fig, ch, view, b):
            if view == "front":
                fig.shape("M20.6 72 C19 62 25 55.6 31 56 L41 56 C47 55.6 52.4 61 50.8 71 L36 66Z", shade(color, 0.88), role="top")
        def det(fig, ch, view, b):
            if view == "front":
                fig.line("M31 63.2 C33 66.6 39 66.8 41.4 63.2", tc, 1.2)
                fig.line("M38.6 66 L38.8 90", tc, 1.1)
                for y in frange(68, 90, 3.4):
                    fig.fill(ell(39.8, y, 0.75), tc)
            else:
                hood = "M24 62 C21 70 22 84 28 96 C31 101 34 106 36.4 110 C38.4 106 41.6 101 44.6 96 C50 84 51 70 48 62 C42 59.6 30 59.6 24 62Z"
                fig.shape(hood, color, role="top", shadow=["M18 58 L28 58 L32 112 L18 112Z"],
                          hi=["M26 63 C32 61 40 61 46 63 C40 63.2 32 63.2 26 63Z"])
                fig.line("M28.6 66 C30 80 33 94 36.4 108", tc, 0.9)
                fig.line(hood, tc, 0.9)
        pat = stripes(stripe, gap=5.4, w=1.0, op=0.55) if stripe else None
        upper(fig, ch, view, color, sleeve="wide", wide=1.8, hem=ROBE_HEM, flare=4.0, under=under, details=det,
              pattern=pat)
    return draw


def top_abaya(color, trim, hem=ROBE_HEM + 2):
    """Gulf abaya: flowing black robe with wide sleeves; a fine embroidered trim at the front and cuffs."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            if view == "front":
                fig.line("M39.0 70 C39.4 110 40.4 150 41.6 %s" % f(hem - 1), trim, 1.0, op=0.95)
                fig.line("M40.6 70 C41.0 110 42.0 150 43.2 %s" % f(hem - 1), shade(color, 1.3), 0.6, op=0.8)
                fig.line("M27 112 C26 140 24.6 170 23 %s" % f(hem - 2), shade(color, 1.45), 0.7, op=0.7)
                fig.line("M47 112 C48.6 140 50 170 51 %s" % f(hem - 2), shade(color, 1.45), 0.7, op=0.5)
            else:
                fig.line("M30 112 C29.4 140 28.6 170 27.6 %s" % f(hem - 2), shade(color, 1.45), 0.7, op=0.7)
                fig.line("M43 112 C44 140 45 170 46 %s" % f(hem - 2), shade(color, 1.45), 0.7, op=0.5)
        def ad(fig, ch, view, side, d):
            b = BUILD[ch["build"]]
            cx = arm_geo(b, side)[0] + (-0.9 if side == "n" else 0.9)
            fig.line("M%s 101.6 L%s 101.6" % (f(cx - b["wrist"] / 2 - 2.2), f(cx + b["wrist"] / 2 + 2.2)), trim, 1.2)
        upper(fig, ch, view, color, sleeve="wide", wide=2.2, hem=hem, flare=5.6, details=det, arm_details=ad)
    return draw


def top_kurta(color, trim=None, hem=156.0):
    """Kurta: knee-length tunic, band collar, half placket, long sleeves, side slits."""
    def draw(fig, ch, view):
        tc = trim or shade(color, 0.7)
        def det(fig, ch, view, b):
            if view == "front":
                band_collar(fig, color, h=3.0)
                fig.line("M38.6 65.8 L38.8 92", tc, 0.9)
                for y in (70, 76, 82, 88):
                    fig.fill(ell(39.8, y, 0.75), shade(color, 0.6))
                fig.line("M20.0 %s L21.6 %s" % (f(hem), f(hem - 12)), shade(color, 0.7), 0.8)
                fig.line("M52.4 %s L51.2 %s" % (f(hem), f(hem - 12)), shade(color, 0.7), 0.8)
            else:
                band_collar(fig, color, y=60.8, h=3.0)
        upper(fig, ch, view, color, sleeve="long", hem=hem, flare=3.0, details=det, cuff=None)
    return draw


def top_kameez(color, trim, hem=162.0, motif=None):
    """Kameez: long tunic with an embroidered round neck, 3/4 sleeves and side slits."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            if view == "front":
                fig.shape("M30.6 63.0 C32 70 40 70.6 41.6 63.0 L43.4 64.4 C42 73.6 30 73.6 28.8 64.4Z", trim, lw=0.8)
                for x, y in ((31, 68), (34, 70.6), (38, 70.8), (41.2, 68.4)):
                    fig.fill(ell(x, y, 0.7), shade(trim, 0.7))
                fig.line("M19.0 %s L20.8 %s" % (f(hem), f(hem - 14)), shade(color, 0.7), 0.8)
                fig.line("M53.4 %s L52.0 %s" % (f(hem), f(hem - 14)), shade(color, 0.7), 0.8)
                fig.fill(P((18, hem - 3), (56, hem - 3), (56, hem + 1), (18, hem + 1)), trim, op=0.9)
            else:
                fig.line("M30.0 62.4 C34 61 38 61 42.0 62.4", trim, 1.6)
                fig.fill(P((18, hem - 3), (56, hem - 3), (56, hem + 1), (18, hem + 1)), trim, op=0.9)
        upper(fig, ch, view, color, sleeve="3q", wide=0.6, hem=hem, flare=3.6, details=det, cuff=trim, pattern=motif)
    return draw


def top_kurung(color, motif, hem=150.0):
    """Baju kurung: loose knee-length tunic with a round neck and long loose sleeves."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            if view == "front":
                fig.line("M30.8 63.2 C33 67 39 67.2 41.4 63.2", shade(color, 0.7), 1.0)
                fig.line("M37.2 66.6 L37.4 73", shade(color, 0.7), 0.9)
        pat = dots([motif, shade(motif, 0.9)], step=7.2, r=2.4, y0=68, shape="flower") if motif else None
        upper(fig, ch, view, color, sleeve="wide", wide=1.0, hem=hem, flare=4.0, details=det, pattern=pat, sleeve_pattern=pat)
    return draw


def top_kemis(color, tibeb, hem=ROBE_HEM + 1):
    """Habesha kemis: white cotton dress, woven tibeb band down the front, at the hem and cuffs."""
    def draw(fig, ch, view):
        t1, t2, t3 = tibeb
        def band(fig, x0, x1, y0, y1):
            fig.shape(P((x0, y0), (x1, y0), (x1 + 0.4, y1), (x0 - 0.4, y1)), t1, lw=0.7, lc=shade(t1, 0.6))
            for y in frange(y0 + 2, y1 - 1, 3.6):
                fig.fill("M%s %s L%s %s L%s %s L%s %sZ" % tuple(map(f, ((x0 + x1) / 2 - 1.6, y, (x0 + x1) / 2, y - 1.4,
                                                                       (x0 + x1) / 2 + 1.6, y, (x0 + x1) / 2, y + 1.4))), t2)
            fig.line("M%s %s L%s %s" % (f(x0 + 0.8), f(y0), f(x0 + 0.6), f(y1)), t3, 0.6)
            fig.line("M%s %s L%s %s" % (f(x1 - 0.8), f(y0), f(x1 - 0.6), f(y1)), t3, 0.6)
        def det(fig, ch, view, b):
            if view == "front":
                fig.line("M31 63.2 C33.4 66.4 38.6 66.6 41.2 63.2", t1, 1.4)
                band(fig, 35.6, 41.6, 65.6, 116)
                fig.fill(P((17.4, hem - 7), (54.6, hem - 7), (54.8, hem - 3.6), (17.2, hem - 3.6)), t1)
                for x in frange(19.4, 54, 3.4):
                    fig.fill(ell(x, hem - 5.3, 0.8), t2)
                fig.line("M17 %s L55 %s" % (f(hem - 2.6), f(hem - 2.6)), t3, 0.8)
            else:
                fig.line("M30.0 62.2 C34 60.8 38 60.8 42.0 62.2", t1, 1.4)
                fig.fill(P((17.4, hem - 7), (54.6, hem - 7), (54.8, hem - 3.6), (17.2, hem - 3.6)), t1)
                for x in frange(19.4, 54, 3.4):
                    fig.fill(ell(x, hem - 5.3, 0.8), t2)
        upper(fig, ch, view, color, sleeve="long", hem=hem, flare=5.0, details=det, cuff=t1)
    return draw


def top_dress(color, pattern=None, hem=180.0, sleeve="elbow", neck=None, peplum=None):
    """Fitted long dress (e.g. an ankara print dress)."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            fig.line("M31 63.2 C33.4 66.6 38.6 66.8 41.2 63.2" if view == "front" else "M30 62.2 C34 60.8 38 60.8 42 62.2",
                     neck or shade(color, 0.7), 1.3)
        upper(fig, ch, view, color, sleeve=sleeve, wide=0.8, hem=hem, flare=4.4, details=det, pattern=pattern,
              sleeve_pattern=pattern)
    return draw


def top_aodai(color, trim=None, hem=176.0):
    """Ao dai: fitted tunic, high collar, closure to the wearer's right, panels split from the waist."""
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        tc = trim or shade(color, 0.72)
        def det(fig, ch, view, b):
            if view == "front":
                band_collar(fig, color, h=4.0)
                fig.line("M36.4 67 C33 70.4 28.4 72.6 25.4 75.6", tc, 1.0)
                for x, y in ((33.4, 69.4), (29.6, 72.2)):
                    fig.fill(ell(x, y, 0.7), tc)
            else:
                band_collar(fig, color, y=60.6, h=3.8)
        # the long panel below the waist, front panel narrower than the hips: trousers show at the sides
        fig.at(31)
        top = 104.0
        panel = "M24.6 %s L47.4 %s L48.6 %s Q37 %s 25.6 %s Z" % (f(top), f(top), f(hem), f(hem + 2.4), f(hem))
        if view == "rear":
            panel = "M23.6 %s L48.4 %s L50.0 %s Q37 %s 23.4 %s Z" % (f(top), f(top), f(hem + 1), f(hem + 3.4), f(hem + 1))
        fig.shape(panel, color, role="top", shadow=[P((0, 0), (28.6, 0), (29.6, 200), (0, 200))])
        fig.line("M36.6 112 C36.8 140 37 160 37 %s" % f(hem - 4), shade(color, 0.8), 0.7, op=0.7)
        upper(fig, ch, view, color, sleeve="long", hem=b["hl"][1] - 4, details=det, cuff=None)
    return draw


def top_sari(sari, border, blouse):
    """Sari: fitted blouse, pleated skirt, pallu across the chest and over the wearer's left shoulder."""
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        fig.at(30)
        # skirt part to the floor with front pleats
        sk = "M22.6 104 L49.6 104 L52.6 194.6 Q37 196.6 20.6 194.6 Z"
        fig.shape(sk, sari, role="top", shadow=[P((0, 0), (26.6, 0), (25.6, 200), (0, 200))])
        clip_fill(fig, sk, '<rect x="0" y="191.4" width="72" height="6" fill="%s"/>' % border)
        fig.line("M20.6 194.6 Q37 196.6 52.6 194.6", shade(sari, OUTLINE), LW)
        if view == "front":
            for x0, x1 in ((35.2, 34.6), (38.0, 38.0), (40.8, 41.6), (43.4, 45.0)):
                fig.line("M%s 118 L%s 191" % (f(x0), f(x1)), shade(sari, 0.74), 0.75)
        upper(fig, ch, view, blouse, role="o", sleeve="elbow", hem=106, details=None, z=40)
        fig.at(46)
        if view == "front":
            # pallu: from the wearer's right hip across the chest, over the left shoulder (screen right)
            pl = "M21.0 108 C26 96 34 84 42 74 C45 70 47.6 66 49.6 64.6 L54.0 68.6 C55 76 54.4 88 52.6 98 L51.4 112 C42 112 30 112 21.0 108Z"
            fig.shape(pl, sari, role="top", shadow=["M10 100 L30 100 L30 120 L10 120Z"], hi=["M45 70 C47 67 48.6 65.6 49.8 65 L51 66.4 C49 68 47 70 45.6 72Z"])
            fig.line("M21.0 108 C26 96 34 84 42 74 C45 70 47.6 66 49.6 64.6", border, 1.8)
            fig.line("M30 106 C35 96 41 88 47 80", shade(sari, 0.74), 0.7)
            fig.line("M36 109 C40 100 45 92 50 86", shade(sari, 0.74), 0.7)
        else:
            # pallu falls from the wearer's left shoulder (screen left in this view) down the back
            pl = "M17.6 68 C21 64 27 62.6 31 63 L36 70 C34 90 32 120 31 150 L19 150 C17 120 16.4 90 17.6 68Z"
            fig.shape(pl, sari, role="top", shadow=["M0 0 L21 0 L21 160 L0 160Z"])
            clip_fill(fig, pl, '<rect x="0" y="145.4" width="72" height="5" fill="%s"/>' % border)
            fig.line(pl, shade(sari, OUTLINE), LW)
            fig.line("M33.6 72 C32.6 92 31.2 120 30.6 148", border, 1.6)
    return draw


def top_manta(shawl, band, blouse, hem=None):
    """Andean manta: woven shawl over the shoulders, knotted at the chest, over a blouse."""
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        upper(fig, ch, view, blouse, role="o", sleeve="long", hem=hem or 112, cuff=None)
        fig.at(52)
        if view == "front":
            d = ("M17.6 66 C22 61.4 30 60.4 36 60.8 C43 60.8 50 62 55 66.6 C57.6 76 57.6 88 56.4 96 L50 94 "
                 "C46 90 42 86 38.6 82.6 C34 86 28 90 22 94 L15.4 96.4 C14.6 86 15 74 17.6 66Z")
            fig.shape(d, shawl, role="top", shadow=["M0 0 L21 0 L21 120 L0 120Z"], hi=["M22 64 C28 62 34 61.4 38 61.6 C32 62.6 27 63.6 23.4 65.4Z"])
            for k, c in enumerate(band):
                fig.line("M%s %s C%s %s %s %s" % tuple(map(f, (16.0 + k * 0.2, 88 + k * 1.8, 25, 85 + k * 1.8, 37, 76 + k * 1.8))), c, 1.2)
                fig.line("M%s %s C%s %s %s %s" % tuple(map(f, (56.0 - k * 0.2, 88 + k * 1.8, 48, 84 + k * 1.8, 40, 76 + k * 1.8))), c, 1.2)
            fig.shape(ell(38.6, 82.4, 2.6, 2.2), shade(shawl, 0.9), role="top", lw=0.9)
            fig.line(d, shade(shawl, OUTLINE), LW)
        else:
            d = ("M17.4 66 C22 61 30 60 36 60.2 C43 60 50 61 55 66 C57.6 80 57 96 55 108 C46 112 26 112 17.6 108 "
                 "C15.4 96 15 80 17.4 66Z")
            fig.shape(d, shawl, role="top", shadow=["M0 0 L21 0 L21 120 L0 120Z"])
            for k, c in enumerate(band):
                fig.line("M%s %s C%s %s %s %s" % tuple(map(f, (16.6, 96 + k * 2.2, 36, 100 + k * 2.2, 56.2, 96 + k * 2.2))), c, 1.4)
            fig.line(d, shade(shawl, OUTLINE), LW)
    return draw


def top_agbada(color, embroidery, inner):
    """Nigerian agbada: very wide robe with the sides folded onto the shoulders, embroidered neck; over a buba."""
    def draw(fig, ch, view):
        b = BUILD[ch["build"]]
        upper(fig, ch, view, inner, role="o", sleeve="long", hem=124, cuff=None)
        fig.at(52)
        d = ("M8.6 72 C10 66 20 62.4 30 62.4 L42 62.4 C52 62.4 62 66 63.4 72 C64 92 63 120 61.6 %s Q36 %s 10.4 %s "
             "C9 120 8 92 8.6 72Z" % (f(170), f(174), f(170)))
        fig.shape(d, color, role="top", shadow=["M0 0 L16 0 L18 200 L0 200Z", "M27 58 C33 66.6 39 66.6 46 58 L46 56 L27 56Z"],
                  hi=["M12 68.6 C18 64.6 26 63.4 31 63.6 C25 64.8 18 66.6 13.6 70Z"])
        fig.line("M17.4 80 C18 110 18.6 140 19.4 168", shade(color, 0.76), 0.8)
        fig.line("M54.8 80 C55 110 54.8 140 54 168", shade(color, 0.76), 0.8)
        if view == "front":
            fig.line("M31 63.0 C33 67 39 67.2 41.4 63.0", embroidery, 1.4)
            emb = "M31.6 66.6 C33 72 38 72.4 40.6 66.6 L43.6 70 L42.6 92 C40 96 36 96 33.6 92 L32 76Z"
            fig.shape(emb, shade(color, 1.08), role="top", lw=0.8, lc=embroidery)
            for y in frange(72, 92, 3.6):
                fig.line("M34.6 %s Q38 %s 41.6 %s" % (f(y), f(y + 1.6), f(y)), embroidery, 0.8)
            fig.line("M38 92.4 L38 100", embroidery, 0.9)
        else:
            fig.line("M30.0 62.2 C34 60.8 38 60.8 42.0 62.2", embroidery, 1.4)
        fig.line(d, shade(color, OUTLINE), LW)
        # hands peek out at the folded edges
        fig.at(53)
        for side in ("n", "f"):
            x, y = hand_xy(b, side)
            fig.shape(ell(x + (-3 if side == "n" else 3), 150, b["hand"] * 0.9), ch["skin"], sc=skin_tones(ch["skin"])["sh"],
                      shadow=[P((0, 140), (x + (-3.6 if side == "n" else 2.6), 140), (x + (-3.6 if side == "n" else 2.6), 160), (0, 160))]) \
                if False else None
    return draw


def top_manteau(color, hem=146.0, belt_c=None):
    """Iranian manteau: a light long coat with buttons, worn with trousers."""
    def draw(fig, ch, view):
        def det(fig, ch, view, b):
            if view == "front":
                band_collar(fig, color, h=2.8)
                fig.line("M38.8 66 L40.2 %s" % f(hem), shade(color, 0.66), 0.9)
                for k in range(6):
                    fig.fill(ell(41.4, 70 + k * 12.6, 0.8), shade(color, 0.58))
                fig.line("M21.4 %s L22.6 %s" % (f(hem), f(hem - 14)), shade(color, 0.7), 0.8)
                fig.line("M53.6 %s L52.6 %s" % (f(hem), f(hem - 14)), shade(color, 0.7), 0.8)
            else:
                band_collar(fig, color, y=60.8, h=2.8)
                fig.line("M36.6 104 L37 %s" % f(hem), shade(color, 0.7), 0.8)
            if belt_c:
                fig.shape(P((22.6, 101), (49.4, 101), (49.4, 103.8), (22.6, 103.8)), belt_c, lw=0.8)
        upper(fig, ch, view, color, sleeve="long", hem=hem, flare=4.0, details=det, cuff=None)
    return draw


def overlay_kente(colors):
    """Kente stole: two woven strips hanging from the neck down the front (a V across the back)."""
    gold, green, red, dark = colors
    def draw(fig, ch, view):
        fig.at(56)
        if view == "front":
            for pts in (((30.4, 62.0), (34.4, 62.6), (33.6, 110), (28.2, 110)), ((41.6, 62.0), (45.2, 63.4), (46.8, 110), (41.4, 110))):
                d = P(*pts)
                fig.shape(d, gold, lw=0.9, lc=shade(gold, 0.55))
                (x0, y0), (x1, _), (x2, y2), (x3, _) = pts
                inner = ""
                for k, y in enumerate(frange(66, 110, 6.4)):
                    c = (green, red, dark, red)[k % 4]
                    inner += '<rect x="0" y="%s" width="72" height="2.8" fill="%s"/>' % (f(y), c)
                    inner += '<rect x="0" y="%s" width="72" height="0.7" fill="%s"/>' % (f(y + 3.8), dark)
                clip_fill(fig, d, inner)
                fig.line(d, shade(gold, 0.55), 0.9)
                fig.line("M%s 110.4 L%s 112.6 M%s 110.4 L%s 112.6 M%s 110.4 L%s 112.6" % tuple(map(f, (
                    x3 + 1, x3 + 1, (x2 + x3) / 2, (x2 + x3) / 2, x2 - 1, x2 - 1))), gold, 0.8)
        else:
            d = "M22 66 C26 62 32 61 36 61 C40 61 46 62 50 66 L44 70 C40 66.6 32 66.6 28 70Z"
            fig.shape(d, gold, lw=0.9, lc=shade(gold, 0.55))
            fig.line("M24 66.6 C30 63.2 42 63.2 48 66.6", red, 1.0)
    return draw


def overlay_dupatta(color, trim=None):
    """Dupatta draped around the neck with both ends falling behind the shoulders."""
    def draw(fig, ch, view):
        tc = trim or shade(color, 0.7)
        fig.at(54)
        if view == "front":
            d = ("M19.4 66.4 C22 70 26 74 31 76 C35 77.6 41 77.6 46 75 C49.6 73 52 70 53.4 66.6 C55 68 56.4 70 56.6 72 "
                 "C55 76 51 80 46 82 C40 84.4 33 84 27.6 82 C23 80 19.4 76 18 72 C18 70 18.6 68 19.4 66.4Z")
            fig.shape(d, color, shadow=["M0 0 L24 0 L24 100 L0 100Z"], hi=["M24 72.6 C30 77 40 78 46 75.6 C40 79 30 78.6 24 72.6Z"])
            fig.line("M18 72 C19.4 76 23 80 27.6 82 C33 84 40 84.4 46 82 C51 80 55 76 56.6 72", tc, 1.0)
            # end falling behind the far shoulder
            fig.at(12)
            fig.shape("M50 66 C55 68 58.6 72 58.8 80 L58.4 118 L52.4 118 L52.6 78Z", color, shadow=["M0 0 L72 0 L72 200 L0 200Z"])
        else:
            fig.at(57)
            d = "M17.6 68 C22 63.4 30 62.4 36 62.6 C42 62.4 50 63.4 54.4 68 L53 112 C48 114 42 114 38 112 L36 76 L33 112 C28 114 22 114 19 112Z"
            fig.shape(d, color, shadow=["M0 0 L22 0 L22 120 L0 120Z"])
            fig.line("M19 112 C22 114 28 114 33 112 M38 112 C42 114 48 114 53 112", tc, 1.2)
    return draw


def overlay_netela(color, border):
    """Netela: light cotton shawl over the shoulders with a woven border."""
    def draw(fig, ch, view):
        fig.at(54)
        if view == "front":
            d = ("M17.6 67 C22 62.6 30 61.6 32 62.6 C30 70 30 80 31.6 90 L25 96 C20 92 16.6 84 16.4 76 C16.4 72 16.8 69 17.6 67Z")
            fig.shape(d, color, shadow=["M0 0 L21 0 L21 100 L0 100Z"], lc="#a9a294")
            fig.line("M31.6 90 L25 96", border[0], 1.4)
            d2 = "M41 62.6 C46 62.4 52 64 54.6 67.4 C56.4 74 56.4 84 55.4 92 L49.6 90 C49.2 82 46 72 41 62.6Z"
            fig.shape(d2, color, lc="#a9a294")
            fig.line("M49.6 90 L55.4 92", border[0], 1.4)
        else:
            d = "M17.4 66 C22 61 30 60 36 60.2 C43 60 50 61 55 66 C57 80 56.6 94 55 104 C46 108 26 108 17.6 104 C16 94 15.4 80 17.4 66Z"
            fig.shape(d, color, shadow=["M0 0 L21 0 L21 120 L0 120Z"], lc="#a9a294")
            fig.line("M17.8 100.6 C26 104.6 46 104.6 54.8 100.6", border[0], 1.6)
            fig.line("M17.8 98 C26 102 46 102 54.8 98", border[1], 0.8)
    return draw


# ----------------------------------------------------------------------------------------------- hair
# Every hair part is drawn in tones of one hue (base, shadow x0.8, highlight) so the page can recolor it.
def hair_tones(c):
    return dict(base=c, sh=shade(c, 0.8), hi=shade(c, 1.24))


def hshape(fig, d, c, shadow=(), hi=(), role="hair", lw=LW):
    t = hair_tones(c)
    fig.shape(d, c, role=role, shadow=shadow, hi=hi, sc=t["sh"], hc=t["hi"], lw=lw)


HI_TOP = "M20.4 13.4 C25.6 8.0 31.6 6.2 38.4 6.4 C32.6 8.6 27.6 11.2 23.8 15.8Z"
HI_REAR = "M25 10.4 C31 6.4 40 6.0 46.4 8.6 C40 8.6 32 9.8 27.4 12.8Z"
SH_BACK = "M6 20 C12 30 16 36 22.4 38.6 L22.4 48 L6 48Z"
REAR_SHORT = ("M15.4 40.6 C11.2 31 12 18 20.2 10.6 C25.8 5.8 31.2 %(t)s 37 %(t)s C47.2 %(t)s 56 9.4 59 19.6 "
              "C61.2 27.6 60.2 37.2 56.4 45.4 C53.4 51.6 48.2 55.2 42.6 55.8 C38 56.2 33 55.4 29.6 53.8 "
              "C26 52.2 23.6 48.4 22.8 44.4 C22.2 41 21 39.2 18.6 39Z")


def rear_short(fig, c, top=3.2, lines=True):
    fig.at(64, head=True)
    d = REAR_SHORT % {"t": f(top)}
    hshape(fig, d, c, shadow=["M6 30 C14 40 18 46 24 56 L6 60Z", "M28 52 C38 55.4 46 54.6 55 47.6 L58 58 L26 58Z"], hi=[HI_REAR])
    if lines:
        t = hair_tones(c)
        fig.line("M41 18 C45 26 48.4 34 49.4 42", t["sh"], 0.8, op=0.85)
        fig.line("M33 14 C34 22 34 30 33 36", t["sh"], 0.8, op=0.6)


def hair_short(fig, ch, view, c, style="short"):
    """Men's short styles: short (textured), side (side part), slick (combed back), crop (close), wavy."""
    t = hair_tones(c)
    if view == "rear":
        rear_short(fig, c, top={"crop": 5.0, "wavy": 2.2}.get(style, 3.2), lines=style != "crop")
        if style == "crop":
            for x, y in ((30, 16), (40, 14), (48, 24), (36, 30), (26, 28), (44, 40), (52, 36)):
                fig.line("M%s %s q1.2 -1.2 2.4 0" % (f(x), f(y)), t["sh"], 0.7)
        return
    fig.at(64, head=True)
    if style == "short":
        d = ("M13.8 39.4 C10.4 30 10.8 18 19 10.4 C24.6 5.4 30.6 3.2 37 3.2 C46.6 3.2 55 8.2 58.8 16.6 C60.6 20.6 61 26.6 59.4 32.4 "
             "L57.2 27.6 L55.6 30.6 C54.4 26 52 23.2 48.4 21.6 L47 24.6 L44.2 21 C39.4 20.8 34.4 21.8 30.4 24 L30 27.4 L27.2 25.4 "
             "C24 28.2 22 32.6 21.6 38 L18.2 39.4Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
    elif style == "side":
        d = ("M13.8 39.4 C10.4 30 10.8 18 19 10.4 C24.6 5.4 30.6 3 37.4 3 C47 3 55.4 8.4 59 17.4 C60.4 21 60.6 26.4 59.4 31.6 "
             "C58.2 26.4 55.2 22 49.6 19.8 C43.4 17.8 35 18.2 29.8 20.6 C25 23.6 22.2 29.6 21.8 37.6 L18.2 39.4Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=["M31 11 C38 7.4 47 7.6 53 11.6 C46 10.6 38 10.8 33 13Z"])
        fig.line("M29.8 20.6 C28.4 15 30 10 33.4 6.4", t["sh"], 0.9)
    elif style == "slick":
        d = ("M13.8 39 C10.4 30 10.8 18 19 10.4 C24.6 5.4 30.6 3 37.4 3 C47 3 55.4 8.4 59 17.4 C59.8 19.6 60 22.4 59.6 25 "
             "C57.2 20.8 52.2 17.6 45.2 17 C37.2 16.6 29.6 19 25 24.2 C22.8 27.4 21.8 32.4 21.6 37.6 L18.2 39Z")
        hshape(fig, d, c, shadow=[SH_BACK])
        fig.line("M50 15 C42 10.6 31 10 21 15", t["hi"], 0.9)
        fig.line("M54 18.6 C45 14 32 14 19.6 21", t["hi"], 0.7, op=0.8)
    elif style == "crop":
        d = ("M14.4 38.4 C12 30 12.4 18.6 19.8 11.6 C25 6.8 30.6 5.2 36.6 5.2 C45.8 5.2 53.8 9.8 57.2 17.4 C58.6 20.8 58.8 25 58 29 "
             "L55.8 25 C52.6 22.2 46 20.8 38.6 21 C32 21.2 26.4 22.8 23.6 25.6 C22 28.4 21.8 33 21.8 37 L18.4 38.6Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
        for x, y in ((28, 12), (36, 9.6), (44, 11), (24, 19), (33, 17), (50, 16), (18, 27)):
            fig.line("M%s %s q1.2 -1.2 2.4 0" % (f(x), f(y)), t["sh"], 0.7)
    elif style == "wavy":
        d = ("M13.6 40 C9.6 30 10 17 18.6 9.6 C24.4 4.4 30.6 2.2 37.4 2.2 C47.6 2.2 56.4 8 60 17.6 C61.6 22 61.6 28 60.2 34 "
             "C58.6 30 56.6 27.4 54 26 C53.6 22.8 51 20.6 47.4 20.6 C44.6 23.4 40 24 36.6 22.6 C33.4 25 28.6 26 25.6 26.4 "
             "C23 29 22 33 21.8 38.4 L18 40Z")
        hshape(fig, d, c, shadow=[SH_BACK, "M36.6 22.6 C40 24 44.6 23.4 47.4 20.6 L47.4 23 C44 25.6 40 25.6 36.6 24Z"], hi=[HI_TOP])
        fig.line("M44 9 C48 12 50 16 50.4 20", t["sh"], 0.8)


def hair_bald(fig, ch, view, c):
    """Receding top with short hair at the sides and back (older men)."""
    t = hair_tones(c)
    fig.at(64, head=True)
    if view == "front":
        d = "M13.6 40 C11 32 11.4 24 14.6 17.6 C17 22 19.4 26 22.6 28.4 C22 31 21.8 34.6 21.8 38.4 L18.2 40Z"
        hshape(fig, d, c, shadow=[SH_BACK])
        fig.shape("M57.4 22.6 C59 25 59.4 28 59 31.4 L56.6 28.6Z", c, role="hair", lw=0.8, lc=shade(c, OUTLINE))
    else:
        d = ("M15.4 40.6 C12 32 12.4 24 15.4 18 C22 22 30 23.6 38 23.6 C46 23.6 53 21.6 58.4 18.6 C61 26 60.4 37 56.4 45.4 "
             "C53.4 51.6 48.2 55.2 42.6 55.8 C38 56.2 33 55.4 29.6 53.8 C26 52.2 23.6 48.4 22.8 44.4 C22.2 41 21 39.2 18.6 39Z")
        hshape(fig, d, c, shadow=["M28 52 C38 55.4 46 54.6 55 47.6 L58 58 L26 58Z"])


def hair_long(fig, ch, view, c, length=98.0, bangs="curtain", part=None):
    """Long straight hair: a mass behind the shoulders, a cap framing the face, one lock in front of the far shoulder."""
    t = hair_tones(c)
    L = length
    if view == "front":
        fig.at(8, head=True)
        back = ("M36 3.6 C22 3.6 10.4 13.6 10.4 30 C10.4 50 11.6 %s 14.6 %s C24 %s 48 %s 57.6 %s C60.6 %s 61.8 50 61.6 30 "
                "C61.6 13.6 50 3.6 36 3.6Z" % tuple(map(f, (L - 22, L - 2, L + 2.4, L + 2.4, L - 2, L - 22))))
        hshape(fig, back, c, shadow=[P((0, 0), (72, 0), (72, 200), (0, 200))])
        fig.at(64, head=True)
        if bangs == "curtain":
            d = ("M13.4 58 C10.4 42 10.6 22 19.2 11.8 C24.8 5.8 31.2 3.6 37.4 3.6 C47.6 3.6 55.8 9.8 59 19.4 C61 26 61.4 36 60.8 46 "
                 "L60.4 60 C59 62.2 56.8 62.2 55.8 60 L56.4 44 C56.6 34 55.6 27.6 52.2 23.6 C49.6 21 46.2 20 43.6 19.6 "
                 "C40.8 22 36.2 24.6 30.8 26 C25.6 27.6 22.6 32 21.8 39 L21.4 54 C20 58 15.8 59.6 13.4 58Z")
            shd = ["M8 30 L22.2 34 L22.2 64 L8 64Z", "M43.6 19.6 C47 21 51 22.6 53.2 25 L56.6 34 L56.8 62 L54 62 L54 30Z"]
        elif bangs == "straight":
            d = ("M13.2 58 C10 42 10.6 22 19.4 12 C25 6 31.4 3.6 37.4 3.6 C47.6 3.6 55.8 10 59 19.6 C61 26 61.4 36 61 46 "
                 "L60.8 60 C59.2 62 56.8 62 56 60 L56.2 36 L56 28.6 C49 29.8 40 29.8 30 28.8 L24.6 28.2 C22.4 32 21.6 38 21.4 44 "
                 "L21 54 C19.4 58 15.6 59.6 13.2 58Z")
            shd = ["M8 30 L21.8 34 L21.8 62 L8 62Z", "M24 26 L57 26 L57 29.6 L24 29.6Z"]
        else:  # centre part, no fringe
            d = ("M13.4 58 C10.4 42 10.6 22 19.2 11.8 C24.8 5.8 31.2 3.6 37.4 3.6 C47.6 3.6 55.8 9.8 59 19.4 C61 26 61.4 36 60.8 46 "
                 "L60.4 60 C59 62.2 56.8 62.2 55.8 60 L56.4 44 C56.6 34 55.4 26 50.6 21 C47.6 18.4 44 17.6 41 17.4 "
                 "C36 17.6 30 19.6 26.4 23.6 C23.4 27 22 33 21.8 39 L21.4 54 C20 58 15.8 59.6 13.4 58Z")
            shd = ["M8 30 L22.2 34 L22.2 64 L8 64Z"]
            fig.line("M41 17.4 C40.4 13 40 8.6 38.6 4.6", t["sh"], 0.9)
        hshape(fig, d, c, shadow=shd, hi=[HI_TOP])
        # lock in front of the far shoulder
        fig.at(79, head=True)
        lock = ("M55.8 56 C58 54.6 60.6 55 61.2 57.4 C62.6 66 62.4 %s 60.6 %s C59.4 %s 57.6 %s 56.6 %s C55.4 %s 55.2 66 55.8 56Z" % tuple(map(f, (
            L - 14, L - 6, L - 4, L - 4.4, L - 6.6, L - 14))))
        hshape(fig, lock, c, shadow=["M50 50 L58 50 L58 120 L50 120Z"])
    else:
        fig.at(80, head=True)
        d = ("M36 3.6 C22 3.6 11 13.6 11 30 C10.6 44 12.6 54 17.6 62 C18.6 74 18.8 %s 19.6 %s C28 %s 46 %s 53.6 %s "
             "C54.4 %s 54.4 74 55.2 62 C59.8 54 61.4 44 61 30 C61 13.6 50 3.6 36 3.6Z" % tuple(map(f, (
                 L - 12, L - 2, L + 2.6, L + 2.6, L - 2, L - 12))))
        hshape(fig, d, c, shadow=["M0 0 L21 0 C19 30 20 70 23 130 L0 130Z", "M0 %s L72 %s L72 140 L0 140Z" % (f(L - 4), f(L - 4))],
               hi=[HI_REAR])
        fig.line("M38 14 C41 30 42 60 43 %s" % f(L - 6), t["sh"], 0.8, op=0.8)
        fig.line("M29 18 C27 36 27 64 28.6 %s" % f(L - 8), t["sh"], 0.8, op=0.6)


def hair_bob(fig, ch, view, c, bangs="straight"):
    t = hair_tones(c)
    if view == "front":
        fig.at(8, head=True)
        hshape(fig, "M12 40 C11 50 12 58 16 62 L30 62 L30 40Z", c, shadow=[P((0, 0), (72, 0), (72, 200), (0, 200))])
        fig.at(64, head=True)
        d = ("M12.4 58.6 C9 44 9.6 22 18.8 11.6 C24.6 5.6 31.2 3.4 37.6 3.4 C47.8 3.4 56 9.8 59.4 19.8 C61.4 26 61.8 36 61.2 46 "
             "L60.6 56.6 C60 59.8 57.4 61 55.6 59.2 L56.4 44 C56.6 36 56.4 31 55.6 27.6 C48.2 29.4 38.8 29.6 29.8 28.4 "
             "L23.8 27.8 C22.2 31.6 21.6 37.6 21.4 44 L21.4 56 C19.4 60.4 14.6 61 12.4 58.6Z")
        hshape(fig, d, c, shadow=["M8 30 L21.6 34 L21.6 64 L8 64Z", "M23 26 L57 26 L57 29.8 L23 29.8Z"], hi=[HI_TOP])
        fig.line("M33 28.6 L33.6 25.4 M42 29 L42.2 25.8 M50 28.6 L50.6 25.6", t["sh"], 0.7)
    else:
        fig.at(64, head=True)
        d = ("M36 3.4 C22 3.4 10.6 13 10.6 30 C10.6 42 11.6 52 14 59.6 C22 62.6 50 62.6 58 59.6 C60.4 52 61.4 42 61.4 30 "
             "C61.4 13 50 3.4 36 3.4Z")
        hshape(fig, d, c, shadow=["M0 0 L20 0 C18 20 18 40 22 64 L0 64Z", "M0 57.4 L72 57.4 L72 70 L0 70Z"], hi=[HI_REAR])
        fig.line("M38 14 C41 26 42 42 42.6 58", t["sh"], 0.8, op=0.8)
        fig.line("M28 16 C26 30 26 46 27 58", t["sh"], 0.8, op=0.6)


def hair_bun(fig, ch, view, c, where="top", pin=None, flowers=None):
    """Hair pulled back into a bun: where='top' (back of the crown, with a hairpin) or 'low' (at the nape)."""
    t = hair_tones(c)
    if view == "front":
        fig.at(58, head=True)
        if where == "top":
            hshape(fig, ell(16.4, 15.6, 7.4, 7.0), c, shadow=["M4 14 C10 20 16 22 24 22 L24 30 L4 30Z"],
                   hi=["M11.6 12 C13 9.6 16 8.6 18.6 9C16 10 14 11.6 13 13.6Z"])
            fig.line("M11 12.6 C14 14 17.6 17.6 19.4 21.4", t["sh"], 0.8)
            if pin:
                fig.at(57, head=True)
                fig.line("M7.4 9.4 L25.6 21.8", pin, 1.3)
                fig.at(58.5, head=True)
                fig.shape(ell(7.6, 9.4, 1.6), shade(pin, 1.1) if pin != "#ffffff" else pin, lw=0.7, lc=shade(pin, 0.6))
        else:
            hshape(fig, ell(13.6, 51.6, 6.6, 6.4), c, shadow=["M4 50 L20 50 L20 60 L4 60Z"])
            if flowers:
                for a in (200, 235, 270):
                    x, y = 13.6 + 6.8 * math.cos(math.radians(a)), 51.6 + 6.6 * math.sin(math.radians(a))
                    fig.shape(ell(x, y, 1.3), flowers, lw=0.6, lc=shade(flowers, 0.7))
        fig.at(64, head=True)
        d = ("M13.8 42 C10.6 32 11 18.6 19.2 10.8 C24.8 5.8 31 3.8 37.4 3.8 C47.2 3.8 55.6 9.2 59.2 18.2 C60.6 22 60.8 27 59.6 32.6 "
             "C58.4 27.6 56 24 52.6 21.6 C47.6 18.6 41 18 36 19 C30.6 20 26 22.8 23.4 27 C22 30 21.4 34 21.2 38.6 L18.6 42Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
        fig.line("M36 19 C33 15 30 13 26 12.4", t["sh"], 0.8)
        fig.line("M44 18.6 C41 14 37 11 32 9.6", t["sh"], 0.8, op=0.8)
    else:
        fig.at(64, head=True)
        d = ("M15.4 41 C11.2 31 12 18 20.2 10.6 C25.8 5.8 31.2 3.6 37 3.6 C47.2 3.6 56 9.4 59 19.6 C61.2 27.6 60.2 37.2 56.4 45.4 "
             "C53.4 51.6 48.2 55.2 42.6 55.8 C38 56.2 33 55.4 29.6 53.8 C26 52.2 23.6 48.4 22.8 44.4 C22.2 41 21 39.2 18.6 39Z")
        hshape(fig, d, c, shadow=["M6 30 C14 40 18 46 24 56 L6 60Z"], hi=[HI_REAR])
        fig.line("M30 52 C32 40 33 26 35 12", t["sh"], 0.8, op=0.7)
        fig.line("M44 52 C42 40 40 26 37 12", t["sh"], 0.8, op=0.7)
        fig.at(66, head=True)
        if where == "top":
            if pin:
                fig.line("M24.4 7.6 L46.4 17.2", pin, 1.3)
            hshape(fig, ell(35.6, 12.4, 8.2, 7.4), c, shadow=["M20 12 C26 18 34 20 44 18 L44 30 L20 30Z"],
                   hi=["M30 8 C32 6 36 5.4 39 6.2 C36 6.8 33.4 7.8 31.6 9.6Z"])
            fig.line("M29.6 9.4 C33 12 38 13.4 42 12.6", t["sh"], 0.8)
            if pin:
                fig.at(67, head=True)
                fig.line("M43.4 15.9 L46.6 17.3", pin, 1.3)
                fig.shape(ell(24.2, 7.6, 1.6), shade(pin, 1.1) if pin != "#ffffff" else pin, lw=0.7, lc=shade(pin, 0.6))
        else:
            hshape(fig, ell(36.4, 51.2, 8.4, 7.6), c, shadow=["M24 52 C30 58 40 60 48 56 L48 64 L24 64Z"],
                   hi=["M30.4 47 C32.6 45 36 44.2 39 44.8 C36 45.6 33.4 46.6 31.8 48.6Z"])
            fig.line("M30 49 C33 52 38 53.4 43 52", t["sh"], 0.8)
            if flowers:
                for a in range(180, 361, 30):
                    x, y = 36.4 + 9.2 * math.cos(math.radians(a)), 51.2 + 8.4 * math.sin(math.radians(a))
                    fig.shape(ell(x, y, 1.35), flowers, lw=0.6, lc=shade(flowers, 0.7))


def hair_ponytail(fig, ch, view, c, tie_c="#e86a6a"):
    t = hair_tones(c)
    if view == "front":
        fig.at(9, head=True)
        d = "M15 24 C8 30 6.4 44 8.4 58 C9.4 66 11 74 13.4 80 C16 74 17.4 64 17.6 56 C18 46 18.6 36 20 28Z"
        hshape(fig, d, c, shadow=["M0 0 L12 0 L12 90 L0 90Z"])
        fig.at(58, head=True)
        fig.shape(ell(16.4, 25.4, 2.6, 3.2), tie_c, lw=0.8)
        fig.at(64, head=True)
        d = ("M14 40 C10.8 31 11.2 18.6 19.2 10.8 C24.8 5.8 31 3.8 37.4 3.8 C47.2 3.8 55.6 9.2 59.2 18.2 C60.8 22.4 61 28 59.8 33.6 "
             "C58.8 28.4 56.4 24.6 53 22.4 L51.6 25.4 L49.4 21.6 C44 19.4 37 19.8 31.6 21.6 C27 23.2 23.6 26.8 22.4 31.4 "
             "C21.8 34 21.6 36.6 21.6 39 L18.4 40.6Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
        fig.line("M30 21.6 C27 18 23 16 18.6 16", t["sh"], 0.8)
    else:
        fig.at(64, head=True)
        d = ("M15.4 41 C11.2 31 12 18 20.2 10.6 C25.8 5.8 31.2 3.6 37 3.6 C47.2 3.6 56 9.4 59 19.6 C61.2 27.6 60.2 37.2 56.4 45.4 "
             "C53.4 51.6 48.2 55.2 42.6 55.8 C38 56.2 33 55.4 29.6 53.8 C26 52.2 23.6 48.4 22.8 44.4 C22.2 41 21 39.2 18.6 39Z")
        hshape(fig, d, c, shadow=["M6 30 C14 40 18 46 24 56 L6 60Z"], hi=[HI_REAR])
        for x0 in (26, 46):
            fig.line("M%s 44 C%s 36 %s 30 37 24" % (f(x0), f(x0 + (4 if x0 < 37 else -4)), f(x0 + (6 if x0 < 37 else -6))),
                     t["sh"], 0.8, op=0.8)
        fig.at(81, head=True)
        d = "M33 26 C30 36 30 52 31.6 66 C32.6 76 34.6 84 37 88 C39.4 82 41.2 74 41.4 64 C41.6 50 41 36 39.6 26Z"
        hshape(fig, d, c, shadow=["M0 0 L34 0 L34 100 L0 100Z"], hi=["M36.6 30 C37.6 40 37.8 54 37.2 66 L36.4 66 C36.6 54 36.4 40 35.8 30Z"])
        fig.shape(rect(32.4, 23.2, 7.8, 4.0, 1.6), tie_c, lw=0.8)


def braid_d(x0, y0, x1, y1, w, n):
    """A braid as a chain of overlapping lobes from (x0,y0) to (x1,y1)."""
    out = []
    for k in range(n):
        tk = (k + 0.5) / n
        cx, cy = lerp(x0, x1, tk), lerp(y0, y1, tk)
        seg = math.hypot(x1 - x0, y1 - y0) / n
        out.append((cx, cy, w / 2 * (1 - 0.18 * tk), seg * 0.66))
    return out


def hair_braids(fig, ch, view, c, length=104.0, front=True, tie_c=None, tassel=None):
    """Two braids from a centre part.  front=True: over both shoulders; False: hanging down the back."""
    t = hair_tones(c)
    tc = tie_c or shade(c, 0.6)
    def draw_braid(x0, y0, x1, y1, w=6.2, n=8):
        for cx, cy, rx, ry in braid_d(x0, y0, x1, y1, w, n):
            hshape(fig, ell(cx, cy, rx, ry), c, shadow=[P((cx - 9, cy - 9), (cx - rx * 0.3, cy - 9), (cx - rx * 0.3, cy + 9), (cx - 9, cy + 9))],
                   lw=0.95)
        fig.shape(rect(x1 - 2.6, y1 - 1.2, 5.2, 2.6, 1.0), tc, lw=0.7)
        if tassel:
            fig.shape("M%s %s L%s %s L%s %s L%s %s Z" % tuple(map(f, (x1 - 1.8, y1 + 1.4, x1 + 1.8, y1 + 1.4, x1 + 2.6, y1 + 8, x1 - 2.6, y1 + 8))),
                      tassel, lw=0.8)
        else:
            hshape(fig, "M%s %s L%s %s L%s %s Z" % tuple(map(f, (x1 - 2.2, y1 + 1.4, x1 + 2.2, y1 + 1.4, x1, y1 + 6))), c, lw=0.8)
    if view == "front":
        fig.at(64, head=True)
        d = ("M14.4 44 C10.8 33 11 18.6 19.2 10.8 C24.8 5.8 31 3.8 37.4 3.8 C47.2 3.8 55.6 9.2 59.2 18.2 C60.8 22.4 61.2 30 60.4 38 "
             "L57.4 42 C57.4 34 56 26 51.4 21.2 C47.6 17.8 42 16.8 40.6 17 C35.6 17.6 30 19.6 26.4 23.6 C23.4 27 22 33 21.8 38.6 L19 44Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
        fig.line("M40.6 17 C40 12.6 39.6 8.4 38.4 4.4", t["sh"], 0.9)
        if front:
            fig.at(79, head=False)
            draw_braid(18.0, 50, 19.6, length)
            draw_braid(58.0, 48, 55.6, length - 4)
        else:
            fig.at(9, head=False)
            draw_braid(16.0, 50, 14.4, length, n=9)
    else:
        fig.at(64, head=True)
        d = ("M15.4 44 C11.2 31 12 18 20.2 10.6 C25.8 5.8 31.2 3.6 37 3.6 C47.2 3.6 56 9.4 59 19.6 C61.2 27.6 60.4 38 57.4 46 "
             "C52 52 44 54 36.4 54 C30 54 24 52 20.4 48Z")
        hshape(fig, d, c, shadow=["M6 30 C14 40 18 46 24 56 L6 60Z"], hi=[HI_REAR])
        fig.line("M38 6 C37.4 20 37 36 36.6 53", t["sh"], 0.9)
        if front:
            fig.at(81, head=False)
            draw_braid(20.4, 50, 15.6, 72, w=6.0, n=3)
            draw_braid(53.4, 50, 57.0, 72, w=6.0, n=3)
        else:
            fig.at(81, head=False)
            draw_braid(25.6, 50, 27.6, length, n=9)
            draw_braid(47.4, 50, 45.4, length, n=9)


def curl_ring(cx, cy, rx, ry, a0, a1, n, amp=1.5):
    return bumps(arc_pts(cx, cy, rx, ry, a0, a1, n), amp=amp)


def hair_curly(fig, ch, view, c, length=84.0, volume=1.0, tips=None):
    """Voluminous curls to the shoulders."""
    t = hair_tones(c)
    L = length
    v = volume
    if view == "front":
        fig.at(8, head=True)
        left = [(36 - 29.6 * v, y) for y in (40, 54, 68)] + [(12, L - 4)]
        bot = [(22, L + 2), (36, L + 3), (50, L + 2), (60, L - 4)]
        right = [(36 + 29.6 * v, y) for y in (68, 54, 40)]
        outline = [(36 - 29 * v, 30)] + left + bot + right + [(36 + 29 * v, 30)] + list(reversed(arc_pts(36, 30, 29 * v, 26.4, 180, 360, 12)))[1:-1]
        d = bumps(outline[::-1], amp=1.7, closed=True)
        hshape(fig, d, c, shadow=[P((0, 0), (72, 0), (72, 200), (0, 200))], hi=[])
        if tips:
            for x, y in ((14, L - 10), (22, L - 2), (50, L - 2), (58, L - 10), (10, 60), (62, 58)):
                fig.fill(ell(x, y, 3.0, 2.4), tips, op=0.9)
        fig.at(64, head=True)
        d = ("M12.6 50 C9 40 9.4 24 16 14.4 C21.6 6.6 29 3 37 3 C48 3 57 9.4 60.4 19.8 C62.4 27 62.6 38 61.4 50 "
             "C60 56 57 58 55.4 54 C56.8 44 56.4 34 53 27.6 C51.6 25.6 49.4 24.6 47.4 25.2 C46.6 27.6 44 28.4 42 27.2 "
             "C40.6 29.6 37.4 30.2 35.4 28.6 C33.6 31 30 31.4 28.2 29.4 C26 31 23.6 31.4 22.6 34 C21.8 38 21.6 44 21.4 50 "
             "C19.6 54 14.4 54.6 12.6 50Z")
        hshape(fig, d, c, shadow=["M6 30 L22 34 L22 60 L6 60Z"], hi=[HI_TOP])
        for x, y, a in ((30, 12, 0), (42, 10, 0), (52, 16, 1), (20, 22, 1), (24, 42, 1), (57, 42, 0)):
            fig.line("M%s %s a2.2 2.2 0 1 %d 3.4 1.2" % (f(x), f(y), a), t["sh"], 0.8)
        # front curls over the far shoulder
        fig.at(79, head=True)
        lk = bumps([(55.6, 52), (60.6, 60), (61.2, 70), (58.6, L - 6), (54.6, 70), (54.6, 60)], amp=1.2, closed=True)
        hshape(fig, lk, c, shadow=["M50 50 L57 50 L57 120 L50 120Z"])
    else:
        fig.at(80, head=True)
        outline = arc_pts(36, 30, 29 * v, 26.4, 180, 360, 12) + [(36 + 29.4 * v, 40), (36 + 28 * v, 56), (59, L - 6),
                                                                              (48, L + 2), (36, L + 3), (24, L + 2), (13, L - 6),
                                                                              (36 - 28 * v, 56), (36 - 29.4 * v, 40)]
        d = bumps(outline, amp=1.7, closed=True)
        hshape(fig, d, c, shadow=["M0 0 L20 0 C16 30 16 70 22 130 L0 130Z"], hi=[HI_REAR])
        for x, y, a in ((30, 14, 0), (42, 12, 0), (50, 22, 1), (24, 26, 1), (36, 34, 0), (46, 42, 1), (28, 48, 0), (40, 60, 1),
                        (24, 66, 0), (48, 70, 1), (34, 76, 0)):
            fig.line("M%s %s a2.4 2.4 0 1 %d 3.6 1.2" % (f(x), f(y), a), t["sh"], 0.8)
        if tips:
            for x, y in ((18, L - 8), (28, L - 1), (44, L - 1), (54, L - 8)):
                fig.fill(ell(x, y, 3.2, 2.4), tips, op=0.9)


def hair_afro(fig, ch, view, c, r=29.0):
    t = hair_tones(c)
    cy = 27.0
    ring = arc_pts(36, cy, r, r * 0.9, 0, 360, 22)[:-1]
    d = bumps(ring, amp=1.6, closed=True)
    if view == "front":
        fig.at(8, head=True)
        hshape(fig, d, c, shadow=["M0 30 C10 50 24 62 40 70 L0 70Z"], hi=["M14 18 C18 9 27 3.6 36 3.4 C28 6.6 21 12 17.4 20Z"])
        for x, y, a in ((20, 14, 0), (30, 7, 1), (44, 6.6, 0), (54, 13, 1), (60, 26, 0), (12, 30, 1), (14, 44, 0), (58, 42, 1)):
            fig.line("M%s %s a2.2 2.2 0 1 %d 3.4 1" % (f(x), f(y), a), t["sh"], 0.8)
        fig.at(64, head=True)
        edge = ("M13 40 C12 34 12.6 28 15 24 C19 21.6 24 21 27.6 21.4 C32 19.6 38 19 43 19.6 C48 20.4 53 21.4 56.6 23.4 "
                "C58.6 27 59 31 58.6 34 C57.6 30 55.6 27 53 26 C46 24.4 36 24.4 30 26 C25.4 27.4 22.6 31 22 36 L21.8 40 L18 41Z")
        hshape(fig, edge, c, shadow=[SH_BACK])
    else:
        fig.at(64, head=True)
        dd = d[:-1] + "Z"
        hshape(fig, dd, c, shadow=["M0 0 L22 0 C18 20 18 40 22 70 L0 70Z", "M20 46 C30 56 44 56 56 46 L60 70 L16 70Z"],
               hi=["M22 12 C28 6 38 4 46 5.6 C38 6.6 30 9 25 13Z"])
        for x, y, a in ((30, 12, 0), (42, 10, 1), (50, 20, 0), (26, 26, 1), (38, 28, 0), (48, 36, 1), (30, 40, 0), (44, 46, 1)):
            fig.line("M%s %s a2.2 2.2 0 1 %d 3.4 1" % (f(x), f(y), a), t["sh"], 0.8)


def hair_locs(fig, ch, view, c, length=86.0, tie_c=None):
    """Locs pulled back from the face and falling to the shoulders."""
    t = hair_tones(c)
    def loc(x0, y0, x1, y1, w=3.4):
        d = "M%s %s L%s %s Q%s %s %s %s L%s %s Q%s %s %s %sZ" % tuple(map(f, (
            x0 - w / 2, y0, x1 - w / 2, y1 - 1.4, x1 - w / 2, y1 + 0.6, x1, y1 + 0.6, x1 + w / 2, y1 - 1.4, x1 + w / 2, y1 + 0.6,
            x0 + w / 2, y0)))
        # simpler capsule
        d = "M%s %s L%s %s A%s %s 0 0 0 %s %s L%s %s Z" % tuple(map(f, (x0 - w / 2, y0, x1 - w / 2, y1, w / 2, w / 2, x1 + w / 2, y1, x0 + w / 2, y0)))
        hshape(fig, d, c, shadow=[P((x0 - 6, y0), (x0 - w * 0.1, y0), (x1 - w * 0.1, y1 + 3), (x1 - 6, y1 + 3))], lw=0.9)
        for yy in frange(y0 + 6, y1 - 2, 6.5):
            xx = lerp(x0, x1, (yy - y0) / max(1, y1 - y0))
            fig.line("M%s %s L%s %s" % (f(xx - w / 2 + 0.5), f(yy), f(xx + w / 2 - 0.5), f(yy + 0.8)), t["sh"], 0.6)
    if view == "front":
        fig.at(8, head=True)
        for k, x in enumerate((12.6, 16.2, 19.8, 23.4)):
            loc(x + 1, 28, x - 1.4 + k * 0.2, length - 4 + (k % 2) * 3)
        for k, x in enumerate((50.4, 54.0, 57.6, 61.0)):
            loc(x - 2, 30, x + 0.8, length - 8 + (k % 2) * 3)
        fig.at(64, head=True)
        d = ("M14.2 42 C11 33 11.2 18.6 19.4 10.8 C25 5.8 31 3.6 37.4 3.6 C47.2 3.6 55.6 9.2 59.2 18.2 C60.6 22.4 60.8 28 59.8 33.6 "
             "C58.4 28 55.6 24 51.6 21.6 C46.6 18.8 40 18.4 34.6 19.4 C29.6 20.4 25.4 23.4 23.4 27.6 C22.2 30.6 21.8 34.6 21.6 39 L18.6 42Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
        for x0, y0, x1, y1 in ((24, 26, 18, 12), (30, 21.4, 25, 8), (38, 19.4, 34, 5), (46, 19.6, 44, 5.6), (53, 22.6, 53, 9.6)):
            fig.line("M%s %s Q%s %s %s %s" % (f(x0), f(y0), f((x0 + x1) / 2 - 1.4), f((y0 + y1) / 2), f(x1), f(y1)), t["sh"], 0.8)
        fig.at(65.5, head=True)
        for k, x in enumerate((13.4, 17.0)):
            loc(x + 1.2, 36, x - 1.2, length - 16 + k * 4)
        fig.at(79, head=True)
        loc(57.6, 36, 59.2, length - 14)
    else:
        fig.at(64, head=True)
        rear_short(fig, c, top=3.4, lines=False)
        fig.at(80, head=True)
        for k, x in enumerate(frange(14.6, 59, 3.5)):
            loc(x + (36 - x) * 0.18, 14 + abs(36 - x) * 0.5, x, length - 2 - abs(36 - x) * 0.25 + (k % 2) * 2.4)
        if tie_c:
            fig.shape(rect(28, 22, 16, 3.4, 1.4), tie_c, lw=0.8)


def hair_topknot(fig, ch, view, c):
    """Hair pulled back into a top knot (Pacific Islander man)."""
    t = hair_tones(c)
    if view == "front":
        fig.at(63, head=True)
        hshape(fig, ell(24.6, 6.4, 7.0, 5.8), c, hi=["M20 4 C22 2 26 1.4 28.6 2.2C26 2.8 23.6 3.8 22 5.4Z"])
        fig.line("M19.6 6 C22 8 26 9 29.6 8.4", t["sh"], 0.8)
        fig.at(64, head=True)
        d = ("M13.8 40 C10.4 30 10.8 18 19 10.4 C24.6 5.4 30.6 3.4 37.4 3.4 C47 3.4 55.4 8.4 59 17.4 C59.8 19.6 60 22.4 59.6 25 "
             "C57.2 20.8 52.2 17.6 45.2 17 C37.2 16.6 29.6 19 25 24.2 C22.8 27.4 21.8 32.4 21.6 37.6 L18.2 40Z")
        hshape(fig, d, c, shadow=[SH_BACK], hi=[HI_TOP])
        fig.line("M48 16.8 C40 11 32 8.6 26 9.6", t["sh"], 0.8)
        fig.line("M54 20 C46 14 36 12.6 28 13.6", t["sh"], 0.8, op=0.8)
    else:
        rear_short(fig, c, top=3.4, lines=False)
        fig.line("M28 52 C30 36 32 22 34.6 10", t["sh"], 0.8, op=0.8)
        fig.line("M46 50 C44 36 41 22 37.6 10", t["sh"], 0.8, op=0.8)
        fig.at(66, head=True)
        hshape(fig, ell(36, 6.6, 7.4, 6.0), c, shadow=["M20 6 C28 12 36 13 46 10 L46 20 L20 20Z"],
               hi=["M31 3.6 C33 2 36.6 1.4 39.4 2.2C36.6 2.8 34 3.8 32.6 5.4Z"])
        fig.shape(rect(31.6, 10.2, 8.8, 2.8, 1.2), shade(c, 0.7), role="hair", lw=0.7)


def hair_soft(fig, ch, view, c):
    """Short soft waves with volume (older woman)."""
    t = hair_tones(c)
    if view == "front":
        fig.at(8, head=True)
        hshape(fig, bumps([(12.4, 30), (10.6, 42), (12.0, 52), (17.4, 56.6), (24, 54)], amp=-1.4) + " L30 30Z", c,
               shadow=[P((0, 0), (72, 0), (72, 200), (0, 200))])
        fig.at(64, head=True)
        outer = arc_pts(35.6, 28, 25.4, 25.4, 165, 375, 12)
        d = ("M13.2 48 L%s %s " % (f(outer[0][0]), f(outer[0][1])) + bumps(outer, amp=1.3)[len("M%s %s" % (f(outer[0][0]), f(outer[0][1]))):] +
             " C61 40 60.4 48 58.2 52 C56.6 54 55.4 52.8 55.6 50 C56.6 42 56.2 34 53.4 28.6 C50 23.6 44 21.6 38 22.6 "
             "C33 23.4 28 26 25.4 29.6 C23.4 32 22.6 36 22.2 40 L21.6 46 C19.6 50 15 50.6 13.2 48Z")
        hshape(fig, d, c, shadow=["M6 30 L22 34 L22 60 L6 60Z"], hi=[HI_TOP])
        fig.line("M38 22.6 C43 18 49 18 53.4 22", t["sh"], 0.8)
        fig.line("M24 16 C28 12 33 11 37 12", t["sh"], 0.8)
    else:
        fig.at(64, head=True)
        outer = arc_pts(35.6, 28, 25.6, 25.6, 165, 375, 12)
        d = bumps(outer + [(60, 44), (56, 54.4), (46, 57.4), (36, 58), (26, 57.4), (16.4, 54), (12, 44)], amp=1.3, closed=True)
        hshape(fig, d, c, shadow=["M0 0 L20 0 C18 20 18 40 22 64 L0 64Z"], hi=[HI_REAR])
        fig.line("M30 20 C34 26 34 34 32 40", t["sh"], 0.8)
        fig.line("M44 18 C48 26 48 36 45 44", t["sh"], 0.8)


# ----------------------------------------------------------------------------------------------- headwear
# Covered hair has no red in the mask, so cultural headwear always keeps its real colors.
def cloth(fig, d, c, shadow=(), hi=(), lc=None, rule=None, sc=None, role="o", lw=LW):
    fig.shape(d, c, role=role, shadow=shadow, hi=hi, lc=lc, sc=sc or shade(c, SHADOW) if c.startswith("#") else sc, rule=rule, lw=lw)


def checks_pattern(fig, pid, base, ink):
    fig.defs.append('<pattern id="%s" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                    '<rect width="3" height="3" fill="%s"/><rect width="3" height="1.25" fill="%s"/><rect width="1.25" height="3" fill="%s"/>'
                    '</pattern>' % (pid, base, ink, ink))
    return "url(#%s)" % pid


GHUTRA_FACE = ("M24.2 31 C24.6 25.6 27.4 21.6 32 20.4 C38 19 46 19 51.2 20.6 C55 21.8 57 25 57.2 30 "
               "C57.6 38 57.4 46 56 56 L55 62 L49.6 62 C46 64 42 64.6 39 64 C33 63.4 27 60 24.8 56 C24 48 23.8 38 24.2 31Z")


def headwear_ghutra(fig, ch, view, cloth_c=None, pattern=None, agal=None):
    """Gulf ghutra (white) or shemagh (red-and-white checks), held by the black double-cord agal."""
    c = cloth_c or PAL["thobe"]
    ag = agal or PAL["agal"]
    if pattern:
        fill = checks_pattern(fig, "shm" + view, c, pattern)
        lc, sh, fold = shade(pattern, 0.58), None, shade(pattern, 0.6)
    else:
        fill, lc, sh, fold = c, "#9aa1ad", "#e1e5ec", "#b9c0cc"
    def part(d, shadow=(), hi=(), rule=None):
        fig.shape(d, fill, lc=lc, sc=sh, shadow=shadow if not pattern else [], hi=hi if not pattern else [], hc="#ffffff", rule=rule)
        if pattern:   # soft shading over the checks
            for s in shadow:
                clip_fill(fig, d, '<path d="%s" fill="#5a1a1a" opacity="0.16"/>' % s)
            fig.line(d, lc, LW)
    if view == "front":
        fig.at(64, head=True)
        outer = ("M44.6 1.2 C52.6 3.4 58.4 8.6 60.6 16 C62.6 23 62.4 34 61.6 46 L61 58 L56 58 L55 62 L49.6 62 "
                 "C46 64 42 64.6 39 64 C33 63.4 27 60 24.8 56 L22.4 58 L11.6 58 C9.6 48 9 36 10 26 C11 16 16.6 9 25 5 "
                 "C31 2.4 38 1 44.6 1.2Z")
        part(outer + " " + GHUTRA_FACE, shadow=["M6 22 C13 30 18 42 21 60 L6 60Z"], hi=["M22 8.6 C28 4.6 35 3 41 3.2 C34 5 28 7.4 24 10.6Z"], rule=True)
        fig.shape(outer + " " + GHUTRA_FACE, "none", lc=lc, lw=0, rule=True, mask=True) if False else None
        fig.line("M44.6 1.6 C43.4 5 42.6 8.6 42.4 12.6", fold, 0.8)
        fig.line(GHUTRA_FACE, lc, LW)
        fig.at(78)
        lf = "M11.4 56 L22.6 56 C24 66 25.2 78 25.6 96 L13.6 98.6 C12.6 84 11.6 70 11.4 56Z"
        rf = "M55.4 56 L61.2 56 C61.6 68 60.8 82 59.4 94 L52.8 93.4 C53.8 80 54.6 68 55.4 56Z"
        part(lf, shadow=["M0 0 L16.4 0 L18 120 L0 120Z"])
        part(rf, shadow=[])
        fig.line("M17.6 60 C18.4 72 19 84 19.4 96.6", fold, 0.8)
        fig.line("M57.6 60 C57.8 70 57.4 82 56.4 93.4", fold, 0.7)
        if pattern:
            for d in ("M13.6 95.6 L25.6 93.2", "M53 90.6 L59.6 91.2"):
                fig.line(d, pattern, 1.6)
        fig.at(67, head=True)
        for dy in (0.0, 3.0):
            fig.line("M10.6 %s C16 %s 28 %s 40 %s C49.4 %s 56.6 %s 61.2 %s" % tuple(map(f, (
                12.6 + dy, 15.6 + dy, 17.8 + dy, 17.6 + dy, 17.2 + dy, 14.8 + dy, 12.6 + dy))), ag, 2.3, role="o")
        fig.line("M12 12.2 C17 14.8 28 16.6 39 16.4", mix(ag, "#ffffff", 0.35), 0.6)
        fig.line("M14 11.2 C20 8.4 28 7.2 36 7.2 C44 7.2 52 8.4 58 11.2", ag, 1.2, op=0.9)
    else:
        fig.at(64, head=True)
        d = "M36 1.4 C24 1.4 13.4 7.6 10.4 19.6 C8.2 30 9 44 11.4 58 L60.6 58 C62.8 44 63 30 61 19.6 C58.2 8 48 1.4 36 1.4Z"
        part(d, shadow=["M0 0 L22 0 C18 20 18 40 20 60 L0 60Z"], hi=["M24 8.6 C30 4.8 40 4.2 46 6.6 C40 6.8 32 7.8 27 10.4Z"])
        fig.at(78)
        tail = "M11.2 52 C11 70 13.6 88 19 102 C27 109 45 109 53 102 C58.4 88 61 70 60.8 52Z"
        part(tail, shadow=["M0 0 L23 0 C21 40 25 80 29 120 L0 120Z"])
        fig.line("M36 60 C36.4 76 36.4 92 35.6 107", fold, 0.8)
        fig.line("M25 58 C24 74 25 90 27.6 105", fold, 0.7)
        fig.line("M47 58 C48 74 47.6 90 45.6 105.6", fold, 0.7)
        if pattern:
            fig.line("M19 102 C27 109 45 109 53 102", pattern, 1.8)
        fig.at(67, head=True)
        for dy in (0.0, 3.0):
            fig.line("M10.2 %s C16 %s 28 %s 38 %s C48 %s 56 %s 61.6 %s" % tuple(map(f, (
                13.6 + dy, 16.8 + dy, 18.8 + dy, 18.6 + dy, 18.2 + dy, 16.2 + dy, 13.4 + dy))), ag, 2.3, role="o")
        fig.line("M12 13.4 C18 16.2 28 17.8 38 17.6", mix(ag, "#ffffff", 0.35), 0.6)


HIJAB_OUT = ("M41 66.6 C50 66.6 57.4 61.4 60.4 52 C63 42 63.2 26 58.4 16 C54 7.4 45.4 3.2 36.4 3.2 C24.4 3.2 12.8 10.8 10.6 25 "
             "C9 36 11 50 17.6 60 C22.8 66 31.6 67.2 41 66.6Z")
HIJAB_FACE = ("M39.6 62.4 C45.4 62.4 51.4 57.4 54.4 50.2 C56.4 44 56.8 36 55.8 29 C54.8 22.6 50.4 19.2 43.4 18.8 "
              "C36.4 18.6 29.6 20.4 26.6 24.8 C24 29 23.8 38 25.2 45 C27 53 32.6 62.4 39.6 62.4Z")


def headwear_hijab(fig, ch, view, c, drape=88.0, pin=None, long_=False, brim=False, under=None, side_drape=False):
    """Wrapped headscarf framing the face, covering neck and shoulders.
    long_: khimar falling to the waist; brim: tudung with a firm front edge; under: inner cap color at the forehead;
    side_drape: shayla style, one end over the far shoulder."""
    sc = shade(c, SHADOW)
    if view == "front":
        fig.at(9)
        fig.shape("M10 30 C8.6 46 10.6 62 16 74 L40 74 L40 20Z", c, shadow=["M0 0 L72 0 L72 200 L0 200Z"])
        fig.at(64, head=True)
        if under:
            fig.shape("M26.6 24.6 C30 20.6 37 19 44 19.2 C50.4 19.6 54.6 22.6 55.6 28 L55.8 25.6 C55 21.4 50.6 17.8 43.4 17.4 "
                      "C36 17.2 29 19 25.6 23.6Z", under, lw=0.7)
        fig.shape(HIJAB_OUT + " " + HIJAB_FACE, c, rule=True, shadow=["M8 20 C14 32 18 46 24 62 L8 70Z"], hi=[HI_TOP], sc=sc)
        if brim:
            fig.line("M25.4 25.6 C29 19.6 37 17.6 44 17.8 C50.6 18.2 55 21.4 56.4 27.4", shade(c, 0.66), 1.6)
        fig.line("M27.8 26 C31 22 37.6 20.6 44 21", shade(c, 0.8), 0.8)
        fig.at(78)
        bot = drape if not long_ else 112.0
        if long_:
            dr = ("M17 60 C22 64 31 65.4 41 64.8 C49 64.4 55.6 62 59.6 58.6 C63 70 63.6 90 61.6 %s C50 %s 24 %s 12 %s "
                  "C10 92 11.6 72 17 60Z" % tuple(map(f, (bot - 2, bot + 1.4, bot + 1.4, bot - 2))))
        else:
            dr = ("M17 60 C22 64 31 65.4 41 64.8 C49 64.4 55.6 62 59.6 58.6 C61.8 66 61.4 74 58.4 80 C53 %s 45 %s 38 %s "
                  "C30 %s 22 %s 17.6 82 C14.6 76 14.6 68 17 60Z" % tuple(map(f, (bot - 1, bot + 1, bot + 1, bot, bot - 3))))
        fig.shape(dr, c, shadow=["M0 0 L25 0 L27 130 L0 130Z"], sc=sc)
        fig.line("M24 72 C30 78 40 80 50 76", shade(c, 0.76), 0.8, op=0.9)
        if long_:
            fig.line("M20 80 C22 92 23 102 23 110", shade(c, 0.76), 0.8)
            fig.line("M48 82 C50 94 52 102 53 110", shade(c, 0.76), 0.8)
        if side_drape:
            fig.at(79)
            sd = "M50 64 C56 62 60.6 64 61.6 70 C62.6 84 62 100 60.6 112 L52.4 112 C53 98 53.4 84 52 74 Z"
            fig.shape(sd, c, sc=sc, shadow=["M40 60 L54.6 60 L54.6 120 L40 120Z"], hi=["M56 64.6 C58.6 65 60 66.6 60.6 69 C59 67.6 57.6 66.4 56 64.6Z"])
            fig.line("M56.4 70 C57.4 84 57.4 98 56.6 111", shade(c, 0.76), 0.7)
        if pin:
            fig.shape(ell(55.4, 61.4, 1.2), pin, lw=0.6)
    else:
        fig.at(64, head=True)
        d = "M36 3.2 C23 3.2 12.6 11 10.6 24 C9 36 10.6 50 14.4 60 L58 60 C61.4 50 63 36 61.4 24 C59.4 11 49 3.2 36 3.2Z"
        fig.shape(d, c, shadow=["M0 0 L21 0 C17 20 17 44 20 64 L0 64Z"], hi=[HI_REAR], sc=sc)
        fig.at(80)
        bot = drape + 6 if not long_ else 114.0
        dr = "M13.4 52 C11.4 66 12.6 %s 16.6 %s C28 %s 46 %s 56 %s C60.6 %s 61.6 66 59 52Z" % tuple(map(f, (
            bot - 20, bot - 2, bot + 3, bot + 3, bot - 2, bot - 20)))
        if long_:
            dr = "M13.4 52 C10 70 9.6 92 11.4 %s C26 %s 46 %s 61 %s C62.6 92 62.4 70 59 52Z" % tuple(map(f, (bot - 2, bot + 2, bot + 2, bot - 2)))
        fig.shape(dr, c, shadow=["M0 0 L23 0 C21 40 23 80 26 130 L0 130Z"], sc=sc)
        fig.line("M30 60 C30 74 31 86 32 %s" % f(bot - 2), shade(c, 0.76), 0.8, op=0.8)
        fig.line("M44 60 C45 74 45 86 44 %s" % f(bot - 2), shade(c, 0.76), 0.8, op=0.6)
        if side_drape:
            fig.at(81)
            fig.shape("M14 60 C11 74 11 92 12 108 L20 108 C20 94 21 78 24 64Z", c, sc=sc, shadow=["M0 0 L16 0 L16 120 L0 120Z"])


def headwear_roosari(fig, ch, view, c, pattern_c=None):
    """Loose scarf worn back on the head: hair shows at the front, ends drape over the shoulders."""
    sc = shade(c, SHADOW)
    if view == "front":
        fig.at(66, head=True)
        d = ("M30 9.6 C38 6.4 48 6.6 55.6 11.4 C60 15 62.6 22 62.4 32 C62.2 42 61.2 52 59.2 60 L54.6 60 C56.6 50 57.6 40 57.2 32 "
             "C57 25 54.6 19 49.6 16 C44 12.4 36 12 30 14.4 C25 16.6 21.4 21 19.8 27 C19 31 18.8 37 19.4 44 L20.6 56 L11.6 58 "
             "C9.6 48 9 38 10.4 28 C12 18 19 12.4 30 9.6Z")
        fig.shape(d, c, shadow=["M6 20 C13 30 17 42 19.6 60 L6 60Z"], hi=["M28 11.6 C34 9 41 8.4 47 9.4 C40 10.2 34 11.6 30 13.6Z"], sc=sc)
        if pattern_c:
            for x, y in ((15, 34), (14, 46), (59, 28), (59.6, 42), (40, 9.4), (50, 11)):
                fig.fill(ell(x, y, 1.0), pattern_c)
        fig.at(78)
        dr = ("M11.6 56 L20.6 56 C24 64 30 70 38 72 C44 73 50 70 54.6 60 L59.2 60 C60 70 58 80 54 86 L48 84 C42 82 30 82 24 86 "
              "L15 88 C12.6 78 11.6 66 11.6 56Z")
        fig.shape(dr, c, shadow=["M0 0 L20 0 L20 100 L0 100Z"], sc=sc)
        fig.line("M24 76 C32 80 44 80 52 74", shade(c, 0.76), 0.8)
    else:
        fig.at(66, head=True)
        d = "M36 6.6 C24 6.6 14 13 11 24 C9 34 10 48 12.4 60 L59.6 60 C62 48 63 34 61 24 C58 13 48 6.6 36 6.6Z"
        fig.shape(d, c, shadow=["M0 0 L21 0 C17 20 17 44 20 64 L0 64Z"], hi=["M26 12 C32 8.6 40 8.4 46 10.4 C40 10.6 32 11.6 28 14Z"], sc=sc)
        if pattern_c:
            for x, y in ((24, 20), (36, 16), (48, 20), (30, 34), (44, 34), (22, 48), (36, 50), (50, 48)):
                fig.fill(ell(x, y, 1.0), pattern_c)
        fig.at(80)
        fig.shape("M13 54 C12 66 14 78 18 88 C28 92 44 92 54 88 C58 78 60 66 59 54Z", c, shadow=["M0 0 L22 0 L24 100 L0 100Z"], sc=sc)


def headwear_kuma(fig, ch, view, base, colors):
    """Omani kuma: a round embroidered cap."""
    lc = shade(base, 0.6)
    if view == "front":
        fig.at(66, head=True)
        body = "M14.6 20.4 C15.4 12 24 6.4 36 6.4 C48 6.4 56.6 12 57.6 20.4 C57.8 22.6 57.4 24.4 56.6 25.6 C50 21.6 22 21.6 15.6 25.6 C14.8 24.4 14.4 22.4 14.6 20.4Z"
        body = "M14.2 24.4 L14.6 13.8 C18 7.6 26 4.4 36 4.4 C46 4.4 54 7.6 57.6 13.8 L58 24.4 C50 20.4 22.2 20.4 14.2 24.4Z"
        fig.shape(body, base, lc=lc, shadow=["M0 0 L20 0 L20 30 L0 30Z"])
        top = ell(36.1, 9.4, 21.4, 5.0)
        fig.shape(top, shade(base, 1.06), lc=lc, lw=0.9)
        fig.line("M22 10.2 C27 7.6 33 6.8 38 7", colors[0], 0.9)
        for k, x in enumerate(frange(16.6, 56, 3.2)):
            y = 17.6 + 0.012 * (x - 36) ** 2 * 0.4
            fig.fill("M%s %s L%s %s L%s %s L%s %sZ" % tuple(map(f, (x - 1.3, y, x, y - 1.6, x + 1.3, y, x, y + 1.6))), colors[k % len(colors)])
        fig.line("M14.6 14.6 C22 11.6 50 11.6 57.4 14.6", colors[1], 0.9)
        fig.line("M14.4 21.6 C22 18.4 50 18.4 57.8 21.6", colors[2 % len(colors)], 0.9)
    else:
        fig.at(66, head=True)
        body = "M13.6 25.6 L14.2 14 C18 7.6 26 4.4 36 4.4 C46 4.4 54 7.6 57.8 14 L58.4 25.6 C50 22.4 22 22.4 13.6 25.6Z"
        fig.shape(body, base, lc=lc, shadow=["M0 0 L20 0 L20 30 L0 30Z"])
        fig.shape(ell(36.1, 9.4, 21.6, 5.0), shade(base, 1.06), lc=lc, lw=0.9)
        for k, x in enumerate(frange(16, 57, 3.2)):
            y = 18.6
            fig.fill("M%s %s L%s %s L%s %s L%s %sZ" % tuple(map(f, (x - 1.3, y, x, y - 1.6, x + 1.3, y, x, y + 1.6))), colors[k % len(colors)])
        fig.line("M14.2 15.2 C22 12.4 50 12.4 57.6 15.2", colors[1], 0.9)
        fig.line("M13.8 22.6 C22 19.8 50 19.8 58.2 22.6", colors[2 % len(colors)], 0.9)


def headwear_imma(fig, ch, view, c):
    """Sudanese imma: a large white turban wound in even layers."""
    lc = "#a3a9b4"
    sh = "#e2e5eb"
    if view == "front":
        fig.at(66, head=True)
        d = ("M10.4 25.6 C8.6 16 15 6.4 26 3 C32 1.2 40 1 46 2.6 C56 5.2 62.4 12 62 22 C61.8 25 61 27.4 59.6 29 "
             "C55 24.4 46 22 36 22.4 C26 22.8 17 25.6 12.6 30.2 C11.4 28.8 10.6 27.4 10.4 25.6Z")
        fig.shape(d, c, lc=lc, sc=sh, shadow=["M0 0 L18 0 C16 12 16 22 20 32 L0 32Z"], hi=["M22 5.6 C28 3.4 36 2.8 42 3.6 C35 4.6 29 6 25 8Z"])
        for k, (a, b2) in enumerate(((13, 22), (12.4, 15), (17, 9))):
            fig.line("M%s %s C%s %s %s %s %s %s" % tuple(map(f, (11.4 + k * 2, a + 6, 22, a, 44, b2 - 4 + k * 2, 61 - k * 2, b2 + 2))), lc, 0.8)
        fig.line("M36 22.6 C40 16 46 10 54 6.6", lc, 0.8)
    else:
        fig.at(66, head=True)
        d = ("M10 27 C8 16 15 6 26 2.8 C32 1.2 40 1 46 2.6 C56 5.4 63 13 62.4 24 C62.2 26 61.6 28 60.6 29.4 "
             "C54 26 46 25 36 25 C26 25 18 26 11.6 29.6 C10.8 28.8 10.2 28 10 27Z")
        fig.shape(d, c, lc=lc, sc=sh, shadow=["M0 0 L20 0 C17 12 17 22 20 32 L0 32Z"], hi=["M24 5.6 C30 3.4 38 2.8 44 3.6 C37 4.6 31 6 27 8Z"])
        for k in range(3):
            fig.line("M%s %s C%s %s %s %s %s %s" % tuple(map(f, (11 + k * 1.6, 21 - k * 5.4, 24, 17 - k * 5, 48, 17 - k * 5, 61.4 - k * 1.6, 21 - k * 5.4))), lc, 0.8)


def headwear_dastar(fig, ch, view, c):
    """Sikh dastar: a neatly wrapped turban with the peak at the centre of the forehead and layered folds."""
    lc = shade(c, OUTLINE)
    fold = shade(c, 0.72)
    sc = shade(c, SHADOW)
    if view == "front":
        fig.at(66, head=True)
        d = ("M41.6 25.8 C38 23.6 30 23 23.6 25.4 C19.6 27 16.4 29.4 14.2 32.4 C11 26 9.8 18 13 11.6 C17 4.2 26 0 36.4 -0.4 "
             "C47.6 -0.6 57.6 4.6 60.4 13.6 C62 19 61.4 25 59.4 30.6 C56.6 27.8 52 25.6 47 25.2 C45 25.2 43 25.4 41.6 25.8Z")
        fig.shape(d, c, lc=lc, sc=sc, shadow=["M0 0 L19 0 C17 14 17 24 20 34 L0 34Z"], hi=["M22 6.4 C28 2.8 36 1.6 42 2 C35 3.4 29 5.4 25 8.4Z"])
        # folds rising from the peak at the forehead
        fig.line("M41.6 25.6 C34 18 24 14 12 14.6", fold, 0.9)
        fig.line("M41.4 25.4 C36 14 30 7 22 3.4", fold, 0.9)
        fig.line("M42 25.4 C48 18 55 15 60.6 15.8", fold, 0.9)
        fig.line("M42.2 25.2 C46 14 50 7.6 56 5", fold, 0.8, op=0.9)
        fig.line("M41.6 25.8 L42.4 21.4", lc, 0.9)
    else:
        fig.at(65, head=True)
        nape = REAR_SHORT % {"t": "8"}
        fig.shape(nape, PEOPLE["hair"]["black"], sc=shade(PEOPLE["hair"]["black"], 0.8), shadow=["M6 30 C14 40 18 46 24 56 L6 60Z"])
        fig.at(66, head=True)
        d = ("M11.2 33 C8.6 24 9.8 14 15.4 8 C21 2 28.6 -0.4 36.4 -0.4 C46 -0.4 55 3.4 59.4 11 C63 17 62.8 26 60.4 33 "
             "C54 30 46 28.4 36 28.4 C26 28.4 17.6 30 11.2 33Z")
        fig.shape(d, c, lc=lc, sc=sc, shadow=["M0 0 L20 0 C17 14 17 26 21 36 L0 36Z"], hi=["M24 4.4 C30 1.8 38 1.2 44 2 C37 3 31 4.4 27 6.6Z"])
        for k in range(4):
            fig.line("M%s %s C%s %s %s %s %s %s" % tuple(map(f, (11 + k * 0.4, 30 - k * 6.4, 22, 22 - k * 6, 40, 26 - k * 6.6, 61 - k * 0.8, 20 - k * 5))), fold, 0.85)


def headwear_gele(fig, ch, view, c, c2=None, pattern=None):
    """Nigerian gele: a sculpted head wrap with a fanned, pleated crown."""
    lc = shade(c, OUTLINE)
    sc = shade(c, SHADOW)
    c2 = c2 or shade(c, 1.12)
    if view == "front":
        fig.at(58, head=True)
        fan = ("M6.6 18 C4 8 10 -2 20 -5 C26 -7 30 -4 33 -1 C37 -6 46 -8 53 -5 C62 -1.6 67 8 65 18 C64 23 61 27 58 29 "
               "L16 30 C11 27 8 23 6.6 18Z")
        fig.shape(fan, c, lc=lc, sc=sc, shadow=["M0 0 L20 0 L22 34 L0 34Z"], hi=["M14 -1 C18 -4 23 -5.4 27 -4.6 C22 -3 18 -1.4 15.6 1Z"])
        for x0, y0, x1, y1 in ((33, -1, 30, 22), (24, -4, 26, 22), (14, 0, 21, 24), (44, -6, 40, 22), (54, -4.6, 48, 22), (62, 2, 54, 24)):
            fig.line("M%s %s Q%s %s %s %s" % (f(x0), f(y0), f((x0 + x1) / 2 + 2), f((y0 + y1) / 2), f(x1), f(y1)), shade(c, 0.74), 0.9)
        if pattern:
            pattern(fig, fan)
            fig.line(fan, lc, LW)
        fig.at(66, head=True)
        band = ("M12.6 32 C12 26 14 21 19 19.4 C27 17 45 16.6 53 18.8 C58 20.2 60.4 24 60 30 C55 26.4 46 24.6 36 24.8 "
                "C27 25 18.6 27.6 12.6 32Z")
        fig.shape(band, c2, lc=lc, sc=shade(c2, SHADOW), shadow=["M0 0 L18 0 L18 40 L0 40Z"])
        fig.line("M15 26.4 C24 22 46 21 57.4 24.6", shade(c2, 0.76), 0.8)
    else:
        fig.at(66, head=True)
        fan = ("M7.6 20 C5 9 11 -1.6 21 -4.6 C27 -6.4 31 -4 34 -1.4 C38 -6 47 -7.4 54 -4.4 C62.6 -0.6 67 9 64.6 20 C63 26 60 31 56 34 "
               "L16 34 C12 31 9 26 7.6 20Z")
        fig.shape(fan, c, lc=lc, sc=sc, shadow=["M0 0 L20 0 L22 40 L0 40Z"], hi=["M15 -0.6 C19 -3.6 24 -5 28 -4.2 C23 -2.6 19 -1 16.6 1.4Z"])
        for x0, y0, x1, y1 in ((34, -1.4, 34, 30), (24, -4, 28, 30), (15, 0, 22, 30), (45, -6, 42, 30), (55, -4.6, 48, 30), (62, 2, 54, 30)):
            fig.line("M%s %s Q%s %s %s %s" % (f(x0), f(y0), f((x0 + x1) / 2 - 2), f((y0 + y1) / 2), f(x1), f(y1)), shade(c, 0.74), 0.9)
        if pattern:
            pattern(fig, fan)
            fig.line(fan, lc, LW)
        fig.shape("M11.6 30 C10 44 12 54 16 60 C24 64 48 64 56 60 C60 54 62 44 60.6 30Z", c, lc=lc, sc=sc,
                  shadow=["M0 0 L20 0 L22 70 L0 70Z"])
        fig.line("M20 34 C26 46 40 52 54 44", shade(c, 0.74), 0.9)
        fig.shape("M13 40 C12 34 14 30 18 29 C28 27 44 27 54 29 C58 30 60.6 34 59.6 40 C52 37 20 37 13 40Z", c2, lc=lc,
                  sc=shade(c2, SHADOW), shadow=["M0 0 L19 0 L19 44 L0 44Z"])


def headwear_fila(fig, ch, view, c, trim=None):
    """Yoruba fila: a soft cap with its crown folded over to one side."""
    lc = shade(c, OUTLINE)
    sc = shade(c, SHADOW)
    if view == "front":
        fig.at(66, head=True)
        d = ("M14 22 C13.4 14 18 8 26 5.4 C33 3.2 42 3 50 4.4 C56 5.6 61 7.6 63.4 10.6 C64.6 12.4 63.6 14.4 61.4 15.6 "
             "C60 16.4 58.8 17 58.4 18 C59 20 59 22 58.4 24.4 C50 20.8 22 20.8 14 25.4Z")
        fig.shape(d, c, lc=lc, sc=sc, shadow=["M0 0 L19 0 L19 30 L0 30Z"], hi=["M22 8.6 C28 5.6 36 4.6 42 5 C35 6.2 29 8 25 10.6Z"])
        fig.line("M44 6 C50 8 56 11 61.4 15.6", shade(c, 0.72), 0.9)
        if trim:
            fig.line("M14.2 23.4 C22 19.6 50 19.6 58.4 22.8", trim, 1.3)
    else:
        fig.at(66, head=True)
        d = ("M12.6 26 C11.6 16 17 8 26 5 C33 2.8 42 3 49 5 C56 7 61 11 62 16 C62.6 19.6 61.6 23 60.6 26 C52 22.6 21 22.6 12.6 26Z")
        fig.shape(d, c, lc=lc, sc=sc, shadow=["M0 0 L20 0 L20 30 L0 30Z"], hi=["M24 8 C30 5 38 4.4 44 5 C37 6 31 7.6 27 10Z"])
        fig.line("M40 4.4 C46 8 52 12 56 18", shade(c, 0.72), 0.9)
        if trim:
            fig.line("M12.8 24.4 C21 20.8 52 20.8 60.6 24.4", trim, 1.3)


def headwear_beret(fig, ch, view, c):
    lc = shade(c, OUTLINE)
    if view == "front":
        fig.at(67, head=True)
        d = "M11.6 17.6 C11 11 19 4.6 31 3.2 C42 2 52 4.6 55.6 9.6 C57.4 12.4 56 15.4 52 17 C42 20.6 24 21.4 15.4 20.6 C13 20.2 11.8 19 11.6 17.6Z"
        fig.shape(d, c, lc=lc, shadow=["M0 15 L72 15 L72 30 L0 30Z", "M0 0 L16 0 L16 30 L0 30Z"], hi=["M19 7.6 C24 4.8 31 3.8 37 4 C30 5.4 24 7 21 9.4Z"])
        fig.line("M33 3.4 L33.6 0.6", lc, 1.4)
    else:
        fig.at(67, head=True)
        d = "M13 18 C12 11 20 4.6 32 3.4 C43 2.4 53 5.4 57 10.6 C58.6 13.4 57 16.6 53 18 C44 21.2 25 21.6 17 20.8 C14.6 20.4 13.2 19.4 13 18Z"
        fig.shape(d, c, lc=lc, shadow=["M0 15 L72 15 L72 30 L0 30Z", "M0 0 L18 0 L18 30 L0 30Z"], hi=["M22 7 C27 4.6 33 3.8 39 4 C32 5.2 26 6.6 23.4 8.6Z"])
        fig.line("M35 3.6 L35.6 0.8", lc, 1.4)


def headwear_bowler(fig, ch, view, c, band=None):
    """Andean bowler hat, worn small and high on the head."""
    lc = shade(c, OUTLINE)
    sc = shade(c, SHADOW)
    off = 0 if view == "front" else 0.6
    fig.at(67, head=True)
    brim = "M13.6 9.4 C13.6 6 24 3.6 37 3.6 C50 3.6 60.4 6 60.4 9.4 C60.4 12.8 50 15.2 37 15.2 C24 15.2 13.6 12.8 13.6 9.4Z"
    fig.shape(mv(brim, off, 0), c, lc=lc, sc=sc, shadow=["M0 9 L72 9 L72 20 L0 20Z"])
    crown = "M23.4 9.4 C23 0 28.6 -5.6 37 -5.6 C45.4 -5.6 51 0 50.6 9.4 C46 11.4 28 11.4 23.4 9.4Z"
    fig.shape(mv(crown, off, 0), c, lc=lc, sc=sc, shadow=["M0 -10 L29 -10 L29 14 L0 14Z"], hi=["M28 -1.6 C30 -3.6 33.6 -4.6 37 -4.6 C33.6 -3.4 31 -2 29.6 0Z"])
    if band:
        fig.shape(mv("M23.2 5.6 C28 7.4 46 7.4 50.8 5.6 L50.6 8.8 C46 10.6 28 10.6 23.4 8.8Z", off, 0), band, lw=0.8)


# ----------------------------------------------------------------------------------------------- assembly
def Part(fn, *a, **kw):
    """Bind a part function to its options: Part(headwear_hijab, color, drape=90) -> fn(fig, ch, view)."""
    return lambda fig, ch, view: fn(fig, ch, view, *a, **kw)


def draw(ch, view):
    fig = Fig(view)
    ch = dict(ch)
    ch.setdefault("hair_color", (ch.get("hair") or (None, "#3b2a20"))[1])
    bot = ch.get("bottom")
    bare = False
    if bot:
        kind, col = bot[0], bot[1]
        opts = dict(bot[2]) if len(bot) > 2 else {}
        if kind == "trousers":
            trousers(fig, ch, view, col, **opts)
        elif kind == "jeans":
            trousers(fig, ch, view, col, seam=True, **opts)
        elif kind == "skirt":
            legs = opts.pop("legs", None)
            bare_legs(fig, ch, view, top=opts.get("hem", 150) - 12, color=legs)
            skirt(fig, ch, view, col, **opts)
            bare = True
    sh = ch.get("shoes", ("shoe", PAL["shoe"]))
    if sh:
        shoes(fig, ch, view, sh[0], sh[1], z=21 if bare else 17)
    ch["top"](fig, ch, view)
    for fn in ch.get("overlays", []):
        fn(fig, ch, view)
    draw_neck(fig, ch, view)
    draw_head(fig, ch, view)
    hw = ch.get("headwear")
    hr = ch.get("hair")
    if hr:
        opts = hr[2] if len(hr) > 2 else {}
        hr[0](fig, ch, view, hr[1], **opts)
    if view == "front":
        draw_face(fig, ch)
    fz = ch.get("face", {})
    if fz.get("beard"):
        kind, col = fz["beard"]
        facial_hair(fig, ch, view, kind, col, role="hair" if (hr and not hw) else "o")
    ear = ch.get("ear", "hidden" if hw else "over")
    if ear != "hidden":
        draw_ear(fig, ch, view, z=65 if ear == "over" else 61)
    if hw:
        hw(fig, ch, view)
    if ch.get("glasses"):
        draw_glasses(fig, ch, view)
    for fn in ch.get("extras", []):
        fn(fig, ch, view)
    return fig


PAD_X, PAD_Y = 10, 34   # svgs are rendered with room around the frame, to measure the figure and catch clipping


def svg_padded(fig, which, scale):
    s = fig.svg(which, scale)
    return s.replace('width="%d" height="%d" viewBox="0 0 %d %d"' % (W, H, W, H),
                     'width="%d" height="%d" viewBox="%d %d %d %d"' % (W + 2 * PAD_X, H + PAD_Y + 4, -PAD_X, -PAD_Y, W + 2 * PAD_X, H + PAD_Y + 4), 1)


def render(svgdir, pngdir):
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ, NODE_PATH=root)
    if os.path.isdir(pngdir):
        shutil.rmtree(pngdir)
    subprocess.run(["node", os.path.join(HERE, "render.cjs"), svgdir, pngdir], check=True, env=env)


def write_svgs(chars, svgdir, scales):
    if os.path.isdir(svgdir):
        shutil.rmtree(svgdir)
    os.makedirs(svgdir)
    for ch in chars:
        for view in ("front", "rear"):
            fig = draw(ch, view)
            for which in ("color", "mask"):
                with open(os.path.join(svgdir, "%s__%s__%s.svg" % (ch["id"], view, which)), "w") as fh:
                    fh.write(svg_padded(fig, which, scales.get(ch["id"], 1.0)))


def load_rgba(path):
    from PIL import Image
    return Image.open(path).convert("RGBA")


def measure(pngdir, cid):
    """Top row of the figure (in frame coordinates) over both views."""
    import numpy as np
    tops = []
    for v in ("front", "rear"):
        a = np.array(load_rgba(os.path.join(pngdir, "%s__%s__color.png" % (cid, v))))[..., 3]
        rows = np.where(a.max(1) > 64)[0]
        tops.append(rows[0] - PAD_Y if len(rows) else 0)
    return min(tops)


def render_all(chars, work):
    """Two passes: natural size, then the head group scaled so each figure's top lands on the top rows."""
    svgdir, pngdir = os.path.join(work, "svg"), os.path.join(work, "png")
    write_svgs(chars, svgdir, {})
    render(svgdir, pngdir)
    py = PIVOT[1]
    scales = {}
    for ch in chars:
        top = measure(pngdir, ch["id"])
        scales[ch["id"]] = max(0.8, min(1.12, (py - 0.8) / (py - top)))
    write_svgs(chars, svgdir, scales)
    render(svgdir, pngdir)
    return scales, pngdir


def frame(pngdir, cid, view, which):
    """Crop a padded render to the 72x200 frame; report anything outside it."""
    import numpy as np
    im = load_rgba(os.path.join(pngdir, "%s__%s__%s.png" % (cid, view, which)))
    a = np.array(im)
    inside = a[PAD_Y:PAD_Y + H, PAD_X:PAD_X + W]
    total = (a[..., 3] > 40).sum()
    clipped = int(total - (inside[..., 3] > 40).sum())
    from PIL import Image
    return Image.fromarray(inside), clipped


def mask_image(m):
    """Binarize a rendered mask: palette PNG with black, red, green and transparent."""
    import numpy as np
    from PIL import Image
    a = np.array(m).astype(int)
    idx = np.full(a.shape[:2], 3, np.uint8)
    on = a[..., 3] >= 100
    red = on & (a[..., 0] > 127) & (a[..., 0] >= a[..., 1])
    grn = on & (a[..., 1] > 127) & ~red
    idx[on] = 0; idx[red] = 1; idx[grn] = 2
    im = Image.fromarray(idx, "P")
    im.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 0] + [0] * (256 * 3 - 12))
    return im, bool(red.any()), bool(grn.any())


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
        if err.size and np.percentile(err, 99.5) < 40:   # q90 is invisible at 1x on flat art; fine prints stay lossless
            best = b
    with open(out, "wb") as fh:
        fh.write(best.getvalue())
    return best is b


def build(chars, work, write_assets=True):
    from PIL import ImageOps
    scales, pngdir = render_all(chars, work)
    os.makedirs(CHARS, exist_ok=True); os.makedirs(MASKS, exist_ok=True)
    info = {}
    for ch in chars:
        hair = grn_all = True
        clip_total, lossy = 0, 0
        for view, names in (("front", ("front-left", "front-right")), ("rear", ("rear-right", "rear-left"))):
            col, c1 = frame(pngdir, ch["id"], view, "color")
            msk, _ = frame(pngdir, ch["id"], view, "mask")
            m, red, grn = mask_image(msk)
            hair = hair and red if view == "front" else hair
            grn_all = grn_all and grn
            clip_total += c1
            if not write_assets:
                continue
            for k, name in enumerate(names):
                c = col if k == 0 else ImageOps.mirror(col)
                mm = m if k == 0 else ImageOps.mirror(m)
                lossy += save_webp(c, os.path.join(CHARS, "%s-%s.webp" % (ch["id"], name)))
                mm.save(os.path.join(MASKS, "%s-%s.png" % (ch["id"], name)), optimize=True, transparency=3)
        info[ch["id"]] = dict(scale=round(scales[ch["id"]], 3), hair=hair, shirt=grn_all, clipped=clip_total, lossy=lossy)
    return info, pngdir


# ----------------------------------------------------------------------------------------------- sheets
SHEET_BG = (241, 238, 233, 255)


def sheet(images, cols, cell=(72, 200), gap=(18, 18), margin=24, scale=1.0, bg=SHEET_BG, floor=True):
    from PIL import Image, ImageDraw
    cw, chh = int(cell[0] * scale), int(cell[1] * scale)
    rows = (len(images) + cols - 1) // cols
    Wd = margin * 2 + cols * cw + (cols - 1) * gap[0]
    Hd = margin * 2 + rows * chh + (rows - 1) * gap[1]
    out = Image.new("RGBA", (Wd, Hd), bg)
    dr = ImageDraw.Draw(out)
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        x = margin + c * (cw + gap[0]); y = margin + r * (chh + gap[1])
        if floor:   # soft floor shadow under the feet
            dr.ellipse((x + cw * 0.18, y + chh - 5 * scale, x + cw * 0.86, y + chh + 2 * scale), fill=(222, 217, 209, 255))
        if scale != 1.0:
            im = im.resize((cw, chh), Image.LANCZOS)
        out.alpha_composite(im, (x, y))
    return out


def make_sheets(chars, featured, scratch):
    from PIL import Image
    os.makedirs(DOCS, exist_ok=True)
    fl = lambda cid, fc="front-left": load_rgba(os.path.join(CHARS, "%s-%s.webp" % (cid, fc)))
    top = sheet([fl(c) for c in featured], cols=len(featured), scale=2.0, gap=(22, 0), margin=36)
    top.convert("RGB").save(os.path.join(DOCS, "characters-top10.webp"), "WEBP", quality=88, method=6)
    allc = sheet([fl(c["id"]) for c in chars], cols=10, gap=(16, 22), margin=28)
    allc.convert("RGB").save(os.path.join(DOCS, "characters-all.webp"), "WEBP", quality=90, method=6)
    if scratch:
        os.makedirs(scratch, exist_ok=True)
        cells = []
        for c in chars:
            for fc in ("front-left", "front-right", "rear-left", "rear-right"):
                cells.append(fl(c["id"], fc))
            for fc in ("front-left", "rear-right"):
                cells.append(overlay(fl(c["id"], fc), load_rgba(os.path.join(MASKS, "%s-%s.png" % (c["id"], fc)))))
        for k in range(0, len(chars), 10):
            sheet(cells[k * 6:(k + 10) * 6], cols=12, gap=(8, 14), margin=12, floor=False).save(
                os.path.join(scratch, "check-%d.png" % (k // 10 + 1)))


def overlay(col, msk):
    import numpy as np
    from PIL import Image
    a = np.array(col).astype(float)
    m = np.array(msk.convert("RGBA")).astype(float)
    out = a.copy()
    red = (m[..., 0] > 127) & (m[..., 3] > 0)
    grn = (m[..., 1] > 127) & (m[..., 3] > 0)
    out[red, :3] = out[red, :3] * 0.45 + np.array([255, 40, 40]) * 0.55
    out[grn, :3] = out[grn, :3] * 0.45 + np.array([40, 220, 60]) * 0.55
    edge = (m[..., 3] > 0) != (a[..., 3] > 100)
    out[edge] = [40, 90, 255, 255]
    return Image.fromarray(out.astype(np.uint8))


# ----------------------------------------------------------------------------------------------- the cast
SK = PEOPLE["skin"]
HR = PEOPLE["hair"]
CL = PEOPLE["cloth"]


def C(id_, label, culture, gender, **kw):
    kw.update(id=id_, label=label, culture=culture, gender=gender)
    kw.setdefault("build", "f" if gender == "f" else "m")
    return kw


ALL_CHARACTERS = [
    # Arab and Gulf
    C("gulf-thobe", "Gulf man in thobe and ghutra", "Gulf Arab", "m", skin=SK["tan"], featured=True,
      face=dict(beard=("goatee", HR["black"])), top=top_thobe(CL["thobe"]), headwear=Part(headwear_ghutra),
      shoes=("sandal", CL["leather"])),
    C("saudi-shemagh", "Saudi man in red shemagh", "Saudi", "m", skin=SK["warm"],
      face=dict(beard=("full", HR["black"])), top=top_thobe(CL["thobe_warm"]),
      headwear=Part(headwear_ghutra, pattern=CL["shemagh"]), shoes=("sandal", CL["leather_dk"])),
    C("gulf-abaya", "Gulf woman in abaya and shayla", "Gulf Arab", "f", skin=SK["warm"], featured=True,
      face=dict(lips=CL["lip_rose"]), top=top_abaya(CL["abaya"], CL["gold"]),
      headwear=Part(headwear_hijab, CL["abaya"], drape=86, side_drape=True), shoes=("flat", CL["abaya"]), ear="hidden"),
    C("arab-hijab", "Arab woman in hijab and blazer", "Arab", "f", skin=SK["olive_l"],
      top=top_blazer(CL["navy"], inner=CL["cream"], inner_kind="crew"), headwear=Part(headwear_hijab, CL["rose"], drape=82),
      bottom=("trousers", CL["navy_dk"]), shoes=("flat", CL["nude"]), ear="hidden"),
    C("levant-curls", "Levantine woman with curly hair", "Levantine", "f", skin=SK["olive_l"],
      hair=(hair_curly, HR["dark_brown"]), earring=("stud", CL["gold"]), ear="hidden",
      top=top_tee(CL["terracotta"], sleeve="3q"), bottom=("trousers", CL["olive"]), shoes=("flat", CL["leather"])),
    C("egypt-casual", "Egyptian man in business casual", "Egyptian", "m", skin=SK["warm"],
      hair=(hair_short, HR["black"], dict(style="side")), face=dict(beard=("mustache", HR["black"])),
      top=top_shirt(CL["sky"]), bottom=("trousers", CL["trouser"]), shoes=("shoe", CL["leather"])),
    C("oman-kuma", "Omani man in dishdasha and kuma", "Omani", "m", skin=SK["medium"],
      face=dict(beard=("short", HR["black"])), top=top_dishdasha(CL["lilac"], shade(CL["lilac"], 0.82)),
      headwear=Part(headwear_kuma, CL["cream"], [CL["navy"], CL["shemagh"], CL["green"], CL["gold"]]), shoes=("sandal", CL["leather"])),
    C("morocco-djellaba", "Moroccan man in djellaba", "Moroccan", "m", skin=SK["tan"],
      hair=(hair_short, HR["dark_brown"]), face=dict(beard=("short", HR["dark_brown"])),
      top=top_djellaba(CL["djellaba"], stripe=shade(CL["djellaba"], 0.8)), shoes=("babouche", CL["babouche"])),
    C("sudan-imma", "Sudanese man in jalabiya and imma", "Sudanese", "m", skin=SK["deep"], age="old",
      face=dict(beard=("short", HR["white"])), top=top_jalabiya(CL["thobe"]), headwear=Part(headwear_imma, CL["thobe"]),
      shoes=("sandal", CL["leather"])),
    # South Asian
    C("india-sari", "Indian woman in sari", "Indian", "f", skin=SK["medium"], featured=True,
      hair=(hair_bun, HR["black"], dict(where="low", flowers=CL["jasmine"])), earring=("stud", CL["gold"]),
      top=top_sari(CL["teal"], CL["gold"], CL["maroon"]), shoes=("flat", CL["gold"])),
    C("sikh-dastar", "Sikh man in dastar", "Punjabi Sikh", "m", skin=SK["medium"], featured=True,
      face=dict(beard=("full", HR["black"])), headwear=Part(headwear_dastar, CL["navy_turban"]),
      top=top_blazer(CL["grey"], inner=CL["shirt_white"]), bottom=("trousers", CL["charcoal"]), shoes=("shoe", CL["leather_dk"])),
    C("india-kurta", "Indian man in kurta with glasses", "Indian", "m", skin=SK["medium"], age="old",
      hair=(hair_short, HR["grey"], dict(style="side")), glasses=("round", CL["frame"]), face=dict(beard=("mustache", HR["grey"])),
      top=top_kurta(CL["mustard"]), bottom=("trousers", CL["cream"]), shoes=("sandal", CL["leather"])),
    C("pak-kameez", "Pakistani woman in shalwar kameez", "Pakistani", "f", skin=SK["tan"],
      hair=(hair_long, HR["black"], dict(bangs="part")), ear="hidden",
      top=top_kameez(CL["emerald"], CL["gold"]), overlays=[overlay_dupatta(CL["pink"])],
      bottom=("trousers", CL["cream"], dict(gather=True, wide=1.0)), shoes=("flat", CL["gold"])),
    C("desi-hoodie", "South Asian developer in hoodie", "South Asian", "f", skin=SK["brown"],
      hair=(hair_ponytail, HR["black"]), top=top_hoodie(CL["sage"]), bottom=("jeans", CL["denim"]),
      shoes=("sneaker", CL["sneaker"])),
    # East and Southeast Asian
    C("china-qipao", "Chinese woman in qipao-style top", "Chinese", "f", skin=SK["light"], featured=True,
      hair=(hair_bun, HR["black_cool"], dict(where="top", pin=CL["jade"])), face=dict(lips=CL["lip_red"]),
      top=top_qipao(CL["qipao"], CL["gold"]), bottom=("trousers", CL["ink"]), shoes=("flat", CL["ink"])),
    C("china-hoodie", "Chinese man in hoodie with glasses", "Chinese", "m", skin=SK["light"],
      hair=(hair_short, HR["black_cool"]), glasses=("rect", CL["frame"]), top=top_hoodie(CL["slate"]),
      bottom=("jeans", CL["denim"]), shoes=("sneaker", CL["sneaker"])),
    C("japan-bob", "Japanese woman with bob and cardigan", "Japanese", "f", skin=SK["fair"], featured=True,
      hair=(hair_bob, HR["black_cool"]), ear="hidden", top=top_cardigan(CL["oat"], CL["shirt_white"], collar=CL["shirt_white"]),
      bottom=("skirt", CL["navy"], dict(hem=158, pleats=4)), shoes=("shoe", CL["leather"])),
    C("japan-suit", "Japanese man in suit", "Japanese", "m", skin=SK["fair"], age="old",
      hair=(hair_short, HR["grey"], dict(style="side")), top=top_blazer(CL["charcoal"], tie_c=CL["navy"]),
      bottom=("trousers", CL["charcoal"]), shoes=("shoe", CL["ink"])),
    C("korea-sweater", "Korean woman in oversized sweater", "Korean", "f", skin=SK["light"],
      hair=(hair_long, HR["black_cool"]), ear="hidden", top=top_sweater(CL["cream"], oversized=True, hem=121),
      bottom=("trousers", CL["stone"], dict(wide=1.0)), shoes=("sneaker", CL["sneaker"])),
    C("viet-aodai", "Vietnamese woman in ao dai", "Vietnamese", "f", skin=SK["warm"],
      hair=(hair_long, HR["black"], dict(bangs="part", length=106)), ear="hidden",
      top=top_aodai(CL["lavender"]), bottom=("trousers", CL["silk"], dict(wide=1.6)), shoes=("flat", CL["silk"])),
    C("filipino-barong", "Filipino man in barong", "Filipino", "m", skin=SK["warm"],
      hair=(hair_short, HR["black"], dict(style="side")), top=top_barong(CL["barong"], CL["barong_emb"]),
      bottom=("trousers", CL["ink"]), shoes=("shoe", CL["ink"])),
    C("malay-kurung", "Malay woman in tudung and baju kurung", "Malay / Indonesian", "f", skin=SK["warm"],
      headwear=Part(headwear_hijab, CL["dusk_blue"], drape=94, brim=True), ear="hidden",
      top=top_kurung(CL["blush"], (CL["cream"], CL["rose"])), bottom=("skirt", CL["blush"], dict(hem=193, flare=4, top=110)),
      shoes=("flat", CL["nude"])),
    # African
    C("nigeria-gele", "Nigerian woman in gele and ankara", "Nigerian (Yoruba)", "f", skin=SK["deeper"], featured=True,
      headwear=Part(headwear_gele, CL["ankara"], CL["ankara_band"]), earring=("stud", CL["gold"]), ear="over",
      top=top_dress(CL["ankara"], pattern=dots([CL["teal"], CL["cream"]], step=6.2, r=1.9, y0=66, shape="diamond"), hem=186),
      shoes=("flat", CL["gold"])),
    C("nigeria-agbada", "Nigerian man in agbada and fila", "Nigerian (Yoruba)", "m", skin=SK["darkest"],
      face=dict(beard=("short", HR["black"])), top=top_agbada(CL["indigo"], CL["gold"], CL["indigo"]),
      headwear=Part(headwear_fila, CL["indigo"]), bottom=("trousers", CL["indigo"]), shoes=("shoe", CL["leather"])),
    C("ethiopia-kemis", "Ethiopian woman in habesha kemis", "Ethiopian", "f", skin=SK["deep"],
      hair=(hair_bun, HR["black"], dict(where="low")), earring=("stud", CL["gold"]),
      top=top_kemis(CL["kemis"], (CL["green"], CL["gold"], CL["shemagh"])), overlays=[overlay_netela(CL["kemis"], (CL["green"], CL["gold"]))],
      shoes=("flat", CL["leather"])),
    C("ghana-kente", "Ghanaian man with kente stole", "Ghanaian (Akan)", "m", skin=SK["deeper"],
      hair=(hair_short, HR["black"], dict(style="crop")), top=top_shirt(CL["shirt_white"], sleeve="long", pocket=False),
      overlays=[overlay_kente((CL["kente_gold"], CL["green"], CL["shemagh"], CL["ink"]))],
      bottom=("trousers", CL["charcoal"]), shoes=("shoe", CL["leather"])),
    C("somali-hijab", "Somali woman in hijab", "Somali", "f", skin=SK["deep"],
      headwear=Part(headwear_hijab, CL["teal"], long_=True), ear="hidden",
      top=top_abaya(CL["mustard"], CL["gold"]), shoes=("flat", CL["leather"])),
    C("jamaica-locs", "Man with locs", "Jamaican", "m", skin=SK["deeper"],
      hair=(hair_locs, HR["dark_brown"]), face=dict(beard=("stubble", HR["black"])),
      top=top_tee(CL["leaf"]), bottom=("jeans", CL["denim"]), shoes=("sneaker", CL["sneaker"])),
    # Europe, the Americas and others
    C("uk-tweed", "British man in tweed", "British", "m", skin=SK["fair"],
      hair=(hair_short, HR["ginger"]), face=dict(beard=("short", HR["ginger"]), freckles=True),
      top=top_blazer(CL["tweed"], inner=CL["shirt_blue"], tie_c=CL["moss"], patches=CL["leather_dk"]),
      bottom=("trousers", CL["chino"]), shoes=("shoe", CL["leather"])),
    C("france-beret", "French woman with beret and striped top", "French", "f", skin=SK["light"],
      hair=(hair_bob, HR["dark_brown"], dict(bangs="none")), headwear=Part(headwear_beret, CL["beret"]), ear="hidden",
      face=dict(lips=CL["lip_red"]), top=top_tee(CL["cream"], sleeve="3q", print_=None),
      bottom=("trousers", CL["camel"]), shoes=("flat", CL["ink"])),
    C("nordic-braids", "Scandinavian woman with braids", "Scandinavian", "f", skin=SK["porcelain"], featured=True,
      hair=(hair_braids, HR["blonde"]), top=top_knit(CL["cream"], CL["nordic_blue"], CL["cream"]),
      bottom=("jeans", CL["denim_dk"]), shoes=("shoe", CL["leather"])),
    C("italy-suit", "Italian man in a sharp suit", "Italian", "m", skin=SK["olive_l"],
      hair=(hair_short, HR["dark_brown"], dict(style="slick")), face=dict(beard=("stubble", HR["dark_brown"])),
      top=top_blazer(CL["royal"], inner=CL["shirt_white"]), bottom=("trousers", CL["royal"]), shoes=("shoe", CL["cognac"])),
    C("mexico-guayabera", "Mexican man in guayabera", "Mexican", "m", skin=SK["tan"], featured=True,
      hair=(hair_short, HR["black"], dict(style="wavy")), face=dict(beard=("mustache", HR["black"])),
      top=top_guayabera(CL["shirt_white"]), bottom=("trousers", CL["chino"]), shoes=("shoe", CL["leather"])),
    C("brazil-curls", "Brazilian woman with curls", "Brazilian", "f", skin=SK["tan"],
      hair=(hair_curly, HR["brown"], dict(length=86, volume=0.9, tips=HR["caramel"])), earring=("hoop", CL["gold"]), ear="hidden",
      top=top_tee(CL["coral"]), bottom=("trousers", CL["cream"]), shoes=("flat", CL["leather"])),
    C("andean-bowler", "Andean woman with bowler hat and shawl", "Andean (Quechua)", "f", skin=SK["medium"],
      hair=(hair_braids, HR["black"], dict(front=False, length=118, tassel=CL["ink"])), headwear=Part(headwear_bowler, CL["bowler"], band=CL["ink"]),
      top=top_manta(CL["magenta"], (CL["kente_gold"], CL["teal"], CL["shemagh"]), CL["shirt_white"]),
      bottom=("skirt", CL["teal"], dict(hem=156, flare=8, pleats=5)), shoes=("flat", CL["ink"])),
    C("turkey-knit", "Turkish man in a knit sweater", "Turkish", "m", skin=SK["olive_l"],
      hair=(hair_short, HR["dark_brown"], dict(style="wavy")), face=dict(beard=("short", HR["dark_brown"])),
      top=top_sweater(CL["burgundy"], collar=CL["shirt_white"]), bottom=("trousers", CL["grey"]), shoes=("shoe", CL["leather"])),
    C("persian-scarf", "Persian woman in a loose scarf", "Iranian (Persian)", "f", skin=SK["olive_l"],
      hair=(hair_long, HR["dark_brown"], dict(bangs="part", length=70)), headwear=Part(headwear_roosari, CL["sea"], pattern_c=CL["cream"]),
      ear="hidden", face=dict(lips=CL["lip_rose"]), top=top_manteau(CL["olive"]), bottom=("trousers", CL["ink"]), shoes=("flat", CL["ink"])),
    C("pacific-floral", "Pacific Islander man in floral shirt", "Pacific Islander (Samoan)", "m", build="b", skin=SK["medium"],
      hair=(hair_topknot, HR["black"]), face=dict(beard=("stubble", HR["black"])),
      top=top_floral(CL["sea"], CL["cream"], CL["mustard"]), bottom=("trousers", CL["chino"]), shoes=("sandal", CL["leather"])),
    C("us-afro", "Black American woman with afro", "African American", "f", skin=SK["deeper"], featured=True,
      hair=(hair_afro, HR["dark_brown"]), earring=("hoop", CL["gold"]), face=dict(lips=CL["lip_rose"]),
      top=top_blazer(CL["mustard"], inner=CL["shirt_white"], inner_kind="crew"), bottom=("trousers", CL["ink"]), shoes=("flat", CL["ink"])),
    C("europe-grey", "Older European woman with grey hair", "European", "f", skin=SK["porcelain"], age="old",
      hair=(hair_soft, HR["silver"]), glasses=("round", CL["tortoise"]), ear="hidden",
      top=top_cardigan(CL["sage"], CL["shirt_white"], collar=CL["shirt_white"]), bottom=("trousers", CL["charcoal"]),
      shoes=("shoe", CL["leather"])),
]

# The first release ships these 10 (all featured); the rest are drafted above and switched on later by adding their id.
ACTIVE = ["gulf-thobe", "saudi-shemagh", "gulf-abaya", "arab-hijab", "india-sari", "sikh-dastar", "china-qipao",
          "japan-suit", "nigeria-gele", "brazil-curls"]
CHARACTERS = [dict(c, featured=True) for c in ALL_CHARACTERS if c["id"] in ACTIVE]


# ----------------------------------------------------------------------------------------------- main
OLD_IDS = ["Claude-1", "Frontend-dev-1", "Me-1", "dev-1", "dev-2", "employee-1", "employee-2", "employee-3", "explore-1",
           "security-audit-1"]
FACINGS = ("front-left", "front-right", "rear-left", "rear-right")


def manifest(chars):
    return [{"id": c["id"], "label_en": c["label"], "culture_en": c["culture"], "gender": c["gender"],
             "hair": bool(c.get("hair")) and not c.get("headwear_covers", False) and c["_hair"], "featured": bool(c.get("featured"))}
            for c in chars]


def main():
    ap = argparse.ArgumentParser(description="Draw the office characters.")
    ap.add_argument("--only", help="comma-separated ids: draw only these (assets are written, manifest is not)")
    ap.add_argument("--work", default=os.path.join(tempfile.gettempdir(), "office-chars"), help="scratch folder")
    ap.add_argument("--no-sheets", action="store_true")
    ap.add_argument("--remove-old", action="store_true", help="delete the old sprite ids from chars/ and masks/")
    args = ap.parse_args()
    chars = CHARACTERS
    if args.only:
        keep = set(args.only.split(","))
        chars = [c for c in chars if c["id"] in keep]
    ids = [c["id"] for c in CHARACTERS]
    assert len(ids) == len(set(ids)), "duplicate ids"
    assert all("front" not in i and "rear" not in i for i in ids)
    info, _ = build(chars, args.work)
    for c in chars:
        c["_hair"] = info[c["id"]]["hair"]
    for cid, v in info.items():
        flag = "" if v["clipped"] < 3 else "  CLIPPED %d px" % v["clipped"]
        print("%-20s scale %.3f  hair %-5s shirt %-5s%s" % (cid, v["scale"], v["hair"], v["shirt"], flag))
    if not args.only:
        with open(os.path.join(CHARS, "characters.json"), "w") as fh:
            json.dump(manifest(chars), fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        if not args.no_sheets:
            make_sheets(chars, [c["id"] for c in chars if c.get("featured")], os.path.join(args.work, "sheets"))
    if args.remove_old:
        for oid in OLD_IDS:
            for fc in FACINGS:
                for p in (os.path.join(CHARS, "%s-%s.webp" % (oid, fc)), os.path.join(MASKS, "%s-%s.png" % (oid, fc))):
                    if os.path.exists(p):
                        os.remove(p)
    sizes = [os.path.getsize(os.path.join(d, n)) for d in (CHARS, MASKS) for n in os.listdir(d) if n.endswith((".webp", ".png"))
             and n.split("-")[0] + "-" not in [o + "-" for o in OLD_IDS]]
    print("%d files, %.1f KB" % (len(sizes), sum(sizes) / 1024))


if __name__ == "__main__":
    main()
