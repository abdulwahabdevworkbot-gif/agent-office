import numpy as np, json, os
from PIL import Image
HD=json.load(open("heads.json"))
FIX={10:.27,17:.27,36:.27}
ROW={1:1,2:1,3:2,4:3,5:4,6:4,7:5,8:6,9:7,10:7,11:8,12:10,13:11,14:8,15:12,16:9,17:6,18:6,19:1,20:1,21:1,22:1,23:1,24:3,25:3,26:1,27:2,28:2,
     29:4,30:5,31:5,32:5,33:5,34:4,35:4,36:4,37:4,38:5,39:5,40:12,41:5}
def head(i):
    h=HD[str(i)]; im=Image.open("n41/raw%02d.png"%i)
    cf=min(FIX.get(i,h["chinf"]),.30); y1=h["top"]+int(h["H"]*(cf+.03))
    hd=im.crop((0,h["top"],im.width,y1)); bb=hd.getbbox(); return hd.crop(bb), h["H"]
def neck_of(body):
    a=np.asarray(body)[...,3]>128; ys=np.nonzero(a.any(1))[0]; top=ys[0]
    # neck: centre of the top 4 rows of the torso
    xs=np.nonzero(a[top:top+4].any(0))[0]; return (xs[0]+xs[-1])/2, top
def shoulders(body):
    a=np.asarray(body)[...,3]>128; ys=np.nonzero(a.any(1))[0]; top=ys[0]
    r=a[top+int(body.height*.14)]; xs=np.nonzero(r)[0]; return np.ptp(xs)+1 if len(xs) else 20
def compose(i,col,S=4):
    """body cell scaled up S times, the character's head on its neck"""
    body=Image.open("seat/b%02d-%d.png"%(ROW[i],col)); body=body.resize((body.width*S,body.height*S),Image.LANCZOS)
    hd,H=head(i)
    ref=Image.open("seat/b%02d-1.png"%ROW[i]); shw=shoulders(ref)*S
    # standing figure: shoulders are about 1.45 head widths in this art
    s=(shw/1.45)/hd.width; hd=hd.resize((max(1,round(hd.width*s)),max(1,round(hd.height*s))),Image.LANCZOS)
    nx,ny=neck_of(body)
    W=max(body.width,hd.width)+20; top_pad=hd.height
    c=Image.new("RGBA",(W+40,body.height+top_pad),(0,0,0,0)); ox=20+(W-body.width)//2
    c.paste(body,(ox,top_pad),body)
    hx=int(ox+nx-hd.width/2); hy=int(top_pad+ny-hd.height+hd.height*.06)
    c.paste(hd,(hx,hy),hd); return c.crop(c.getbbox())
if __name__=="__main__":
    os.makedirs("comp",exist_ok=True)
    picks=[1,2,5,7,9,12,13,16,18,23,28,40]
    S=Image.new("RGB",(9*230,len(picks)*230),(244,241,234))
    for r,i in enumerate(picks):
        for col in range(1,10):
            c=compose(i,col); c.thumbnail((220,220)); S.paste(c,((col-1)*230+5,r*230+5),c)
    S.save("comp-sample.png")
