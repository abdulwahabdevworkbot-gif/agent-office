import numpy as np, json, os, shutil
from PIL import Image
from seatcomp import ROW
from build import tag
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../assets")
OLD2NEW={1:1,2:2,3:4,4:5,5:6,6:7,7:8,8:9,9:10,10:11,11:12,12:13}
S=3
def neck_ref(c):
    # row 1 (white thobe): the neck is the top of the white cloth; chair parts are dark
    b=np.asarray(Image.open("seat2/b01-%d.png"%c)).astype(int); a=b[...,3]>128
    wh=a&(b[...,:3].min(2)>170)
    ys=np.nonzero(wh.any(1))[0]; top=ys[0]; xs=np.nonzero(wh[top:top+4].any(0))[0]
    H,W=a.shape; return ((xs[0]+xs[-1])/2)/W, top/H
NR={c:neck_ref(c) for c in range(1,11)}
old=json.load(open(f"{A}/seated/seated.json"))
for f in os.listdir(f"{A}/seated"):
    if f.endswith(".webp"): os.remove(f"{A}/seated/{f}")
meta={"rows":{},"bodies":{},"heads":old["heads"],"row_of":{"c%02d"%i:OLD2NEW[ROW[i]] for i in range(1,42)}}
for r in range(1,15):
    meta["rows"][r]=85
    for c in range(1,11):
        b=Image.open("seat2/b%02d-%d.png"%(r,c)); b=b.resize((b.width*S,b.height*S),Image.LANCZOS)
        b=tag(b,fy=0.80,size=7)
        fx,fy=NR[c]; nx,ny=fx*b.width,fy*b.height; b.save(f"{A}/seated/b{r:02d}-{c}.webp",quality=88)
        meta["bodies"][f"{r}-{c}"]=[b.width,b.height,round(nx,1),int(ny)]
json.dump(meta,open(f"{A}/seated/seated.json","w"),separators=(",",":"))
os.system(f"du -sh {A}/seated; ls {A}/seated | wc -l")
