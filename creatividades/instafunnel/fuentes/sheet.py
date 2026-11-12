import sys,json
from PIL import Image
L=json.load(open(sys.argv[1]));import re
r=re.compile(sys.argv[2]) if len(sys.argv)>2 else None
ims=[]
for n,s in L:
    if r and not r.search(n): continue
    im=Image.open(f'png/{n}.png').convert('RGB'); h=int(im.size[1]*300/1080); ims.append(im.resize((300,h)))
cols=6; H=max(i.size[1] for i in ims); rows=(len(ims)+cols-1)//cols
W=Image.new('RGB',(cols*305,rows*(H+5)),'white')
for k,im in enumerate(ims): W.paste(im,((k%cols)*305,(k//cols)*(H+5)))
W.save(sys.argv[3] if len(sys.argv)>3 else 'sheet.png')
