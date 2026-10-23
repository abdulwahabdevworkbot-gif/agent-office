# Meeting room background, conference table, meeting chairs and desk chairs.
# Same iso mapping as game.py. Prints JSON layout (percent of the room) for the page.
import json
from PIL import Image, ImageDraw
import os
S=os.environ.get('OFFICE_BUILD', './')
O=S+'build/meet/'
W,H=1508,1126
B=(50,40);R=(88,65);F=(54,94);L=(4,63)
def P(u,v,h=0):
    x=(1-u)*(1-v)*B[0]+u*(1-v)*R[0]+u*v*F[0]+(1-u)*v*L[0]
    y=(1-u)*(1-v)*B[1]+u*(1-v)*R[1]+u*v*F[1]+(1-u)*v*L[1]
    return (x*W/100, y*H/100-h)
OUT=(34,38,52,255)
def shade(c,f): return tuple(max(0,min(255,int(x*f))) for x in c[:3])+(255,)
def poly(d,pts,c,ol=True): d.polygon(pts,fill=c,outline=OUT if ol else None,width=3 if ol else 0)
def box(d,u0,u1,v0,v1,h,c,top=None,h0=0):
    poly(d,[P(u1,v0,h0),P(u1,v1,h0),P(u1,v1,h),P(u1,v0,h)],shade(c,.78))
    poly(d,[P(u0,v1,h0),P(u1,v1,h0),P(u1,v1,h),P(u0,v1,h)],shade(c,.62))
    poly(d,[P(u0,v0,h),P(u1,v0,h),P(u1,v1,h),P(u0,v1,h)],top or c)
def layer(): 
    im=Image.new('RGBA',(W,H),(0,0,0,0)); return im,ImageDraw.Draw(im)
def crop_save(im,name,anchor=None):
    bb=im.getbbox(); c=im.crop(bb)
    sc=1200/W; c=c.resize((max(1,round(c.width*sc)),max(1,round(c.height*sc))),Image.LANCZOS)
    c.save(O+name+'.webp',quality=88)
    r={'x':round(bb[0]/W*100,2),'y':round(bb[1]/H*100,2),'w':round((bb[2]-bb[0])/W*100,2)}
    if anchor:
        ax,ay=anchor; r['ax']=round((ax-bb[0])/(bb[2]-bb[0]),3); r['ay']=round((ay-bb[1])/(bb[3]-bb[1]),3)
    return r
SEAT=38; CH=(58,64,82,255); CUSH=(92,104,140,255)
FACE={'front-left':(0,1),'front-right':(1,0),'rear-left':(-1,0),'rear-right':(0,-1)}
def chair(d,uc,vc,facing,s=.03):
    du,dv=FACE[facing]
    # star base + lift
    for a,b in [(1,0),(-1,0),(0,1),(0,-1)]:
        x,y=P(uc+a*s*1.1,vc+b*s*1.1,4); d.ellipse([x-5,y-4,x+5,y+4],fill=(30,32,40,255))
        d.line([P(uc,vc,8),P(uc+a*s*1.1,vc+b*s*1.1,6)],fill=(40,42,52,255),width=5)
    d.line([P(uc,vc,8),P(uc,vc,SEAT-6)],fill=(70,72,84,255),width=7)
    def back():
        bu,bv=uc-du*s,vc-dv*s
        if du: box(d,bu-.006,bu+.006,vc-s,vc+s,SEAT+58,CH,top=CUSH,h0=SEAT+6)
        else:  box(d,uc-s,uc+s,bv-.006,bv+.006,SEAT+58,CH,top=CUSH,h0=SEAT+6)
    behind = (du<0 or dv<0)  # backrest toward the viewer when the sitter faces the rear
    if not behind: back()
    box(d,uc-s,uc+s,vc-s,vc+s,SEAT,CH,top=CUSH,h0=SEAT-8)
    if behind: back()
def build_bg(night):
    room=Image.open(S+'co/public/rooms/office-%s.png'%('night' if night else 'day')).convert('RGBA')
    lay,d=layer()
    # rug under the table
    poly(d,[P(.14,.24),P(.90,.24),P(.90,.76),P(.14,.76)],(64,92,120,255),ol=False)
    poly(d,[P(.17,.27),P(.87,.27),P(.87,.73),P(.17,.73)],(84,118,150,255),ol=False)
    # wall screen on the back-right wall
    poly(d,[P(.40,.012,215),P(.66,.012,215),P(.66,.012,120),P(.40,.012,120)],(22,24,32,255))
    poly(d,[P(.415,.012,207),P(.645,.012,207),P(.645,.012,128),P(.415,.012,128)],(40,120,220,255) if not night else (30,90,190,255),ol=False)
    for k,(c,hh) in enumerate([((120,220,160,255),40),((255,210,90,255),58),((255,120,140,255),30),((150,190,255,255),48)]):
        u=.44+k*.05; poly(d,[P(u,.012,140),P(u+.03,.012,140),P(u+.03,.012,140+hh),P(u,.012,140+hh)],c,ol=False)
    room.alpha_composite(lay); return room
for n in (0,1):
    build_bg(n).convert('RGB').resize((1200,896),Image.LANCZOS).save(O+'meet-%s.webp'%('night' if n else 'day'),quality=82)
lay_out={}
# table
im,d=layer()
for (u,v) in [(.30,.42),(.74,.42),(.30,.58),(.74,.58)]: box(d,u-.01,u+.01,v-.01,v+.01,60,(60,50,44,255))
box(d,.28,.76,.40,.60,68,(150,104,66,255),top=(178,130,86,255),h0=58)
for (u,v) in [(.38,.47),(.52,.53),(.66,.47)]:
    x,y=P(u,v,67); d.ellipse([x-9,y-5,x+9,y+5],fill=(240,240,245,255),outline=OUT,width=2)
lay_out['table']=crop_save(im,'table'); lay_out['table']['z']=500
seats=[]
SP=[(.36,.33,'front-left',300),(.52,.33,'front-left',310),(.68,.33,'front-left',320),
    (.21,.50,'front-right',400),
    (.36,.67,'rear-right',700),(.52,.67,'rear-right',710),(.68,.67,'rear-right',720),
    (.83,.50,'rear-left',650)]
for i,(u,v,f,z) in enumerate(SP):
    im,d=layer(); chair(d,u,v,f)
    r=crop_save(im,'mchair-%d'%i); front=f.startswith('rear')
    r['z']=z-5; lay_out['mchair-%d'%i]=r  # the sitter's torso hides the backrest, from either side
    x,y=P(u,v,SEAT)
    seats.append({'x':round(x/W*100,2),'y':round(y/H*100,2),'f':f,'z':z})
lay_out['seats']=seats
# standing spots around the table for overflow
stand=[]
for (u,v,f) in [(.12,.36,'front-right'),(.92,.64,'rear-left'),(.14,.68,'front-right'),(.92,.34,'rear-left'),(.44,.84,'rear-right'),(.62,.86,'rear-right')]:
    x,y=P(u,v); stand.append({'x':round(x/W*100,2),'y':round(y/H*100,2),'f':f,'z':round(y/H*1000)})
lay_out['stand']=stand
x,y=P(.12,.86); lay_out['door']={'x':round(x/W*100,2),'y':round(y/H*100,2)}
# desk chairs, one per facing, anchored at the floor under the seat
for f in FACE:
    im,d=layer(); chair(d,.5,.5,f); ax,ay=P(.5,.5,SEAT)
    lay_out['chair-'+f]=crop_save(im,'chair-'+f,anchor=(ax,ay))
print(json.dumps(lay_out))
