# the owner's third seated library: 14 outfits x 10 poses, bodies only (no heads, no furniture), one cell per pose
import os, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from clean import matte
im=np.asarray(Image.open("src/hi/seated3.png").convert("RGB")).astype(int)
cols=[(152,272),(276,397),(400,518),(522,642),(646,771),(775,904),(908,1036),(1040,1172),(1176,1308),(1312,1440)]
rows=[100,170,240,313,388,460,534,604,674,744,812,883,949,1013,1084]
os.makedirs("seat3",exist_ok=True)
BOXED={(10,5),(11,5),(12,5)}   # cells whose background is a shade darker than the sheet
for ri in range(14):
    for ci,(a,b) in enumerate(cols):
        y0,y1=rows[ri]+1,rows[ri+1]; x0,x1=a,b; c=im[y0:y1,x0:x1].astype(float)
        border=np.concatenate([c[0],c[-1],c[:,0],c[:,-1]]); bg=np.median(border,axis=0)
        d=np.abs(c-bg).max(axis=2); cand=d<16
        if (ri,ci) in BOXED: cand|=(c.max(2)-c.min(2)<16)&(c.mean(2)>200)
        # a pose that touches the cell edge would cut the background in two: grow the background from every edge pixel
        seed=np.zeros_like(cand); seed[0]=seed[-1]=seed[:,0]=seed[:,-1]=True
        lab,n=ndi.label(cand|seed)
        edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
        fg=~np.isin(lab,list(edge)); fg=ndi.binary_opening(fg,iterations=1)
        fg[:3]=False
        # the soft floor shadow under each body is not part of it
        sat=c.max(2)-c.min(2); shadow=(d<60)&(sat<22)&(c.mean(2)>150)&(c.mean(2)<235); fg&=~shadow
        l2,n2=ndi.label(ndi.binary_dilation(fg,iterations=2)); sz=ndi.sum(fg,l2,range(1,n2+1)); fg=fg&(l2==1+int(np.argmax(sz)))
        fg=ndi.binary_fill_holes(fg)
        rgb,a_=matte(c,fg,bg)
        ys,xs=np.nonzero(a_>0.02)
        out=np.dstack([rgb,a_*255])[ys.min():ys.max()+1,xs.min():xs.max()+1].astype(np.uint8)
        Image.fromarray(out).save("seat3/b%02d-%d.png"%(ri+1,ci+1))
S=Image.new("RGB",(10*130,14*80),(90,110,140))
for ri in range(14):
    for ci in range(10):
        b=Image.open("seat3/b%02d-%d.png"%(ri+1,ci+1)); b.thumbnail((126,76)); S.paste(b,(ci*130+2,ri*80+2),b)
S.save("seat3sheet.png")
