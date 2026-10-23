#!/usr/bin/env python3
"""Rebuild the room backgrounds and furniture sprites with one command, from the repo root:

    python3 office/tools/art/build_rooms.py [--work DIR]

Writes office/assets/rooms/{office,meet,game}-{day,night}.webp and office/assets/furn/*.webp.
Needs node + playwright (render.cjs, no downloads) and Python with PIL. See NOTES-rooms.md.
"""
import argparse, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image  # noqa: E402
import isokit, rooms, furniture  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--work", default=None, help="scratch folder for svg/png (default: a temp dir)")
a = ap.parse_args()
work = a.work or tempfile.mkdtemp(prefix="rooms-")
total = 0
for kind, mod, out, target in [("rooms", rooms, "rooms", 60000), ("furn", furniture, "furn", None)]:
    sd, pd = os.path.join(work, kind, "svg"), os.path.join(work, kind, "png")
    os.makedirs(sd, exist_ok=True)
    mod.build(sd)
    isokit.render(sd, pd)
    for fn in sorted(os.listdir(pd)):
        im = Image.open(os.path.join(pd, fn))
        im = im.convert("RGB") if kind == "rooms" else im.convert("RGBA")
        dst = os.path.join(isokit.ASSETS, out, fn[:-4] + ".webp")
        n = isokit.save_webp(im, dst, target=target, q0=88 if kind == "rooms" else 90, lossless_ok=kind != "rooms")
        total += n
        print(f"{n:7d}  {os.path.relpath(dst, isokit.ROOT)}")
print(f"{total:7d}  total")
