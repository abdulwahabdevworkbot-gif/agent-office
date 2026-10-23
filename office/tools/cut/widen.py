# widen a room: lift the free-standing furniture off, fill the floor under it from the floor itself,
# stretch the empty room by repeating a strip of floor and wall, then put the furniture back further apart
import numpy as np, json, sys
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
def floorish(c):
    r,g,b=c[...,0],c[...,1],c[...,2]
    wood=(r>225)&(g>160)&(g<230)&(b>90)&(b<190)&(r-b>55)
    rug=(r>185)&(abs(r-g)<16)&(r-b>8)&(r-b<60)
    return wood|rug
def poly_mask(shape,pts):
    m=Image.new("L",(shape[1],shape[0]),0); ImageDraw.Draw(m).polygon([tuple(p) for p in pts],fill=255); return np.asarray(m)>0
def sprite_mask(c,a,pts):
    """the item inside its outline polygon: everything except the floor that reaches the polygon edge"""
    pm=poly_mask(a.shape,pts)
    fl=floorish(c)&(a>=250)&pm
    ring=pm&~ndi.binary_erosion(pm,iterations=2)
    lab,n=ndi.label(fl); edge=np.unique(lab[ring&fl]); edge=edge[edge>0]
    m=pm&~np.isin(lab,edge)
    m=ndi.binary_opening(m,iterations=1); m=ndi.binary_fill_holes(m)
    return ndi.binary_dilation(m,iterations=2)&pm
def inpaint(c,hole,valid,dirs,K=900):
    out=c.copy(); todo=hole.copy(); H,W=hole.shape
    ys,xs=np.nonzero(todo)
    for k in range(1,K):
        if not len(ys): break
        best=None
        for (dx,dy) in dirs:
            for s in (1,-1):
                X=np.round(xs+s*k*dx).astype(int); Y=np.round(ys+s*k*dy).astype(int)
                ok=(X>=0)&(X<W)&(Y>=0)&(Y<H)
                ok2=np.zeros(len(xs),bool); ok2[ok]=valid[Y[ok],X[ok]]
                sel=ok2&(best is None or True)
                if sel.any():
                    out[ys[sel],xs[sel]]=c[Y[sel],X[sel]]
                    keep=~sel; ys,xs=ys[keep],xs[keep]
                    if not len(ys): break
            if not len(ys): break
    return out
def widen(img,cut,t,s_of_y):
    """cut: x of the seam for every row (old coords); rows right of it move by (t, t*s(y))"""
    H,W,_=img.shape; dyt=[t*s_of_y(y) for y in range(H)]
    pad_top=int(np.ceil(max(0,-min(dyt)))); pad_bot=int(np.ceil(max(0,max(dyt))))
    NH,NW=H+pad_top+pad_bot,W+int(np.ceil(t))
    out=np.zeros((NH,NW,4),np.uint8)
    yy,xx=np.mgrid[0:NH,0:NW]; oy=yy-pad_top
    # left part: as it was
    # source for every new pixel
    sy=oy.astype(float); sx=xx.astype(float)
    cutn=np.interp(np.clip(oy,0,H-1),np.arange(H),cut)
    right=xx>=cutn
    # for the right part, find the old row: y_new = y_old + t*s(y_old) ~ solve with one fixed-point step
    s=np.array([s_of_y(y) for y in range(H)])
    y0=oy.astype(float); 
    for _ in range(3): y0=oy - t*np.interp(np.clip(y0,0,H-1),np.arange(H),s)
    sy=np.where(right,y0,oy); sx=np.where(right,xx-t,xx)
    # the seam itself must be judged in old coords of the source pixel
    syi=np.round(sy).astype(int); sxi=np.round(sx).astype(int)
    ok=(syi>=0)&(syi<H)&(sxi>=0)&(sxi<W)
    out[ok]=img[syi[ok],sxi[ok]]
    return out,pad_top
def inpaint_blend(c,hole,valid,d,K=1500):
    """fill along the plank direction d, blending the nearest clean floor on both sides"""
    out=c.astype(float).copy(); H,W=hole.shape
    ys,xs=np.nonzero(hole); n=len(ys)
    res=[]
    for s in (1,-1):
        col=np.zeros((n,c.shape[2])); dist=np.full(n,np.inf); left=np.ones(n,bool)
        for k in range(1,K):
            if not left.any(): break
            X=np.round(xs+s*k*d[0]).astype(int); Y=np.round(ys+s*k*d[1]).astype(int)
            inb=(X>=0)&(X<W)&(Y>=0)&(Y<H)
            left&=inb
            hit=np.zeros(n,bool); idx=np.nonzero(left)[0]; hit[idx]=valid[Y[idx],X[idx]]
            col[hit]=c[Y[hit],X[hit]]; dist[hit]=k; left&=~hit
        res.append((col,dist))
    (c1,k1),(c2,k2)=res
    w1=np.where(np.isinf(k1),0,np.where(np.isinf(k2),1,k2/(k1+k2+1e-9)))[:,None]
    w2=np.where(np.isinf(k2),0,1-w1[:,0])[:,None]
    got=(w1[:,0]+w2[:,0])>0
    out[ys[got],xs[got]]=(c1*w1+c2*w2)[got]
    return np.clip(out,0,255).astype(np.uint8)
def inpaint_copy(c,hole,valid,d,K=1500,ret_left=False):
    """fill from the nearest clean pixel along d (either side), no blending, so texture stays crisp"""
    out=c.copy(); H,W=hole.shape; ys,xs=np.nonzero(hole); n=len(ys)
    best=np.full(n,np.inf); bx=np.zeros(n,int); by=np.zeros(n,int)
    for s in (1,-1):
        left=np.ones(n,bool)
        for k in range(1,K):
            if not left.any(): break
            X=np.round(xs+s*k*d[0]).astype(int); Y=np.round(ys+s*k*d[1]).astype(int)
            inb=(X>=0)&(X<W)&(Y>=0)&(Y<H); left&=inb
            idx=np.nonzero(left)[0]; hit=np.zeros(n,bool); hit[idx]=valid[Y[idx],X[idx]]
            upd=hit&(k<best); best[upd]=k; bx[upd]=X[upd]; by[upd]=Y[upd]; left&=~hit
    got=np.isfinite(best); out[ys[got],xs[got]]=c[by[got],bx[got]]
    left=np.zeros_like(hole); left[ys[~got],xs[~got]]=True
    return (out,left) if ret_left else out
