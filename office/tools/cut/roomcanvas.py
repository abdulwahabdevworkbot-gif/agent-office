import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
MAP={"boss":"manager","main-a":"office-a","main-b":"office-b","main-wide":"office-wide","meet-10":"meeting-10","meet-20":"meeting-20",
     "meet-30":"meeting-30","huddle":"huddle","game":"games","idle":"waiting","meet-8":"meeting-1"}
FB=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
os.makedirs("rc",exist_ok=True); OFF={}
for out,src in MAP.items():
    im=Image.open("rooms/%s.png"%src)
    W,H=(2400,896) if out=="main-wide" else (1200,896)
    s=min(W/im.width,H/im.height); im=im.resize((round(im.width*s),round(im.height*s)),Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.6,60,2))
    c=Image.new("RGBA",(W,H),(0,0,0,0)); x=(W-im.width)//2; y=(H-im.height)//2; c.paste(im,(x,y),im)
    # clear credit tag, bottom right on the dark margin
    d=ImageDraw.Draw(c); t="@Abdulwahabdev"; tw=d.textlength(t,font=FB)
    tx,ty=W-tw-18,H-34
    for dx,dy in ((1,1),(2,2)): d.text((tx+dx,ty+dy),t,font=FB,fill=(0,0,0,150))
    d.text((tx,ty),t,font=FB,fill=(255,255,255,235))
    c.save("rc/%s.webp"%out,quality=90); OFF[out]=(x,y,im.width,im.height)
    # grid copy for picking seats
    g=c.copy(); gd=ImageDraw.Draw(g); f=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",13)
    for p in range(0,101,5):
        X=W*p/100; Y=H*p/100; col=(255,0,0,160) if p%10==0 else (255,120,0,90)
        gd.line([(X,0),(X,H)],fill=col,width=1); gd.line([(0,Y),(W,Y)],fill=col,width=1)
        if p%10==0: gd.text((X+2,2),str(p),fill=(255,0,0),font=f); gd.text((2,Y+2),str(p),fill=(255,0,0),font=f)
    bg=Image.new("RGB",(W,H),(15,20,32)); bg.paste(g,(0,0),g); bg.save("rc/grid-%s.png"%out)
print(OFF)
