# the owner's turnaround sheets: find every standing figure (right / back / left views)
import numpy as np, json, sys
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
out={}
for sh in ("turn1","turn2"):
    im=np.asarray(Image.open(f"src/hi/{sh}.png").convert("RGB")).astype(int)
    bg=np.median(im[:5].reshape(-1,3),axis=0); d=np.abs(im-bg).max(2)
    fg=d>22; fg=ndi.binary_closing(fg,iterations=2)
    lab,n=ndi.label(fg); objs=ndi.find_objects(lab)
    figs=[]
    for i,sl in enumerate(objs):
        h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start
        if h>180:
            k=max(1,round(w/64))   # touching figures come out as one blob: split it evenly
            for j in range(k): figs.append([sl[1].start+w*j//k,sl[0].start,sl[1].start+w*(j+1)//k,sl[0].stop,i+1])
    # reading order: band by top y, then x
    figs.sort(key=lambda b:(round(b[1]/150),b[0]))
    out[sh]=figs
    v=Image.open(f"src/hi/{sh}.png").convert("RGB"); dr=ImageDraw.Draw(v)
    for k,b in enumerate(figs): dr.rectangle(b[:4],outline=(255,0,0)); dr.text((b[0]+2,b[1]+2),str(k),fill=(0,0,255))
    v.save(f"{sh}-seg.png"); print(sh,len(figs),[ (b[2]-b[0]) for b in figs])
json.dump(out,open("turnseg.json","w"))
