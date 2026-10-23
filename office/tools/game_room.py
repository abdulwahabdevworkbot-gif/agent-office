import sys
from PIL import Image, ImageDraw
S='/tmp/claude-0/-home-claude/45c3a0e2-d715-5f1c-bddb-beec708a9bc7/scratchpad/'
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
    # visible: top, face u=u1 (right-front), face v=v1 (left-front)
    poly(d,[P(u1,v0,h0),P(u1,v1,h0),P(u1,v1,h),P(u1,v0,h)],shade(c,.78))
    poly(d,[P(u0,v1,h0),P(u1,v1,h0),P(u1,v1,h),P(u0,v1,h)],shade(c,.62))
    poly(d,[P(u0,v0,h),P(u1,v0,h),P(u1,v1,h),P(u0,v1,h)],top or c)
def legs(d,u0,u1,v0,v1,h,c,t=.012):
    for (u,v) in [(u0+t,v0+t),(u1-t,v0+t),(u0+t,v1-t),(u1-t,v1-t)]:
        box(d,u-t,u+t*.6,v-t,v+t*.6,h,c)
def build(night):
    room=Image.open(S+'co/public/rooms/office-%s.png'%('night' if night else 'day')).convert('RGBA')
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(lay)
    # rug under lounge
    poly(d,[P(.62,.3),P(.97,.3),P(.97,.62),P(.62,.62)],(122,74,140,255),ol=False)
    poly(d,[P(.65,.33),P(.94,.33),P(.94,.59),P(.65,.59)],(150,96,170,255),ol=False)
    # arcade cabinets on window wall (u small)
    for v0,col,scr in [(.30,(200,52,72,255),(90,220,255,255)),(.47,(52,92,200,255),(140,255,140,255))]:
        box(d,.03,.11,v0,v0+.1,150,col,h0=0)
        # screen on face u=.11 (right-front face)
        poly(d,[P(.11,v0+.015,128),P(.11,v0+.085,128),P(.11,v0+.085,88),P(.11,v0+.015,88)],(18,22,30,255))
        poly(d,[P(.11,v0+.025,123),P(.11,v0+.075,123),P(.11,v0+.075,94),P(.11,v0+.025,94)],scr,ol=False)
        # control panel
        box(d,.11,.15,v0+.01,v0+.09,70,shade(col,1.1),top=(40,44,58,255))
        for k,bc in [(.03,(255,214,0,255)),(.05,(255,90,90,255)),(.07,(90,200,255,255))]:
            x,y=P(.13,v0+k,71); d.ellipse([x-6,y-4,x+6,y+4],fill=bc,outline=OUT,width=2)
        # marquee glow
        poly(d,[P(.11,v0+.01,150),P(.11,v0+.09,150),P(.11,v0+.09,136),P(.11,v0+.01,136)],(255,236,140,255))
    # ping-pong table
    legs(d,.33,.6,.42,.6,52,(60,60,70,255))
    box(d,.33,.6,.42,.6,58,(28,110,72,255),h0=52)
    for a,b in [((.465,.42),(.465,.6))]:
        d.line([P(*a,58),P(*b,58)],fill=(240,240,240,255),width=3)
    d.line([P(.33,.51,58),P(.6,.51,58)],fill=(240,240,240,255),width=3)
    poly(d,[P(.465,.41,58),P(.465,.61,58),P(.465,.61,74),P(.465,.41,74)],(235,235,235,200))
    x,y=P(.52,.47,90); d.ellipse([x-6,y-6,x+6,y+6],fill=(255,150,40,255),outline=OUT,width=2)
    # TV on counter + console
    box(d,.84,.9,.04,.18,112,(110,78,52,255))
    box(d,.86,.88,.03,.19,185,(25,27,35,255),h0=112)
    poly(d,[P(.88,.045,178),P(.88,.175,178),P(.88,.175,120),P(.88,.045,120)],(70,160,255,255),ol=False)
    poly(d,[P(.88,.06,160),P(.88,.11,160),P(.88,.11,133),P(.88,.06,133)],(255,210,80,255),ol=False)
    poly(d,[P(.88,.12,155),P(.88,.16,155),P(.88,.16,128),P(.88,.12,128)],(255,100,120,255),ol=False)
    # bean bags
    for (u,v,c) in [(.72,.38,(240,140,40,255)),(.88,.42,(60,170,160,255)),(.76,.54,(230,80,110,255))]:
        x,y=P(u,v,0); d.ellipse([x-48,y-58,x+48,y+12],fill=c,outline=OUT,width=3)
        d.ellipse([x-30,y-52,x+22,y-24],fill=shade(c,1.18),outline=None)
    # foosball front-left
    legs(d,.2,.34,.74,.84,40,(70,50,36,255))
    box(d,.2,.34,.74,.84,62,(150,98,60,255),top=(40,150,80,255),h0=40)
    for k in [.23,.26,.29,.32]:
        d.line([P(k,.72,66),P(k,.86,66)],fill=(200,200,210,255),width=4)
        for vv in [.77,.8]:
            x,y=P(k,vv,62); d.rectangle([x-4,y-14,x+4,y],fill=(220,60,60,255) if k in (.23,.29) else (60,90,220,255),outline=OUT)
    # sign on the back right wall
    room.alpha_composite(lay)
    return room
for n in (0,1):
    im=build(n)
    im.convert('RGB').resize((1200,896),Image.LANCZOS).save(S+'build/game-%s.webp'%('night' if n else 'day'),quality=82)
im=build(0); im.convert('RGB').resize((754,563)).save(S+'build/game-prev.jpg',quality=85)
