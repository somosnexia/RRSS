import cv2, numpy as np, math
img=cv2.imread('../images/1.jpg').astype(np.float32)/255
cx,cy,r=706.3,459.8,10.3
S=8; pad=40
x0,y0=int(cx-pad),int(cy-pad); x1,y1=int(cx+pad),int(cy+pad)
patch=img[y0:y1,x0:x1].copy(); H,W=patch.shape[:2]
big=cv2.resize(patch,(W*S,H*S),interpolation=cv2.INTER_CUBIC)
pcx,pcy,pr=(cx-x0)*S,(cy-y0)*S,r*S
yy,xx=np.mgrid[0:H*S,0:W*S].astype(np.float32)
d=np.sqrt((xx-pcx)**2+(yy-pcy)**2); ang=np.arctan2(yy-pcy,xx-pcx); t=d/pr
# eyelid: soft occlusion of the top ~10% of iris
lid=np.clip((yy-(pcy-pr*0.86))/(pr*0.12),0,1)
inside=np.clip((pr*0.97-d)/(0.7*S),0,1)*lid
lum=cv2.cvtColor(big,cv2.COLOR_BGR2GRAY)
# tint original iris texture to electric blue keeping detail
blue=np.array([0.886,0.294,0.180]); cyan=np.array([1.0,0.80,0.50])
L=np.clip((lum-0.05)/0.45,0,1)[...,None]
tinted=np.clip(blue*(0.45+0.6*L)+(cyan*0.12)*L,0,1)
layer=tinted.copy()
def ring(rr,wid,col,a):
    global layer
    m=(np.exp(-((t-rr)/wid)**2)*a)[...,None]; layer=layer*(1-m)+col*m
ring(0.97,0.03,cyan,0.85)       # limbal light ring
ring(0.70,0.012,cyan,0.55)      # inner thin ring
ticks=((np.abs(np.sin(ang*30))<0.10)&(t>0.78)&(t<0.93)).astype(np.float32)[...,None]*0.85
layer=layer*(1-ticks)+cyan*ticks
sweep=(np.clip(1-((ang+2.0)%(2*math.pi))/1.0,0,1)*(t>0.38)*(t<0.95)*0.30)[...,None]
layer=layer*(1-sweep)+cyan*sweep
cr=((((np.abs(xx-pcx)<0.35*S)|(np.abs(yy-pcy)<0.35*S))&(t>0.40)&(t<0.75)).astype(np.float32)*0.45)[...,None]
layer=layer*(1-cr)+cyan*cr
gap=((np.abs(np.sin(ang*2))<0.12)&(t>0.9)).astype(np.float32)[...,None]*0.7
layer=layer*(1-gap)+np.array([0.15,0.06,0.03])*gap
pup=(t<0.30).astype(np.float32)[...,None]; layer=layer*(1-pup)+np.array([0.10,0.04,0.02])*pup
ring(0.31,0.025,cyan,0.9)       # glowing pupil edge
out=big*(1-inside[...,None])+layer*inside[...,None]
spec=(np.exp(-(((xx-(pcx+0.22*pr))**2+(yy-(pcy-0.30*pr))**2)/(2*(0.11*pr)**2)))*0.95)[...,None]
out=out*(1-spec)+np.array([1.0,0.97,0.93])*spec
glow=(np.exp(-((t-1.08)/0.30)**2)*(t>0.98)*lid*0.10)[...,None]
out=np.clip(out+blue*glow,0,1)
out=np.clip(out,0,1)
img[y0:y1,x0:x1]=np.clip(cv2.resize(out,(W,H),interpolation=cv2.INTER_AREA),0,1)
cv2.imwrite('work/bionic_full.jpg',(img*255).astype(np.uint8),[cv2.IMWRITE_JPEG_QUALITY,95])
z=img[int(cy-28):int(cy+28),int(cx-45):int(cx+45)]
cv2.imwrite('work/bionic_zoom.png',(cv2.resize(z,None,fx=6,fy=6,interpolation=cv2.INTER_CUBIC).clip(0,1)*255).astype(np.uint8))
