# export the third seated library (bodies only) and the back / profile heads into office/assets
import numpy as np, json, os
from PIL import Image
from seatcomp import ROW
from build import tag
A="/home/claude/agent-office/office/assets"
OLD2NEW={1:1,2:2,3:4,4:5,5:6,6:7,7:8,8:9,9:10,10:11,11:12,12:13}
FIXROW={17:14}                      # woman with a bun in a cream shirt: blouse and trousers
# seat type -> sheet column: 1 front, 2 side, 3 back, 4 3/4 back, 5 3/4 front, 6 crossed legs (visitor), 7 one leg crossed (meeting),
# 8 relaxed lounge (sofa), 9 bean bag, 10 stool
COL={1:1,2:2,3:3,4:4,5:5,6:7,7:8,8:6,9:9,10:10}
S=3
old=json.load(open(f"{A}/seated/seated.json"))
for f in os.listdir(f"{A}/seated"):
    if f.endswith(".webp"): os.remove(f"{A}/seated/{f}")
def neck(b):
    a=np.asarray(b)[...,3]>128; ys=np.nonzero(a.any(1))[0]; top=ys[0]; xs=np.nonzero(a[top:top+6].any(0))[0]
    return (xs[0]+xs[-1])/2, top
meta={"rows":{},"bodies":{},"heads":old["heads"],"views":{},"row_of":{"c%02d"%i:FIXROW.get(i,OLD2NEW[ROW[i]]) for i in range(1,42)}}
for r in range(1,15):
    meta["rows"][r]=85
    for k,c in COL.items():
        b=Image.open("seat3/b%02d-%d.png"%(r,c)); b=b.resize((b.width*S,b.height*S),Image.LANCZOS)
        b=tag(b,fy=0.80,size=7); nx,ny=neck(b)
        b.save(f"{A}/seated/b{r:02d}-{k}.webp",quality=88)
        meta["bodies"][f"{r}-{k}"]=[b.width,b.height,round(nx,1),int(ny)]
TH=json.load(open("turnheads.json"))
for i,v in TH.items():
    c="c%02d"%int(i); meta["views"][c]=v
    for k in v: Image.open(f"out-heads/{c}-{k}.png").save(f"{A}/heads/{c}-{k}.webp",quality=90)
json.dump(meta,open(f"{A}/seated/seated.json","w"),separators=(",",":"))
os.system(f"du -sh {A}/seated {A}/heads; ls {A}/heads | wc -l")
