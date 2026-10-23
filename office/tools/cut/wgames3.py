import numpy as np, json
from PIL import Image
box=json.load(open("w-games-boxes.json"))
base=Image.open("w-games-wide.png").convert("RGBA")
T=238; S=-0.44
def mv(f): return (round(T*f), round(120+T*f*S))
MOVE={"beanbag-orange":0,"left":0,"cabinet":0,"planters":0,"planterbox":0,"pool":.5,"foos":.5,"lounge":1,"pingpong":1}
order=[]
for k,f in MOVE.items():
    sp=Image.open("w-sp-%s.png"%k); x,y=box[k]; dx,dy=mv(f)
    order.append((y+sp.height+dy,k,sp,(x+dx,y+dy)))
for _,k,sp,p in sorted(order): base.alpha_composite(sp,p)
base.save("w-games-final.png")
json.dump({k:[box[k][0]+mv(f)[0],box[k][1]+mv(f)[1]] for k,f in MOVE.items()},open("w-games-place.json","w"))
b=Image.new("RGB",base.size,(15,20,32)); b.paste(base,(0,0),base); b.save("w-view.png")
