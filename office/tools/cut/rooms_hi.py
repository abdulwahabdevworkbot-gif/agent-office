# cut the owner's high-resolution room pictures (one room per picture, dark navy background)
import os, glob, numpy as np
from PIL import Image
from scipy import ndimage as ndi
os.makedirs("rooms",exist_ok=True)
for f in sorted(glob.glob("src/hi/*.png")):
    name=os.path.basename(f)[:-4]
    if name.startswith("seated"): continue
    c=np.asarray(Image.open(f).convert("RGB")).astype(float)
    r,g,b=c[...,0],c[...,1],c[...,2]
    navy=(c.max(axis=2)<80)&(b-r>14)
    lab,n=ndi.label(navy)
    edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
    fg=~np.isin(lab,list(edge))
    lab2,n2=ndi.label(fg); sz=ndi.sum(fg,lab2,range(1,n2+1)); fg=lab2==(1+int(np.argmax(sz)))
    fg=ndi.binary_fill_holes(fg)
    bg=np.median(np.concatenate([c[0],c[-1],c[:,0],c[:,-1]]),axis=0)
    d=np.abs(c-bg).max(axis=2)
    a=fg.astype(float)
    rim=fg&~ndi.binary_erosion(fg,iterations=2); a[rim]=np.clip((d[rim]-8)/45,0,1)
    # unblend the navy from the soft rim
    al=np.clip(a,1e-3,1)[...,None]; c=np.where(rim[...,None],np.clip((c-bg*(1-al))/al,0,255),c)
    ys,xs=np.nonzero(fg)
    rgba=np.dstack([c,a*255])[ys.min():ys.max()+1,xs.min():xs.max()+1].astype(np.uint8)
    Image.fromarray(rgba).save("rooms/%s.png"%name); print(name,rgba.shape[1],rgba.shape[0])
