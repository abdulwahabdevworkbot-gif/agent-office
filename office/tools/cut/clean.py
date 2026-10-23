import json, os, numpy as np
from PIL import Image
from scipy import ndimage as ndi
from seg import fg_mask
R="src/"
SRC={"N":"src/chars41.png","G":"src/games.png","A":"c31fe783-image.png","B":"ref5-sheet.png","C":"79de6443-image.png","P":"05ad477f-image.png","H":"6dc6e69a-image.png"}
def matte(im,fg,bg):
    """soft alpha on the 2px rim, colour un-blended from the background; drop the grey floor shadow"""
    im=im.astype(float); d=np.abs(im-bg).max(axis=2)
    rim=fg & ~ndi.binary_erosion(fg,iterations=2)
    a=np.where(fg,1.0,0.0)
    a[rim]=np.clip((d[rim]-4)/40,0,1)
    out=im.copy()
    aa=np.maximum(a,1e-3)[...,None]
    out=np.where(rim[...,None],(im-(1-aa)*bg)/aa,im)
    return np.clip(out,0,255),a
def shadow_fix(rgb,a,full):
    if not full: return rgb,a
    h=a.shape[0]; ys=np.arange(h)[:,None]
    br=rgb.mean(axis=2); sat=rgb.max(axis=2)-rgb.min(axis=2)
    sh=(ys>h*0.93)&(br>175)&(sat<22)&(a>0)
    a=a.copy(); a[sh]=np.clip((240-br[sh])/90,0,0.35)
    rgb=rgb.copy(); rgb[sh]=40
    return rgb,a
def holes(rgb,a):
    """face hole of a head cover: flat near-white area holding the upper-centre point"""
    h,w=a.shape; wh=(rgb.min(axis=2)>236)&(rgb.max(axis=2)-rgb.min(axis=2)<14)&(a>0.5)
    lab,n=ndi.label(wh)
    for fy in (0.42,0.5,0.35,0.55):
        l=lab[int(h*fy),w//2]
        if l: 
            m=lab==l
            if m.sum()<0.5*(a>0.5).sum():
                m=ndi.binary_dilation(m,iterations=1)
                a=a.copy(); a[m]=0; return a
    return a
cache={}
def src(key):
    if key not in cache: cache[key]=fg_mask(SRC[key] if SRC[key].startswith("..") else R+SRC[key])
    return cache[key]
def cut(key,box,full=False,hole=False,dil=3):
    im,fg,bg=src(key); x0,y0,x1,y1=box
    sub=fg[y0:y1,x0:x1]
    lab,n=ndi.label(ndi.binary_dilation(sub,iterations=dil))
    sizes=ndi.sum(sub,lab,range(1,n+1)); keep=lab==(1+int(np.argmax(sizes)))
    m=sub&keep
    rgb,a=matte(im[y0:y1,x0:x1],m,bg)
    rgb,a=shadow_fix(rgb,a,full)
    if hole: a=holes(rgb,a)
    ys,xs=np.nonzero(a>0.02)
    rgb=rgb[ys.min():ys.max()+1,xs.min():xs.max()+1]; a=a[ys.min():ys.max()+1,xs.min():xs.max()+1]
    return Image.fromarray(np.dstack([rgb,a*255]).astype(np.uint8))
