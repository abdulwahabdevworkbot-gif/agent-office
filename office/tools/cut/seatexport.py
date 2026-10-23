import numpy as np, json, os, shutil
from PIL import Image
from seatcomp import HD, FIX, ROW, neck_of, shoulders
from build import tag
A=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets")
TIGHT={8,9,10,11,12,14,16,17,38,39,40}
S=3   # bodies stored at 3x the sheet so the credit tag can be read when zoomed
for d in ("seated","heads"): shutil.rmtree(f"{A}/{d}",ignore_errors=True); os.makedirs(f"{A}/{d}")
meta={"rows":{},"bodies":{},"heads":{},"row_of":{}}
for r in range(1,13):
    ref=Image.open("seat/b%02d-1.png"%r); meta["rows"][r]=round(shoulders(ref)*S/1.45,1)   # head width on this row, in stored body px
    for c in range(1,10):
        b=Image.open("seat/b%02d-%d.png"%(r,c)); b=b.resize((b.width*S,b.height*S),Image.LANCZOS)
        b=tag(b,fy=0.80,size=7)
        nx,ny=neck_of(b); b.save(f"{A}/seated/b{r:02d}-{c}.webp",quality=88)
        meta["bodies"][f"{r}-{c}"]=[b.width,b.height,round(nx,1),int(ny)]
for i in range(1,42):
    h=HD[str(i)]; im=Image.open("n41/raw%02d.png"%i)
    cf=min(FIX.get(i,h["chinf"]),.30); y1=h["top"]+int(h["H"]*(cf+(.008 if i in TIGHT else .03)))
    hd=im.crop((0,h["top"],im.width,y1)); hd=hd.crop(hd.getbbox())
    hd=hd.resize((96,round(hd.height*96/hd.width)),Image.LANCZOS)
    hd.save(f"{A}/heads/c{i:02d}.webp",quality=90); meta["heads"]["c%02d"%i]=[hd.width,hd.height]
    meta["row_of"]["c%02d"%i]=ROW[i]
json.dump(meta,open(f"{A}/seated/seated.json","w"),separators=(",",":"))
print(json.dumps(meta)[:300]); os.system(f"du -sh {A}/seated {A}/heads")
