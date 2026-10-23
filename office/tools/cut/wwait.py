import numpy as np, json
from PIL import Image
from scipy import ndimage as ndi
from widen import *
RUG=[(138,628),(642,401),(1237,680),(740,929)]
SP={
 "sofaB":[(368,505),(375,452),(560,355),(650,328),(700,333),(784,375),(784,452),(560,562),(480,600),(455,592),(368,552)],
 "armchair1":[(798,410),(830,362),(880,349),(942,378),(948,452),(880,478),(830,473),(800,452)],
 "sidetable":[(916,460),(922,392),(992,392),(1000,470),(992,525),(922,525)],
 "armchair2":[(960,470),(1030,430),(1092,438),(1122,480),(1120,562),(1050,592),(1008,587),(962,562)],
 "armchair3":[(258,560),(300,525),(352,527),(412,575),(414,652),(340,688),(298,683),(260,642)],
 "armchair4":[(446,665),(500,630),(560,638),(614,680),(614,748),(560,768),(468,763),(448,722)],
 "coffee":[(612,560),(680,503),(720,462),(782,467),(832,498),(882,518),(918,560),(913,642),(850,675),(760,671),(700,653),(615,603)],
 "planterF":[(338,700),(348,618),(440,620),(522,700),(622,798),(622,882),(570,898),(343,778)],
 "sidetableF":[(613,770),(623,698),(712,698),(720,770),(714,855),(623,858)],
 "sofaF":[(708,760),(718,718),(840,698),(1000,618),(1080,578),(1122,583),(1178,623),(1175,712),(852,875),(798,875),(710,822)],
 "ottomanR":[(1163,600),(1193,552),(1272,552),(1300,600),(1298,652),(1240,668),(1168,652)],
 "ottomanF":[(660,860),(688,826),(772,828),(802,860),(798,933),(740,951),(668,933)],
}
im=Image.open("rooms/waiting.png").convert("RGBA"); A=np.asarray(im).copy(); c=A[...,:3].astype(int); a=A[...,3]
H,W=a.shape; yy,xx=np.mgrid[0:H,0:W]
masks={k:ndi.binary_dilation(sprite_mask(c,a,v),iterations=1)&ndi.binary_dilation(poly_mask(a.shape,v),iterations=4) for k,v in SP.items()}
masks["sofaB"]&=~((xx<425)&(yy<466))
hole=np.zeros(a.shape,bool)
for m in masks.values(): hole|=m
hole&=a>20
r,g,b=c[...,0],c[...,1],c[...,2]
rugp=poly_mask(a.shape,RUG); rugin=ndi.binary_erosion(rugp,iterations=3)
tile=(r>238)&(g>195)&(g<235)&(b>140)&(b<200)&(r-b>45)
rugc=(r>195)&(abs(r-g)<30)&(r-b>8)&(r-b<70)&(r<245)
ZONE=[(0,610),(780,335),(1435,605),(1435,1005),(0,1005)]
zone=poly_mask(a.shape,ZONE)
L1=604.66+0.587*xx; L2=1347.1-0.5053*xx
slab=(r>120)&(r<200)&(g>80)&(g<150)&(b>50)&(b<120)
hi=(r>238)&(g>210)&(b>150)
band=(xx<690)&(yy>L1-40)&(yy<L1+6); band2=(xx>700)&(yy>L2-40)&(yy<L2+6)
clean=zone&~ndi.binary_dilation(hole,iterations=3)&(a>250)
d1=np.array([1,-0.45]); d1/=np.linalg.norm(d1); d2=np.array([1,0.5]); d2/=np.linalg.norm(d2)
e1=np.array([1,0.587]); e1/=np.linalg.norm(e1); e2=np.array([1,-0.5053]); e2/=np.linalg.norm(e2)
A=inpaint_blend(A,hole&band,clean&band&(tile|slab|hi),e1); hole&=~band
A=inpaint_blend(A,hole&band2,clean&band2&(tile|slab|hi),e2); hole&=~band2
# rug: near its d1-parallel edges copy along d1, elsewhere along d2
ed=rugp&~ndi.binary_erosion(rugp,iterations=16)
fr=ed&(np.abs(yy-(929-0.5*(xx-740)))<18); bk=ed&(np.abs(yy-(628-0.45*(xx-138)))<18)
rv=clean&rugp&rugc
A,lf=inpaint_copy(A,hole&(fr|bk),rv&(fr|bk),d1,ret_left=True); hole=(hole&~(fr|bk))|lf
A,lf=inpaint_copy(A,hole&rugp,rv,d2,ret_left=True)
A,lf=inpaint_copy(A,lf,rv,d1,ret_left=True)
A=inpaint_copy(A,lf,rv,np.array([0.,1.])); hole&=~rugp
A=inpaint_blend(A,hole,clean&~rugp&tile,d2)
Image.fromarray(A).save("w-wait-shell.png")
A0=np.asarray(im)
for k,m in masks.items():
    ys,xs=np.nonzero(m); s=np.zeros_like(A0); s[m]=A0[m]
    Image.fromarray(s[ys.min():ys.max()+1,xs.min():xs.max()+1]).save("w-spw-%s.png"%k)
json.dump({k:[int(np.nonzero(m)[1].min()),int(np.nonzero(m)[0].min())] for k,m in masks.items()},open("w-wait-boxes.json","w"))
b=Image.new("RGB",im.size,(15,20,32)); s_=Image.fromarray(A); b.paste(s_,(0,0),s_); b.resize((957,670)).save("wv-w1.png")
