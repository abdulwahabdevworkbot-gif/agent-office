import json, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
from clean import cut
idx=json.load(open("out/index.json"))
TAG="@Abdulwahabdev"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def tag(im, fy=0.86, size=11):
    """tiny low-contrast credit on the figure: shade of the pixels under it"""
    im=im.copy(); W,H=im.size
    f=ImageFont.truetype(FONT,size)
    tw=f.getlength(TAG); x=int((W-tw)/2); y=int(H*fy)
    arr=np.asarray(im).astype(int)
    patch=arr[y:y+size+2,max(x,0):int(x+tw)]
    m=patch[...,3]>200
    base=patch[...,:3][m].mean(axis=0) if m.any() else np.array([128,128,128])
    lum=base.mean(); col=tuple(int(c) for c in (base-24 if lum>110 else base+28))
    txt=Image.new("L",im.size,0); ImageDraw.Draw(txt).text((x,y),TAG,font=f,fill=255)
    t=(np.asarray(txt)/255.0)*(np.asarray(im)[...,3]>200)
    a=np.asarray(im).astype(float).copy()
    for c in range(3): a[...,c]=a[...,c]*(1-t)+col[c]*t
    a=a.astype(np.uint8)
    return Image.fromarray(a)
def fit(im,W=216,H=600):
    s=min(H/im.height,(W-4)/im.width); im=im.resize((max(1,round(im.width*s)),round(im.height*s)),Image.LANCZOS)
    c=Image.new("RGBA",(W,H),(0,0,0,0)); c.paste(im,((W-im.width)//2,H-im.height),im); return c
CH=["A%02d"%i for i in range(1,19)]+["B%02d"%i for i in range(1,11)]+["B%02d"%i for i in range(30,42)]+["C01"]
os.makedirs("chars",exist_ok=True)
def _main():
  for i,k in enumerate(CH,1):
    im=fit(cut(k[0],idx[k],full=True)); im=tag(im)
    im.save("chars/%02d.png"%i)
if __name__=="__main__": _main()
