import os, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from clean import matte
im=np.asarray(Image.open("src/seated.png").convert("RGB")).astype(int)
cols=[(196, 279), (309, 406), (457, 555), (590, 682), (718, 832), (864, 1019), (1055, 1154), (1191, 1295), (1352, 1425)]
lum=im.mean(2); sat=im.max(2)-im.min(2); ink=(lum<215)|(sat>38)
r=ink[990:1035,190:1430].sum(1); split=990+int(np.argmin(r))
rows=[(96,179),(180,263),(264,350),(350,435),(435,520),(520,606),(606,690),(690,777),(777,863),(863,948),(948,split),(split,1086)]
os.makedirs("seat",exist_ok=True)
for ri,(y0,y1) in enumerate(rows,1):
    for ci,(a,b) in enumerate(cols,1):
        x0,x1=a-10,b+10; c=im[y0:y1,x0:x1].astype(float)
        border=np.concatenate([c[0],c[-1],c[:,0],c[:,-1]]); bg=np.median(border,axis=0)
        d=np.abs(c-bg).max(axis=2); cand=d<16; lab,n=ndi.label(cand)
        edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
        fg=~np.isin(lab,list(edge)); fg=ndi.binary_opening(fg,iterations=1)
        l2,n2=ndi.label(ndi.binary_dilation(fg,iterations=2)); sz=ndi.sum(fg,l2,range(1,n2+1)); fg=fg&(l2==1+int(np.argmax(sz)))
        rgb,a_=matte(c,fg,bg)
        # floor shadow -> soft dark
        ys,xs=np.nonzero(a_>0.02)
        out=np.dstack([rgb,a_*255])[ys.min():ys.max()+1,xs.min():xs.max()+1].astype(np.uint8)
        Image.fromarray(out).save("seat/b%02d-%d.png"%(ri,ci))
print("split",split)
