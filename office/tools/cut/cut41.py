import os, numpy as np
from PIL import Image
from parts import splitn
from build import tag
from tall import tall
rows=[((8,8,1114,344),11),((3,374,1118,728),11),((5,752,1118,1062),11),((8,1084,906,1372),8)]
os.makedirs("n41",exist_ok=True); n=0
for box,k in rows:
    for im in splitn("N",box,k,full=True):
        n+=1; im.save("n41/raw%02d.png"%n)
print(n)
