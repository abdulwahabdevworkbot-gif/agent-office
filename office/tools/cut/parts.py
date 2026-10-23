import json, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from clean import cut, src
idx=json.load(open("out/index.json"))
def splitn(key,box,n,full=False,hole=False):
    """merged group of n items: cut at the emptiest column near each even split"""
    im,fg,bg=src(key); x0,y0,x1,y1=box
    col=fg[y0:int(y0+(y1-y0)*0.9),x0:x1].sum(axis=0).astype(float)
    col=np.convolve(col,np.ones(5)/5,mode="same"); w=x1-x0; cuts=[0]
    for k in range(1,n):
        c=int(w*k/n); r=int(w/n*0.35); seg=col[c-r:c+r]; cuts.append(c-r+int(np.argmin(seg)))
    cuts.append(w)
    return [cut(key,(x0+a,y0,x0+b,y1),full=full,hole=hole,dil=0) for a,b in zip(cuts,cuts[1:])]
def split(key,box,full=False,hole=False):
    """merged group: split on empty columns"""
    im,fg,bg=src(key); x0,y0,x1,y1=box
    col=fg[y0:y1,x0:x1].sum(axis=0)
    # shadows join neighbours: ignore the bottom 8%
    col=fg[y0:int(y0+(y1-y0)*0.9),x0:x1].sum(axis=0)
    runs=[];inr=False
    for i,v in enumerate(col):
        if v>0 and not inr: s=i;inr=True
        if v==0 and inr: runs.append((s,i));inr=False
    if inr: runs.append((s,len(col)))
    runs=[r for r in runs if r[1]-r[0]>6]
    return [cut(key,(x0+a-1,y0,x0+b+1,y1),full=full,hole=hole,dil=0) for a,b in runs]
