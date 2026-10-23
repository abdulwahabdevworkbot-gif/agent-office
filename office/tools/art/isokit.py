"""Small SVG toolkit for the room and furniture art (see STYLE.md and NOTES-rooms.md).

Used by rooms.py, furniture.py and fx.py. Rebuild all of that art with one command, from the repo root:

    python3 office/tools/art/build_rooms.py

Everything is drawn as flat vector shapes: a base tone, one shadow tone and one small highlight, with thin
colored outlines (fill x 0.55). Floor points go through the iso helper P(u, v, h) from style.py.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from style import P as _P, PAL, shade, TOP, RIGHT_FACE, LEFT_FACE, OUTLINE, HILITE, W as _W  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ASSETS = os.path.join(ROOT, "office", "assets")
RW, RH = 1200, 896           # room canvas
S = RW / _W                  # h units (1508 scale) -> room pixels


def f(x):
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def pts(ps):
    return " ".join(f"{f(x)},{f(y)}" for x, y in ps)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def mix(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class Svg:
    """Collects shapes; every filled shape gets an outline of its own fill x OUTLINE unless told otherwise."""

    def __init__(self, w, h, lw=2.0, bg=None):
        self.w, self.h, self.lw = w, h, lw
        self.defs, self.body, self.n = [], [], 0
        if bg:
            self.body.append(f'<rect width="{w}" height="{h}" fill="{bg}"/>')

    def uid(self, p="i"):
        self.n += 1
        return f"{p}{self.n}"

    def _st(self, fill, stroke, lw, op, extra):
        s = f'fill="{fill}"'
        if stroke:
            sc = shade(fill, OUTLINE) if stroke is True else stroke
            s += f' stroke="{sc}" stroke-width="{f(self.lw if lw is None else lw)}" stroke-linejoin="round"'
        if op is not None:
            s += f' opacity="{f(op)}"'
        return s + ((" " + extra) if extra else "")

    def poly(self, ps, fill, stroke=True, lw=None, op=None, extra=""):
        self.body.append(f'<polygon points="{pts(ps)}" {self._st(fill, stroke, lw, op, extra)}/>')

    def path(self, d, fill, stroke=True, lw=None, op=None, extra=""):
        self.body.append(f'<path d="{d}" {self._st(fill, stroke, lw, op, extra)}/>')

    def line(self, a, b, color, lw=None, op=None, cap="round"):
        o = f' opacity="{f(op)}"' if op is not None else ""
        self.body.append(f'<line x1="{f(a[0])}" y1="{f(a[1])}" x2="{f(b[0])}" y2="{f(b[1])}" stroke="{color}" '
                         f'stroke-width="{f(self.lw if lw is None else lw)}" stroke-linecap="{cap}"{o}/>')

    def pline(self, ps, color, lw=None, op=None, cap="round"):
        o = f' opacity="{f(op)}"' if op is not None else ""
        self.body.append(f'<polyline points="{pts(ps)}" fill="none" stroke="{color}" stroke-width="'
                         f'{f(self.lw if lw is None else lw)}" stroke-linecap="{cap}" stroke-linejoin="round"{o}/>')

    def ellipse(self, cx, cy, rx, ry, fill, stroke=True, lw=None, op=None, extra=""):
        self.body.append(f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rx)}" ry="{f(ry)}" '
                         f'{self._st(fill, stroke, lw, op, extra)}/>')

    def rect(self, x, y, w, h, fill, rx=0, stroke=True, lw=None, op=None, extra=""):
        r = f' rx="{f(rx)}"' if rx else ""
        self.body.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}"{r} '
                         f'{self._st(fill, stroke, lw, op, extra)}/>')

    def raw(self, s):
        self.body.append(s)

    def group(self, attrs=""):
        self.body.append(f"<g {attrs}>")

    def end(self):
        self.body.append("</g>")

    def clip(self, inner):
        """Define a clipPath from raw SVG shapes; returns its id."""
        i = self.uid("c")
        self.defs.append(f'<clipPath id="{i}">{inner}</clipPath>')
        return i

    def radial(self, color, op=1.0, op_out=0.0, stops=None):
        i = self.uid("g")
        st = stops or [(0, op), (1, op_out)]
        s = "".join(f'<stop offset="{f(o)}" stop-color="{color}" stop-opacity="{f(a)}"/>' for o, a in st)
        self.defs.append(f'<radialGradient id="{i}">{s}</radialGradient>')
        return f"url(#{i})"

    def linear(self, x1, y1, x2, y2, stops, transform=None):
        """stops: [(offset, color, opacity)], user-space coordinates."""
        i = self.uid("l")
        t = f' gradientTransform="{transform}"' if transform else ""
        s = "".join(f'<stop offset="{f(o)}" stop-color="{c}" stop-opacity="{f(a)}"/>' for o, c, a in stops)
        self.defs.append(f'<linearGradient id="{i}" gradientUnits="userSpaceOnUse" x1="{f(x1)}" y1="{f(y1)}" '
                         f'x2="{f(x2)}" y2="{f(y2)}"{t}>{s}</linearGradient>')
        return f"url(#{i})"

    def blur(self, sd):
        i = self.uid("b")
        self.defs.append(f'<filter id="{i}" x="-50%" y="-50%" width="200%" height="200%">'
                         f'<feGaussianBlur stdDeviation="{f(sd)}"/></filter>')
        return f"url(#{i})"

    def text(self):
        d = f"<defs>{''.join(self.defs)}</defs>" if self.defs else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}">{d}{"".join(self.body)}</svg>')

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(self.text())


class Frame:
    """Floor (u, v, h) -> canvas pixels.

    The room frame is P() at 1200x896. A sprite frame is the room frame scaled by k and shifted, so a sprite drawn
    at its real floor spot lines up with the room. linear_at=(u, v) freezes the iso axes at that floor point, so a
    sprite that the page places in many spots (a desk, a plant) has one shape everywhere.
    """

    def __init__(self, k=1.0, ox=0.0, oy=0.0, linear_at=None):
        self.k, self.ox, self.oy = k, ox, oy
        self.lin = None
        if linear_at:
            u0, v0 = linear_at
            e = 1e-4
            o = _P(u0, v0, 0, RW, RH)
            pu = _P(u0 + e, v0, 0, RW, RH)
            pv = _P(u0, v0 + e, 0, RW, RH)
            self.lin = (u0, v0, o, ((pu[0] - o[0]) / e, (pu[1] - o[1]) / e), ((pv[0] - o[0]) / e, (pv[1] - o[1]) / e))

    def room(self, u, v, h=0.0):
        if self.lin:
            u0, v0, o, du, dv = self.lin
            return (o[0] + (u - u0) * du[0] + (v - v0) * dv[0], o[1] + (u - u0) * du[1] + (v - v0) * dv[1] - h * S)
        return _P(u, v, h, RW, RH)

    def __call__(self, u, v, h=0.0):
        x, y = self.room(u, v, h)
        return (self.ox + self.k * x, self.oy + self.k * y)

    def hy(self, h):
        """Height in h units -> canvas pixels."""
        return h * S * self.k

    def plane_v(self, v, u0=0.0, u1=1.0):
        """SVG transform for drawing flat on the plane v=const (parallel to the right wall).
        Local x runs from u0 (x=0) toward u1 in canvas pixels; local y = -height in canvas pixels."""
        o, d = self(u0, v, 0), self(u1, v, 0)
        k = (d[1] - o[1]) / (d[0] - o[0])
        return "matrix(1 %.5f 0 1 %s %s)" % (k, f(o[0]), f(o[1])), d[0] - o[0]

    def plane_u(self, u, v0=1.0, v1=0.0):
        """SVG transform for drawing flat on the plane u=const (parallel to the left wall).
        Local x runs from v0 (x=0, front end) toward v1 in canvas pixels; local y = -height."""
        o, d = self(u, v0, 0), self(u, v1, 0)
        k = (d[1] - o[1]) / (d[0] - o[0])
        return "matrix(1 %.5f 0 1 %s %s)" % (k, f(o[0]), f(o[1])), d[0] - o[0]


def box(svg, F, u0, u1, v0, v1, h0, h1, col, top=None, side=None, front=None, lw=None, faces="tuv", op=None):
    """A shaded block: top x1.00, right-front face (u=u1) x0.86, left-front face (v=v1) x0.72."""
    cu = side or shade(col, RIGHT_FACE)
    cv = front or shade(col, LEFT_FACE)
    if "u" in faces:
        svg.poly([F(u1, v0, h0), F(u1, v1, h0), F(u1, v1, h1), F(u1, v0, h1)], cu, lw=lw, op=op)
    if "v" in faces:
        svg.poly([F(u0, v1, h0), F(u1, v1, h0), F(u1, v1, h1), F(u0, v1, h1)], cv, lw=lw, op=op)
    if "t" in faces:
        svg.poly([F(u0, v0, h1), F(u1, v0, h1), F(u1, v1, h1), F(u0, v1, h1)], top or col, lw=lw, op=op)


def quad(F, u0, u1, v0, v1, h=0.0, n=1):
    """Outline of a floor rectangle (optionally subdivided so bilinear edges stay true)."""
    out = []
    for (a, b) in [((u0, v0), (u1, v0)), ((u1, v0), (u1, v1)), ((u1, v1), (u0, v1)), ((u0, v1), (u0, v0))]:
        for i in range(n):
            t = i / n
            out.append(F(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, h))
    return out


def floor_poly(F, uv, h=0.0, n=6):
    """Polygon through floor points [(u, v)], each edge subdivided n times."""
    out = []
    for i, a in enumerate(uv):
        b = uv[(i + 1) % len(uv)]
        for j in range(n):
            t = j / n
            out.append(F(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, h))
    return out


def floor_ellipse(F, uc, vc, ru, rv, h=0.0, n=28):
    import math
    return [F(uc + ru * math.cos(2 * math.pi * i / n), vc + rv * math.sin(2 * math.pi * i / n), h) for i in range(n)]


def render(svg_dir, png_dir, scale=1):
    env = dict(os.environ)
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        env["NODE_PATH"] = root + (os.pathsep + env["NODE_PATH"] if env.get("NODE_PATH") else "")
    except OSError:
        pass
    subprocess.run(["node", os.path.join(HERE, "render.cjs"), svg_dir, png_dir, str(scale)], check=True, env=env)


def save_webp(im, out, target=None, q0=86, lossless_ok=True, alpha_q=90, qmin=50):
    """Save the smaller of lossless and lossy WebP; lossy quality steps down until the file fits target bytes."""
    import io

    def enc(**kw):
        b = io.BytesIO()
        im.save(b, "WEBP", method=6, **kw)
        return b.getvalue()

    cands = [enc(lossless=True, quality=100)] if lossless_ok else []
    q = q0
    while True:
        kw = dict(quality=q)
        if im.mode == "RGBA":
            kw["alpha_quality"] = alpha_q
        d = enc(**kw)
        if target is None or len(d) <= target or q <= qmin:
            cands.append(d)
            break
        q -= 4
    best = min(cands, key=len)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(best)
    return len(best)
