# the owner's rooms without chairs (one sheet, 3x3): each room cut out and laid exactly over the room it replaces
import numpy as np, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi
A=os.path.join(os.path.dirname(os.path.abspath(__file__)),"../../assets/rooms")
im=np.asarray(Image.open("src/hi/nochairs.png").convert("RGB")).astype(float)
XS=[(0,508),(515,1020),(1028,1536)]; YS=[(0,351),(359,684),(694,1024)]
NAMES=[["main-b","main-a","boss"],["huddle","meet-10","meet-20"],["meet-30","game","idle"]]
FB=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
def biggest(m):
    lab,n=ndi.label(m); sz=ndi.sum(m,lab,range(1,n+1)); return lab==1+int(np.argmax(sz))
os.makedirs("nc",exist_ok=True)
for r,(y0,y1) in enumerate(YS):
    for c,(x0,x1) in enumerate(XS):
        name=NAMES[r][c]; cell=im[y0:y1,x0:x1]
        bg=np.array([11,20,32.]); d=np.abs(cell-bg).max(2)
        fg=biggest(ndi.binary_fill_holes(d>28)); fg=ndi.binary_erosion(fg,iterations=1)
        a=ndi.gaussian_filter(fg.astype(float),.6)
        ys,xs=np.nonzero(fg); bx0,by0,bx1,by1=xs.min(),ys.min(),xs.max()+1,ys.max()+1
        room=Image.fromarray(np.dstack([cell,a*255]).astype(np.uint8)).crop((bx0,by0,bx1,by1))
        old=np.asarray(Image.open(f"{A}/{name}.webp").convert("RGBA"))[...,3]>128; old=biggest(old)
        oy,ox=np.nonzero(old); ox0,oy0,ox1,oy1=ox.min(),oy.min(),ox.max()+1,oy.max()+1
        # the new drawings have their own layout: centre each room on the canvas, as big as it fits
        W,H=1200,896; sc=min((W-8)/(bx1-bx0),(H-60)/(by1-by0)); room=room.resize((round((bx1-bx0)*sc),round((by1-by0)*sc)),Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.4,50,2))
        cv=Image.new("RGBA",(W,H),(0,0,0,0)); cv.paste(room,((W-room.width)//2,(H-60-room.height)//2+14),room)
        dr=ImageDraw.Draw(cv); t="@Abdulwahabdev"; tw=dr.textlength(t,font=FB); tx,ty=W-tw-18,H-34
        for dx,dy in ((1,1),(2,2)): dr.text((tx+dx,ty+dy),t,font=FB,fill=(0,0,0,150))
        dr.text((tx,ty),t,font=FB,fill=(255,255,255,235))
        cv.save(f"nc/{name}.webp",quality=90)
        g=Image.new("RGB",(W,H),(15,20,32)); g.paste(cv,(0,0),cv); gd=ImageDraw.Draw(g); f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",15)
        for p in range(0,101,5):
            X=W*p/100; Y=H*p/100; col=(255,0,0) if p%10==0 else (255,150,0)
            gd.line([(X,0),(X,H)],fill=col,width=1); gd.line([(0,Y),(W,Y)],fill=col,width=1)
            if p%10==0: gd.text((X+2,2),str(p),fill=(255,40,40),font=f); gd.text((2,Y+2),str(p),fill=(255,40,40),font=f)
        g.save(f"nc/grid-{name}.png")
        print(name,(bx1-bx0,by1-by0),(ox1-ox0,oy1-oy0), round((ox1-ox0)/(bx1-bx0),2), round((oy1-oy0)/(by1-by0),2))
