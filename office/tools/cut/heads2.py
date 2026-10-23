import numpy as np, json
from PIL import Image
out={}
for i in range(1,42):
    im=np.asarray(Image.open("n41/raw%02d.png"%i)).astype(int)
    a=im[...,3]>128; ys=np.nonzero(a.any(1))[0]; top,bot=ys[0],ys[-1]; H=bot-top
    xs=np.nonzero(a.any(0))[0]; cx=(xs[0]+xs[-1])//2; W=xs[-1]-xs[0]
    r,g,b=im[...,0],im[...,1],im[...,2]
    skin=a&(r>140)&(r>g+12)&(g>b+8)&(r-b>45)&(r-b<140)
    band=skin[top:top+int(H*.36),cx-int(W*.18):cx+int(W*.18)]
    rows=np.nonzero(band.sum(1)>3)[0]
    chin=int(rows.max()) if len(rows) else int(H*.2)
    eyesonly = len(rows) and (rows.max()-rows.min())<H*.05
    if eyesonly: chin=int(rows.max()+H*.07)
    out[i]=dict(top=int(top),H=int(H),chin=chin,chinf=round(chin/H,3),cx=int(cx),niq=bool(eyesonly))
    print(i,out[i]["chinf"],out[i]["niq"])
json.dump(out,open("heads.json","w"))
