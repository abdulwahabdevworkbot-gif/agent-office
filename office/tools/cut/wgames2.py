import numpy as np, json
from PIL import Image
from widen import widen
A=np.asarray(Image.open("w-games-shell.png").convert("RGBA"))
def s_of(y): return float(np.clip(-0.418+(-0.08)*(y-92)/(628),-0.498,-0.418))
offs=[]
def cutf(H,x0,ybase):
    ys=np.arange(H); return np.where(ys<ybase,x0,x0+(ys-ybase)/0.5)
cur=A; dy_total=0
for k in range(2):
    H=cur.shape[0]
    cur,pt=widen(cur,cutf(H,527,345+dy_total),119,lambda y,dt=dy_total: s_of(y-dt))
    dy_total+=pt
Image.fromarray(cur).save("w-games-wide.png"); print(cur.shape, dy_total)
b=Image.new("RGB",(cur.shape[1],cur.shape[0]),(15,20,32)); im=Image.fromarray(cur); b.paste(im,(0,0),im); b.save("w-view.png")