def main():
    G=[]  # (group, label, gender, image)
    def add(g,lab,sex,im): G.append((g,lab,sex,im))
    heads=["Bald","Receding","Short","Side part","Quiff","Messy","Curly","Short (dark skin)"]
    for i,l in enumerate(heads): add("Men · heads",l,"M",cut("B",idx["B%02d"%(11+i)]))
    for i,l in enumerate(["Short hair","Side part","Swept"]): add("Men · hair",l,"M",cut("P",idx["P%02d"%(2+i)]))
    beards=["Chin strap","Clean","Full","Moustache","Full beard","Moustache + chin","Short beard","Full short"]
    for i,l in enumerate(beards): add("Men · beards (faces)",l,"M",cut("B",idx["B%02d"%(19+i)]))
    for i,l in enumerate(["Moustache","Moustache + goatee","Beard","Full beard","Long beard"]): add("Men · beards",l,"M",cut("P",idx["P%02d"%(13+i)]))
    for i,l in enumerate(["Ghutra + agal","Ghutra tossed","Ghutra loose","Shemagh + agal","Shemagh short","Shemagh tossed"]): add("Men · head covers",l,"M",cut("H",idx["H%02d"%(1+i)],hole=True))
    gp=split("P",idx["P24"],hole=True); add("Men · head covers","Ghutra (small)","M",gp[0]); add("Men · head covers","Shemagh (small)","M",gp[-1])
    add("Men · head covers","White imama","M",cut("P",idx["P21"])); add("Men · head covers","Blue turban","M",cut("P",idx["P22"]))
    add("Men · head covers","Kuma cap","M",cut("H",idx["H13"])); add("Men · head covers","Agal","M",cut("H",idx["H14"]))
    for i,l in enumerate(["Rectangle","Round","Oval"]): add("Glasses",l,"",cut("P",idx["P%02d"%(18+i)]))
    for i,l in enumerate(["Rectangle grey","Rectangle black","Round black"]): add("Glasses",l,"",cut("B",idx["B%02d"%(27+i)]))
    for i,l in enumerate(["Niqab","Niqab wrapped","Niqab layered"]): add("Women · head covers",l,"F",cut("H",idx["H%02d"%(7+i)],hole=True))
    for i,l in enumerate(["Hijab black","Hijab purple","Hijab pink"]): add("Women · head covers",l,"F",cut("H",idx["H%02d"%(10+i)],hole=True))
    for i,l in enumerate(["Hijab black","Hijab purple","Niqab","Hijab pink"]): add("Women · head covers",l+" (2)","F",cut("P",idx["P%02d"%(25+i)],hole=True))
    wh=["Black hijab","Brown hijab","Mauve hijab","Beige hijab","Hijab (dark skin)","Niqab","Long straight"]
    for i,l in enumerate(wh): add("Women · heads",l,"F",cut("B",idx["B%02d"%(42+i)]))
    h2=splitn("B",idx["B49"],2); add("Women · heads","Bob","F",h2[0]); add("Women · heads","Wavy","F",h2[-1])
    add("Women · heads","Bun","F",cut("B",idx["B50"])); add("Women · heads","Braids","F",cut("B",idx["B51"]))
    for i,l in enumerate(["Long","Bun","Braids","Bob"]): add("Women · hair",l,"F",cut("P",idx["P%02d"%(9+i)]))
    for k,l in [("B52","Headband"),("B53","Black bow"),("B54","Beige bow"),("B55","Scrunchie"),("B57","Hair clip"),("B58","Pearl clip"),("P23","Pink headband")]: add("Women · hair accessories",l,"F",cut(k[0],idx[k]))
    for k,l in [("P32","Necklace"),("P33","Gold hoop"),("P35","Pearl drop"),("P37","Flower stud")]: add("Women · jewellery",l,"F",cut(k[0],idx[k]))
    for im,l in zip(splitn("B",idx["B59"],3),["Pearl earrings","Necklace (small)","Earrings"]): add("Women · jewellery",l,"F",im)
    for k,l in [("P30","Black handbag"),("P31","Beige shoulder bag")]: add("Women · bags",l,"F",cut(k[0],idx[k]))
    for im,l in zip(splitn("B",[idx["B56"][0],idx["B56"][1]+35,idx["B56"][2],idx["B56"][3]],2),["Black bag (small)","Maroon bag"]): add("Women · bags",l,"F",im)
    for im,l in zip(split("P",idx["P39"]),["Black flats","Beige flats","Navy flats"]): add("Women · shoes",l,"F",im)
    outs=splitn("P",idx["P29"],13,full=True)
    ol=["White thobe","Grey thobe","Grey thobe (2)","Black abaya","Open abaya","Beige thobe","Cream kurta","Women's suit","Men's suit","Hoodie","Suit + red tie","Wax-print dress","Green tunic"]
    for i,im in enumerate(outs): add("Outfits (no head)",ol[i] if i<len(ol) else "Outfit %d"%(i+1),"",im)
    for i,l in enumerate(["Base man, bald","Base man","Base woman, hijab","Base woman"]): add("Base bodies",l,"MMFF"[i],cut("P",idx["P%02d"%(5+i)],full=True))
    os.makedirs("parts",exist_ok=True)
    json.dump([(g,l,s) for g,l,s,_ in G],open("parts/list.json","w"))
    for i,(g,l,s,im) in enumerate(G): im.save("parts/%03d.png"%i)
    # sheet
    F=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",15); FB=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",22)
    cell=150; cols=12; W=cols*cell+20
    groups=[];[groups.append(g) for g,_,_,_ in G if g not in groups]
    H=20
    for g in groups:
        n=sum(1 for x in G if x[0]==g); big=g in("Outfits (no head)","Base bodies"); ch=300 if big else cell
        H+=40+((n+cols-1)//cols)*(ch+26)
    S=Image.new("RGB",(W,H),(244,241,234)); d=ImageDraw.Draw(S); y=20
    for g in groups:
        items=[x for x in G if x[0]==g]; big=g in("Outfits (no head)","Base bodies"); ch=300 if big else cell
        d.text((14,y),g,fill=(30,30,30),font=FB); y+=40
        for i,(_,l,s,im) in enumerate(items):
            t=im.copy(); t.thumbnail((cell-12,ch-8),Image.LANCZOS)
            x=10+(i%cols)*cell; yy=y+(i//cols)*(ch+26)
            S.paste(t,(x+(cell-t.width)//2,yy+(ch-t.height)//2),t)
            lab=l+(" (%s)"%s if s else ""); d.text((x+cell/2-d.textlength(lab,font=F)/2,yy+ch+3),lab,fill=(60,60,60),font=F)
        y+=((len(items)+cols-1)//cols)*(ch+26)
    S.save("parts-from-refs.webp",quality=88); print(len(G),len(outs),S.size)
if __name__=='__main__':
    main()
