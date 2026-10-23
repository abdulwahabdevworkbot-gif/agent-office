from PIL import Image; import numpy as np, glob, colorsys, json, sys
D='site/assets/chars/'; O='masks/out/'
import os; os.makedirs(O,exist_ok=True)
# ref color, tolerance, y band (fraction of height)
CFG={
 'Claude-1':        {'hair':[(75,40,30),70,0,.2],   'shirt':[(225,200,165),70,.31,.56]},
 'Frontend-dev-1':  {'hair':[(160,55,30),85,0,.42], 'shirt':[(72,120,55),70,.26,.58]},
 'Me-1':            {'hair':[(40,40,40),55,0,.3],   'shirt':[(238,238,238),55,.3,.56]},
 'dev-1':           {'hair':None,                   'shirt':[(24,24,24),60,.3,.56]},
 'dev-2':           {'hair':[(0,160,140),90,0,.3],  'shirt':[(240,190,0),90,.3,.63]},
 'employee-1':      {'hair':[(80,45,30),42,0,.2],   'shirt':[(65,65,70),45,.27,.62]},
 'employee-2':      {'hair':[(50,30,50),55,0,.3],   'shirt':[(48,96,144),70,.3,.6]},
 'employee-3':      {'hair':[(20,20,25),45,0,.2],   'shirt':[(24,48,72),45,.27,.6]},
 'explore-1':       {'hair':[(85,45,25),60,0,.2],   'shirt':[(110,22,22),95,.27,.57]},
 'security-audit-1':{'hair':[(10,5,10),40,0,.3],    'shirt':[(22,22,22),40,.3,.62]},
}
def skin(px):
    r,g,b=px[...,0]/255,px[...,1]/255,px[...,2]/255
    mx=np.maximum(np.maximum(r,g),b); mn=np.minimum(np.minimum(r,g),b)
    return (r>=g)&(g>=b)&(mx>.55)&((mx-mn)/np.maximum(mx,1e-6)>.18)&((mx-mn)/np.maximum(mx,1e-6)<.6)
rows=[]
for name,c in CFG.items():
  for d in ['front-left','front-right','rear-left','rear-right']:
    im=Image.open(f'{D}{name}-{d}.webp').convert('RGBA'); a=np.array(im).astype(float); H,W,_=a.shape
    yy=np.arange(H)[:,None].repeat(W,1)/H
    m=np.zeros((H,W,3),np.uint8); vis=a.copy()
    for ch,key in ((0,'hair'),(1,'shirt')):
      if not c[key]: continue
      ref,tol,y0,y1=c[key]
      dist=np.sqrt(((a[...,:3]-np.array(ref))**2).sum(-1))
      sel=(dist<tol)&(a[...,3]>40)&(yy>=y0)&(yy<y1)
      if key=='shirt' or name!='dev-1': sel&=~skin(a) if not (key=='shirt' and name=='Claude-1') else sel
      m[...,ch]=sel*255
      vis[sel,:3]=[255,0,0] if ch==0 else [0,220,0]
    Image.fromarray(np.dstack([m[...,0],m[...,1],m[...,2],np.where(a[...,3]>0,255,0).astype(np.uint8)]).astype(np.uint8),'RGBA').save(f'{O}{name}-{d}.png',optimize=True)
    rows.append(Image.fromarray(np.uint8(vis)))
W=sum(r.width for r in rows[:40:4]); c2=Image.new('RGBA',(W*1,400),(200,200,200,255)); x=0
for i in range(0,40,4):
    c2.alpha_composite(Image.open(D+list(CFG)[i//4]+'-front-left.webp').convert('RGBA'),(x,0)); c2.alpha_composite(rows[i],(x,200)); x+=rows[i].width
c2.save('masks/vis.png')
