# one room picture from the owner: cut it off its dark background and fit it on the 1200 x 896 room canvas
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi
src, out = sys.argv[1], sys.argv[2]
im=np.asarray(Image.open(src).convert("RGB")).astype(float)
bg=np.median(np.concatenate([im[:4].reshape(-1,3),im[-4:].reshape(-1,3)]),axis=0); d=np.abs(im-bg).max(2)
fg=ndi.binary_fill_holes(d>28); lab,n=ndi.label(fg); sz=ndi.sum(fg,lab,range(1,n+1)); fg=lab==1+int(np.argmax(sz))
a=ndi.gaussian_filter(ndi.binary_erosion(fg,iterations=1).astype(float),.6)
ys,xs=np.nonzero(fg); room=Image.fromarray(np.dstack([im,a*255]).astype(np.uint8)).crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
W,H=1200,896; sc=min((W-8)/room.width,(H-50)/room.height)
room=room.resize((round(room.width*sc),round(room.height*sc)),Image.LANCZOS)
if sc>1: room=room.filter(ImageFilter.UnsharpMask(1.2,40,2))
cv=Image.new("RGBA",(W,H),(0,0,0,0)); cv.paste(room,((W-room.width)//2,(H-50-room.height)//2+8),room)
FB=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
dr=ImageDraw.Draw(cv); t="@Abdulwahabdev"; tw=dr.textlength(t,font=FB); tx,ty=W-tw-18,H-34
for dx,dy in ((1,1),(2,2)): dr.text((tx+dx,ty+dy),t,font=FB,fill=(0,0,0,150))
dr.text((tx,ty),t,font=FB,fill=(255,255,255,235)); cv.save(out,quality=90)
g=Image.new("RGB",(W,H),(15,20,32)); g.paste(cv,(0,0),cv); gd=ImageDraw.Draw(g); f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",15)
for p in range(0,101,5):
    X=W*p/100; Y=H*p/100; col=(255,0,0) if p%10==0 else (255,150,0)
    gd.line([(X,0),(X,H)],fill=col,width=1); gd.line([(0,Y),(W,Y)],fill=col,width=1)
    if p%10==0: gd.text((X+2,2),str(p),fill=(255,40,40),font=f); gd.text((2,Y+2),str(p),fill=(255,40,40),font=f)
g.save(out.rsplit(".",1)[0]+"-grid.png"); print(room.size)
