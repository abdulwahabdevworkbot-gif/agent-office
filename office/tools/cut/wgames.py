import numpy as np, json
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from widen import *
RUG={"lounge":[(636,456),(935,368),(1260,540),(965,634)],"left":[(172,676),(300,604),(480,700),(335,772)]}
SP={
 "beanbag-orange":([(95,560),(150,515),(240,520),(268,580),(255,655),(170,665),(98,632)],None),
 "left":([(198,640),(260,598),(342,598),(382,650),(374,722),(290,734),(203,704)],"left"),
 "pool":([(288,495),(550,378),(732,466),(728,566),(696,574),(472,676),(434,680),(318,608),(294,562)],None),
 "lounge":([(690,410),(840,300),(870,300),(930,300),(1000,380),(988,450),(940,470),(930,418),(1000,420),(1030,460),(1090,450),(1156,460),(1182,520),(1166,588),(1060,588),(1030,560),(1022,572),(950,574),(888,535),(800,532),(776,532),(694,476)],"lounge"),
 "foos":([(588,665),(735,598),(786,608),(912,674),(922,722),(916,820),(900,862),(800,905),(750,900),(612,800),(590,702)],None),
 "pingpong":([(900,660),(1026,574),(1152,540),(1316,632),(1310,742),(1286,748),(1088,850),(1058,846),(937,770),(904,706)],None),
 "cabinet":([(326,700),(400,664),(476,688),(476,856),(420,866),(330,784)],None),
 "planters":([(436,790),(440,690),(500,690),(560,730),(640,800),(640,955),(575,961),(440,844)],None),
 "planterbox":([(596,880),(640,820),(726,846),(734,1006),(690,1011),(600,964)],None),
}
im=Image.open("rooms/games.png").convert("RGBA"); A=np.asarray(im).copy(); c=A[...,:3].astype(int); a=A[...,3]
masks={}
for k,(pts,rug) in SP.items():
    m=sprite_mask(c,a,pts)
    if rug: m|=ndi.binary_dilation(poly_mask(a.shape,RUG[rug]),iterations=7)
    m=ndi.binary_dilation(m,iterations=1)&ndi.binary_dilation(poly_mask(a.shape,pts)|(poly_mask(a.shape,RUG[rug]) if rug else False),iterations=4)
    masks[k]=m
EX=poly_mask(a.shape,[(709,380),(800,380),(800,700),(719,700),(719,462),(709,462)])
masks["lounge"]&=~(poly_mask(a.shape,SP["pool"][0])&~EX)
masks["pool"]&=~EX&~poly_mask(a.shape,SP["left"][0])
masks["foos"]&=~poly_mask(a.shape,SP["planterbox"][0])&~poly_mask(a.shape,SP["planters"][0])
hole=np.zeros(a.shape,bool)
for m in masks.values(): hole|=m
hole&=a>20
for jp in ([(420,540),(465,540),(465,580),(420,580)],[(770,755),(835,755),(835,805),(770,805)]): hole|=poly_mask(a.shape,jp)&(a>20)
r,g,b=c[...,0],c[...,1],c[...,2]
wood=(r>225)&(g>165)&(g<228)&(b>100)&(b<190)&(r-b>55)
ZONE=[(0,620),(0,598),(640,325),(700,300),(760,280),(1425,590),(1425,1053),(0,1053)]
slab=(r>145)&(r<195)&(g>100)&(g<140)&(b>60)&(b<100)
hi=(r>240)&(g>215)&(b>160)&(b<205)
ol=(r>55)&(r<135)&(g>40)&(g<100)&(b>30)&(b<75)&(r>g)&(g>b)
line0=635+0.634*(np.mgrid[0:a.shape[0],0:a.shape[1]][1]-50); yy0=np.mgrid[0:a.shape[0],0:a.shape[1]][0]
xx0=np.mgrid[0:a.shape[0],0:a.shape[1]][1]
nearedge=((xx0<725)&(yy0>line0-44))|((xx0>745)&(xx0<1290)&(yy0>1405.1-0.4988*xx0-44))
valid=poly_mask(a.shape,ZONE)&~ndi.binary_dilation(hole,iterations=3)&(wood|((slab|hi|ol)&nearedge)&(a>250))
d=np.array([1,0.5]); d=d/np.linalg.norm(d)
# the front-left edge: fill along the edge itself so the rim stays a clean line
H,W=a.shape; xs_=np.arange(W); bot=np.array([ (np.nonzero(a[:,x]>128)[0].max() if (a[:,x]>128).any() else 0) for x in xs_])
yy,xx=np.mgrid[0:H,0:W]; line=635+0.634*(xx-50); band=(xx<725)&(yy>line-44)&(yy<line+6)
e=np.array([1,0.635]); e=e/np.linalg.norm(e)
band2=(xx>745)&(yy>1405.1-0.4988*xx-44)&(yy<1405.1-0.4988*xx+6)&(xx<1285)
e2=np.array([1,-0.494]); e2=e2/np.linalg.norm(e2)
A=inpaint_blend(A,hole&band2,valid&band2&(xx<1290),e2); hole=hole&~band2
shell=inpaint_blend(A,hole&band,valid&band,e)
shell=inpaint_blend(shell,hole&~band,valid,d)
Image.fromarray(shell).save("w-games-shell.png")
for k,m in masks.items():
    ys,xs=np.nonzero(m); s=np.zeros_like(A); s[m]=A[m]
    Image.fromarray(s[ys.min():ys.max()+1,xs.min():xs.max()+1]).save("w-sp-%s.png"%k)
json.dump({k:[int(np.nonzero(m)[1].min()),int(np.nonzero(m)[0].min())] for k,m in masks.items()},open("w-games-boxes.json","w"))
