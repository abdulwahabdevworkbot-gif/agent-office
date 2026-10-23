import sys, numpy as np
from PIL import Image
from scipy import ndimage as ndi
def fg_mask(path, tol=14):
    im=np.asarray(Image.open(path).convert('RGB')).astype(int)
    h,w,_=im.shape
    # bg estimate: median of border
    border=np.concatenate([im[0],im[-1],im[:,0],im[:,-1]])
    bg=np.median(border,axis=0)
    d=np.abs(im-bg).max(axis=2)
    cand=d<tol
    lab,n=ndi.label(cand)
    edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
    bgm=np.isin(lab,list(edge))
    fg=~bgm
    fg=ndi.binary_opening(fg,iterations=1)
    return im,fg,bg
if __name__=="__main__":
    for p in sys.argv[1:]:
        im,fg,bg=fg_mask(p)
        lab,n=ndi.label(ndi.binary_dilation(fg,iterations=3))
        objs=ndi.find_objects(lab)
        sizes=ndi.sum(fg,lab,range(1,n+1))
        boxes=[(o[1].start,o[0].start,o[1].stop,o[0].stop,int(s)) for o,s in zip(objs,sizes) if s>300]
        print(p,bg,len(boxes))
        for b in sorted(boxes,key=lambda b:(b[1]//80,b[0])): print("  ",b)
