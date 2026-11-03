import cv2, numpy as np, sys
from scipy.spatial import cKDTree
rng=np.random.default_rng(3)
def bez(p0,p1,p2,p3,n=400):
    t=np.linspace(0,1,n)[:,None]; P=[np.array(p,float) for p in (p0,p1,p2,p3)]
    return ((1-t)**3)*P[0]+3*((1-t)**2)*t*P[1]+3*(1-t)*t*t*P[2]+t**3*P[3]
def render(img, curves, W=20):
    H,Wd=img.shape[:2]; out=img.astype(np.float32)/255
    shadow=np.zeros((H,Wd),np.float32)
    # fiber noise texture
    for pts in curves:
        seg=np.diff(pts,axis=0); L=np.r_[0,np.cumsum(np.hypot(seg[:,0],seg[:,1]))]
        tang=np.gradient(pts,axis=0); tang/=np.linalg.norm(tang,axis=1)[:,None]+1e-9
        nrm=np.stack([-tang[:,1],tang[:,0]],1)
        x0,y0=np.floor(pts.min(0)-W).astype(int); x1,y1=np.ceil(pts.max(0)+W).astype(int)
        x0,y0=max(x0,0),max(y0,0); x1,y1=min(x1,Wd),min(y1,H)
        yy,xx=np.mgrid[y0:y1,x0:x1]; q=np.stack([xx.ravel(),yy.ravel()],1).astype(float)
        tree=cKDTree(pts); d,i=tree.query(q)
        v=q-pts[i]; t=(v*nrm[i]).sum(1); s=L[i]
        half=W/2
        al=(v*tang[i]).sum(1)
        endcut=np.where(i==0,np.clip(1+al,0,1),1.0)*np.where(i==len(pts)-1,np.clip(1-al,0,1),1.0)
        m=np.clip(half+0.8-np.abs(t),0,1)*endcut
        # shadow footprint (offset down-right)
        sh=np.zeros((y1-y0,x1-x0),np.float32); sh.ravel()[:]=np.clip(half+4-np.abs(t),0,1)*endcut
        shadow[y0:y1,x0:x1]=np.maximum(shadow[y0:y1,x0:x1],sh)
        u=t/half
        cyl=np.sqrt(np.clip(1-u**2,0,1))
        phase=(s/(W*1.25)+u*0.6)
        strand=0.55+0.45*np.abs(np.sin(np.pi*phase))**0.45
        groove=0.72+0.28*np.clip(np.abs(np.sin(np.pi*phase))*4,0,1)
        fiber=0.85+0.3*np.sin((s*0.9+u*40)+rng.random(s.shape)*2)*0.5+rng.normal(0,0.06,s.shape)
        base=np.array([0.50,0.66,0.80])  # BGR jute
        lum=(0.55+0.5*cyl*strand)*groove*fiber
        hl=np.clip((cyl-0.75)*3,0,1)*strand*0.25
        col=np.clip(base*lum[:,None]+hl[:,None]*np.array([0.85,0.92,1.0]),0,1)
        reg=out[y0:y1,x0:x1].reshape(-1,3)
        mm=m[:,None]
        # depth ordering: draw over
        reg=reg*(1-mm)+col*mm
        out[y0:y1,x0:x1]=reg.reshape(y1-y0,x1-x0,3)
    # contact shadow under ropes (applied beneath: darken where shadow but not rope) 
    sb=cv2.GaussianBlur(shadow,(0,0),4); sb=np.roll(np.roll(sb,5,0),2,1)
    return out, sb
img=cv2.imread(sys.argv[1])
curves=[
 bez((394,890),(422,911),(446,947),(454,982)),
 bez((410,879),(438,900),(462,936),(470,971)),
 bez((426,868),(454,889),(478,925),(486,960)),
 bez((859,901),(856,935),(842,977),(823,1005)),
 bez((878,908),(875,942),(861,984),(842,1012)),
 bez((897,915),(894,949),(880,991),(861,1019)),
 bez((470,875),(590,910),(720,935),(858,905)),
 bez((868,1015),(880,1060),(850,1110),(872,1185)),
]
base=img.astype(np.float32)/255
out,sb=render(img,curves)
# apply shadow to base first then re-render ropes over shadowed base
shaded=base*(1-0.38*sb[...,None])
img2=(shaded*255).astype(np.uint8)
out,_=render(img2,curves)
soft=cv2.GaussianBlur(out,(0,0),0.8)
m2=(np.abs(out-shaded).sum(2)>0.01).astype(np.float32)
m2=cv2.GaussianBlur(m2,(0,0),1)[...,None]
out=out*(1-m2)+soft*m2
out=out+np.random.default_rng(1).normal(0,0.012,out.shape)*m2
cv2.imwrite(sys.argv[2],(np.clip(out,0,1)*255).astype(np.uint8),[cv2.IMWRITE_JPEG_QUALITY,95])
c=(np.clip(out,0,1)*255).astype(np.uint8)[780:1200,330:1000]; cv2.imwrite(sys.argv[2]+'.zoom.png',c)
