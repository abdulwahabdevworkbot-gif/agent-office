# heads for the other views, cut from the owner's turnaround sheets: b (back) and r (right profile) for each character.
# Each head is scaled so the figure it came from has the same height as the character's front figure.
import numpy as np, json, os
from PIL import Image
from scipy import ndimage as ndi
from clean import matte
from seatcomp import head, FIX
HD=json.load(open("heads.json")); SEG=json.load(open("turnseg.json"))
# sheet figure index for (right, back, left); None = not drawn. A missing right view is the left one mirrored.
T1={1:(0,1,2),2:(3,4,5),3:(6,7,8),4:(9,10,11),5:(12,13,15),6:(16,17,18),7:(19,20,21),8:(22,23,24),9:(25,26,None),10:(None,None,28),
    11:(29,30,31),12:(32,33,34),13:(35,36,37),14:(38,39,40),15:(41,42,43),16:(44,45,46),17:(47,48,49),18:(50,51,52),19:(53,54,55),20:(56,57,58),21:(59,60,61)}
T2={22:(0,1,2),23:(3,4,5),24:(6,7,8),25:(9,10,11),26:(12,13,14),27:(15,16,17),28:(18,19,20),29:(21,22,23),30:(24,25,26),31:(27,28,29),
    32:(30,31,32),33:(33,34,35),34:(36,37,38),35:(39,40,None),36:(None,None,41),37:(46,47,48),38:(49,50,51),39:(52,53,54),40:(55,56,57),41:(58,59,60)}
IM={s:np.asarray(Image.open(f"src/hi/{s}.png").convert("RGB")).astype(float) for s in ("turn1","turn2")}
def figure(sheet,k):
    x0,y0,x1,y1,_=SEG[sheet][k]; im=IM[sheet]; pad=6
    c=im[max(y0-pad,0):y1+pad,max(x0-pad,0):x1+pad]
    bg=np.median(np.concatenate([c[0],c[-1]]),axis=0); d=np.abs(c-bg).max(2)
    fg=ndi.binary_fill_holes(ndi.binary_closing(d>22,iterations=1))
    lab,n=ndi.label(fg); cx=c.shape[1]//2
    # the figure is the blob under the box centre; neighbours that leak into the box are dropped
    col=lab[:,cx-3:cx+4]; ids,cnt=np.unique(col[col>0],return_counts=True); keep=ids[np.argmax(cnt)]
    fg=lab==keep; rgb,a=matte(c,fg,bg)
    ys=np.nonzero(fg.any(1))[0]; return np.dstack([rgb,a*255]).astype(np.uint8), ys[0], ys[-1]-ys[0]
def cut_head(sheet,k,i):
    im,top,H=figure(sheet,k); cf=min(FIX.get(i,HD[str(i)]["chinf"]),.30)
    hd=Image.fromarray(im[top:top+int(H*(cf+.03))]); return hd.crop(hd.getbbox()), H
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),"out-heads"); os.makedirs(A,exist_ok=True)
meta={}
for i in range(1,42):
    T=T1 if i<=21 else T2; sheet="turn1" if i<=21 else "turn2"; R,B,L=T[i]
    fh,FH=head(i); sf=96/fh.width; ref=FH*sf          # front head: 96 wide; ref = front figure height in those units
    meta[i]={}
    for v,k,mir in (("b",B,False),("r",R if R is not None else L,R is None)):
        if k is None: continue
        hd,H=cut_head(sheet,k,i)
        if mir: hd=hd.transpose(Image.FLIP_LEFT_RIGHT)
        s=ref/H; w,h=hd.width*s,hd.height*s
        hd.resize((round(w*1.5),round(h*1.5)),Image.LANCZOS).save(f"{A}/c{i:02d}-{v}.png")
        meta[i][v]=[round(w,1),round(h,1)]
json.dump(meta,open("turnheads.json","w"))
S=Image.new("RGB",(41*70,3*90),(90,110,140))
for i in range(1,42):
    for j,v in enumerate(("f","b","r")):
        p=f"{A}/c{i:02d}-{v}.png" if v!="f" else os.path.join(os.path.dirname(os.path.abspath(__file__)),f"../../assets/heads/c{i:02d}.webp")
        if os.path.exists(p): h=Image.open(p).convert("RGBA"); h.thumbnail((66,86)); S.paste(h,((i-1)*70+2,j*90+2),h)
S.save("turnheads.png")
