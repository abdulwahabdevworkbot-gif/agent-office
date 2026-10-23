# the owner's second seated pose library: 14 outfits x 10 seat types, one cell per pose
import os, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from clean import matte
im=np.asarray(Image.open("src/hi/seated2.png").convert("RGB")).astype(int)
cols=[(171,258),(287,380),(412,514),(538,631),(671,771),(804,890),(931,1023),(1058,1164),(1201,1303),(1346,1425)]
rows=[100,170,240,313,388,460,534,604,674,744,812,883,949,1013,1084]
os.makedirs("seat2",exist_ok=True)
def nodesk(c,fg,col,d):
    """back views (cols 3, 4): the desk behind the person goes. Its top is the row band that crosses the whole cell;
    from there down, anything outside the person's shoulders (col 3) or left of them (col 4) is desk"""
    H,W=fg.shape; cnt=fg.sum(1)
    band=[y for y in range(H) if cnt[y]>(.62 if col==3 else .5)*W] if col==3 else []
    if col==4: band=[y for y in range(H) if fg[y,:int(W*.14)].any()]
    if not band: return fg
    y0=min(band); ref=y0-3
    while ref>0 and not fg[ref].any(): ref-=1
    xs=np.nonzero(fg[max(ref-2,0):ref+1].any(0))[0]
    if not len(xs): return fg
    x0,x1=xs.min()-2,xs.max()+2
    out=fg.copy()
    if col==3: out[y0-2:,:x0]=False; out[y0-2:,x1+1:]=False
    else:
        r,g,b=c[...,0],c[...,1],c[...,2]; wood=(r>140)&(r-b>70)&(r-g>35)&(g>70)
        wood=ndi.binary_dilation(wood,iterations=2); wood[:,int(W*.35):]=False; wood[:y0-3]=False
        out[wood]=False
        out[y0+6:,:int(W*.07)]=False
        cand=d<18; lab,n=ndi.label(cand); out0=out.copy(); out0[0]=out0[-1]=out0[:,0]=out0[:,-1]=False
        bad=np.unique(lab[cand&~out0]); out[np.isin(lab,bad[bad>0])]=False
        sat=c.max(2)-c.min(2); grey=out&(sat<28)
        for x in range(int(W*.16)):
            if grey[y0:,x].sum()>.45*(H-y0): out[y0-2:,x]=False
    lab,n=ndi.label(out); sz=ndi.sum(out,lab,range(1,n+1)); return lab==1+int(np.argmax(sz))
for ri in range(14):
    for ci,(a,b) in enumerate(cols):
        y0,y1=rows[ri]+1,rows[ri+1]; x0,x1=a-12,b+12; c=im[y0:y1,x0:x1].astype(float)
        border=np.concatenate([c[0],c[-1],c[:,0],c[:,-1]]); bg=np.median(border,axis=0)
        d=np.abs(c-bg).max(axis=2); cand=d<16; lab,n=ndi.label(cand)
        edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
        fg=~np.isin(lab,list(edge)); fg=ndi.binary_opening(fg,iterations=1)
        l2,n2=ndi.label(ndi.binary_dilation(fg,iterations=2)); sz=ndi.sum(fg,l2,range(1,n2+1)); fg=fg&(l2==1+int(np.argmax(sz)))
        if ci in (2,3): fg=nodesk(c,fg,ci+1,d)
        rgb,a_=matte(c,fg,bg)
        ys,xs=np.nonzero(a_>0.02)
        out=np.dstack([rgb,a_*255])[ys.min():ys.max()+1,xs.min():xs.max()+1].astype(np.uint8)
        Image.fromarray(out).save("seat2/b%02d-%d.png"%(ri+1,ci+1))
