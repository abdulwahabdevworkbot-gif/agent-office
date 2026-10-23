import os, numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
B={"rooms1":{"office-a1":(15,12,542,354),"office-b1":(570,10,1110,354),"office-wide":(13,369,1109,673),
             "meeting-1":(17,686,549,1012),"huddle":(572,687,1104,1003),"waiting-1":(15,1020,550,1394),"games-1":(571,1021,1109,1396)},
   "rooms2":{"office-a":(11,15,532,363),"office-b":(547,16,1079,363),"manager":(9,372,532,725),"meeting-10":(551,373,1076,725),
             "meeting-20":(4,733,536,1058),"meeting-30":(546,729,1083,1058),"waiting":(5,1070,540,1439),"games":(545,1067,1082,1441)}}
os.makedirs("rooms",exist_ok=True)
for src,boxes in B.items():
    im=np.asarray(Image.open("src/%s.png"%src).convert("RGB")).astype(float)
    for name,(x0,y0,x1,y1) in boxes.items():
        c=im[y0:y1,x0:x1]
        border=np.concatenate([c[0],c[-1],c[:,0],c[:,-1]]); bg=np.median(border,axis=0)
        d=np.abs(c-bg).max(axis=2)
        cand=d<34; lab,n=ndi.label(cand)
        edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
        fg=~np.isin(lab,list(edge))
        lab2,n2=ndi.label(fg); sz=ndi.sum(fg,lab2,range(1,n2+1)); fg=lab2==(1+int(np.argmax(sz)))
        fg=ndi.binary_fill_holes(fg)
        a=fg.astype(float)
        rim=fg&~ndi.binary_erosion(fg,iterations=1); a[rim]=np.clip((d[rim]-10)/50,0,1)
        ys,xs=np.nonzero(fg)
        rgba=np.dstack([c,a*255])[ys.min():ys.max()+1,xs.min():xs.max()+1].astype(np.uint8)
        Image.fromarray(rgba).save("rooms/%s.png"%name); print(name,rgba.shape[1],rgba.shape[0])
