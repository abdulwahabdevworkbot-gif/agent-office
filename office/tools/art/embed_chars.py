"""Copy the character list from assets/chars/characters.json into office.html (CHARS and POOL).
usage: python3 office/tools/art/embed_chars.py   (from the repo root, after chars.py)"""
import json, os, re
OFF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
chars = json.load(open(os.path.join(OFF, "assets", "chars", "characters.json")))
chars.sort(key=lambda c: not c.get("featured"))
keep = ("id", "label_en", "featured", "hair", "robe", "options", "defaults")
rows = [{k: c[k] for k in keep if k in c} for c in chars]
p = os.path.join(OFF, "office.html")
s = open(p).read()
s = re.sub(r"^const CHARS = .*$", lambda m: "const CHARS = " + json.dumps(rows, ensure_ascii=False) + ";", s, count=1, flags=re.M)
s = re.sub(r"^const POOL = .*$", lambda m: "const POOL = " + json.dumps([c["id"] for c in chars]) + ";", s, count=1, flags=re.M)
open(p, "w").write(s)
print(len(rows), "characters embedded")
