import numpy as np, json
from PIL import Image
from widen import widen
A=np.asarray(Image.open("w-wait-shell.png").convert("RGBA"))
def s_of(y): return float(np.clip(-0.38-0.125*(y-123)/667,-0.505,-0.38))
def cutf(H,x0,ybase):
    ys=np.arange(H); return np.where(ys<ybase,x0,x0+(ys-ybase)/0.5)
cur=A; dt=0
for k in range(2):
    cur,pt=widen(cur,cutf(cur.shape[0],520,437+dt),60,lambda y,dt=dt: s_of(y-dt)); dt+=pt
Image.fromarray(cur).save("w-wait-wide.png")
box=json.load(open("w-wait-boxes.json")); base=Image.fromarray(cur)
T=120; S=-0.43
mv=lambda f:(round(T*f),round(dt+T*f*S))
MOVE={"armchair3":0,"planterF":0,"armchair4":0.3,"sofaB":.5,"coffee":.5,"sidetableF":.5,"ottomanF":.5,"armchair1":1,"sidetable":1,"armchair2":1,"ottomanR":1,"sofaF":.8}
order=[]
for k,f in MOVE.items():
    sp=Image.open("w-spw-%s.png"%k); x,y=box[k]; dx,dy=mv(f); order.append((y+sp.height+dy,k,sp,(x+dx,y+dy)))
for _,k,sp,p in sorted(order): base.alpha_composite(sp,p)
base.save("w-wait-final.png")
json.dump({k:[box[k][0]+mv(f)[0],box[k][1]+mv(f)[1]] for k,f in MOVE.items()},open("w-wait-place.json","w"))
b=Image.new("RGB",base.size,(15,20,32)); b.paste(base,(0,0),base); b.resize((b.width*2//3,b.height*2//3)).save("wv-w3.png"); print(cur.shape,dt)
