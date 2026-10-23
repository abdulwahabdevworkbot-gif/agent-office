import json, glob, os, shutil
from PIL import Image, ImageOps
from build import tag
REPO=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets")
L=[("Man in white ghutra and thobe","m"),("Man in red shemagh and thobe","m"),("Man in blue turban and grey thobe","m"),("Man in white imama and cream thobe","m"),
("Woman in black hijab and abaya","f"),("Woman in purple hijab and abaya","f"),("Woman in niqab and abaya","f"),("Woman in a navy suit","f"),
("Man in a suit and red tie","m"),("Man in a beige blazer","m"),("Man in a light blue sweater","m"),("Grey-haired man with glasses","m"),
("Woman in a head wrap and wax-print dress","f"),("Man in a navy shirt","m"),("Woman with braids in a kameez","f"),("Man in a black cap and hoodie","m"),
("Woman with a bun in a cream shirt","f"),("Woman in hijab, glasses and green jacket","f"),("Man in white ghutra and thobe (2)","m"),("Man in shemagh and thobe","m"),
("Man in shemagh, tossed end","m"),("Man in white ghutra, loose","m"),("Man in white ghutra, wrapped","m"),("Man in a beige patterned turban","m"),
("Man in a green patterned turban","m"),("Man in a white kuma cap","m"),("Man in a kuma cap and grey thobe","m"),("Man in shemagh and navy thobe","m"),
("Woman in black hijab and abaya (2)","f"),("Woman in niqab, plain","f"),("Woman in niqab, side-tied","f"),("Woman in niqab, layered","f"),
("Woman in long niqab","f"),("Woman in brown hijab","f"),("Woman in mauve hijab","f"),("Woman in beige hijab","f"),
("Woman in black hijab, wrapped","f"),("Woman with long hair, open abaya","f"),("Woman in navy open abaya","f"),("Woman in maroon kaftan","f"),("Woman in long niqab (2)","f")]
FEAT=[1,2,5,6,7,8,9,10,12,18]
def fit(im,W=216,H=600):
    s=min(H/im.height,(W-4)/im.width); im=im.resize((round(im.width*s),round(im.height*s)),Image.LANCZOS)
    c=Image.new("RGBA",(W,H),(0,0,0,0)); c.paste(im,((W-im.width)//2,H-im.height),im); return c
d=REPO+"/chars"; shutil.rmtree(d,ignore_errors=True); os.makedirs(d)
out=[]
for i in range(1,42):
    im=fit(Image.open("n41/raw%02d.png"%i)); im=tag(im)
    cid="c%02d"%i
    im.save(f"{d}/{cid}-l.webp",quality=88)
    # mirror keeps the credit readable: mirror the figure, then stamp the tag again on the mirror
    m=fit(ImageOps.mirror(Image.open("n41/raw%02d.png"%i))); tag(m).save(f"{d}/{cid}-r.webp",quality=88)
    out.append({"id":cid,"label_en":L[i-1][0],"for":L[i-1][1],"featured":i in FEAT})
json.dump(out,open(d+"/characters.json","w"),indent=1)
r=REPO+"/rooms"; shutil.rmtree(r,ignore_errors=True); os.makedirs(r)
for p in glob.glob("rc/*.webp"): shutil.copy(p,r)
print(len(out), sorted(os.listdir(r)))
