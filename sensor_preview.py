"""Demand-only, bounded sensor visualization. Never modifies recorded CARLA data."""
import io,json,threading
from collections import OrderedDict
import numpy as np
from PIL import Image,ImageDraw

# Distinct semantic-class colours; these previews are visualizations, not raw labels.
PALETTE=np.array([[0,0,0],[128,64,128],[244,35,232],[70,70,70],[102,102,156],[190,153,153],[153,153,153],[250,170,30],[220,220,0],[107,142,35],[152,251,152],[70,130,180],[220,20,60],[255,0,0],[0,0,142],[0,0,70],[0,60,100],[0,80,100],[0,0,230],[119,11,32],[110,190,160],[170,120,50],[55,90,80],[45,60,150],[157,234,50],[81,0,81],[150,100,100],[230,150,140],[180,165,180]],dtype=np.uint8)

def encode_points(kind,data,limit=4000):
    if not kind.startswith('sensor.lidar.'):raise ValueError('Point previews require a LiDAR sensor')
    limit=max(512,min(12000,int(limit)))
    if kind.endswith('ray_cast_semantic'):
        raw=np.frombuffer(data.raw_data,dtype=np.dtype([('xyz','<f4',(3,)),('cos','<f4'),('id','<u4'),('tag','<u4')]))
        xyz=raw['xyz'];tags=raw['tag']
    else:
        raw=np.frombuffer(data.raw_data,dtype='<f4').reshape(-1,4);xyz=raw[:,:3];tags=None
    total=len(xyz);step=max(1,int(np.ceil(total/limit)));xyz=xyz[::step]
    valid=np.isfinite(xyz).all(axis=1);xyz=xyz[valid]
    scale=max(.01,float(np.max(np.abs(xyz)))/32760 if len(xyz) else .01)
    if tags is not None:colours=PALETTE[tags[::step][valid]%len(PALETTE)]
    else:
        t=np.clip((xyz[:,2]+2)/6,0,1);colours=np.column_stack((60+180*t,220-100*t,240-160*t)).astype(np.uint8)
    packed=np.empty(len(xyz),dtype=np.dtype([('xyz','<i2',(3,)),('rgb','u1',(3,))]))
    packed['xyz']=np.rint(xyz/scale).astype('<i2');packed['rgb']=colours
    return packed.tobytes(),'application/vnd.carla.pointcloud',{'X-Preview-Points':str(len(xyz)),'X-Preview-Source-Points':str(total),'X-Point-Scale':str(scale),'X-Point-Stride':'9'}

def encode_preview(kind,data,width=640,format="image",point_limit=4000):
    if format=="points":return encode_points(kind,data,point_limit)
    width=max(160,min(960,int(width)));headers={}
    if kind in ('sensor.other.imu','sensor.other.gnss'):
        if kind.endswith('imu'):
            values={name:{axis:float(getattr(getattr(data,name),axis)) for axis in 'xyz'} for name in ('accelerometer','gyroscope')}
            values['compass']=float(data.compass);units={'accelerometer':'m/s²','gyroscope':'rad/s','compass':'rad'}
        else:values={name:float(getattr(data,name)) for name in ('latitude','longitude','altitude')};units={'latitude':'°','longitude':'°','altitude':'m'}
        return json.dumps({'values':values,'units':units},allow_nan=False).encode(),'application/json',headers
    if kind.startswith('sensor.camera.'):
        if kind.endswith('optical_flow'):
            flow=np.frombuffer(data.raw_data,dtype='<f4').reshape(data.height,data.width,2)
            angle=(np.arctan2(flow[:,:,1],flow[:,:,0])+np.pi)/(2*np.pi)
            hsv=np.stack((angle*255,np.full_like(angle,255),np.minimum(np.linalg.norm(flow,axis=2)*80,255)),axis=-1)
            im=Image.fromarray(np.nan_to_num(hsv).astype(np.uint8),'HSV').convert('RGB')
        else:
            raw=np.frombuffer(data.raw_data,dtype=np.uint8).reshape(data.height,data.width,4)
            if kind.endswith('depth'):
                depth=(raw[:,:,2].astype(np.float32)+256*raw[:,:,1].astype(np.float32)+65536*raw[:,:,0].astype(np.float32))/16777215*1000
                gray=np.clip(np.log1p(depth)/np.log(1001)*255,0,255).astype(np.uint8);im=Image.fromarray(gray).convert('RGB')
            elif kind.endswith('semantic_segmentation'):im=Image.fromarray(PALETTE[raw[:,:,2]%len(PALETTE)])
            elif kind.endswith('instance_segmentation'):
                ids=raw[:,:,1].astype(np.uint32)*256+raw[:,:,0];rgb=np.stack(((ids*53)%256,(ids*97)%256,(ids*193)%256),axis=-1).astype(np.uint8);rgb[ids==0]=PALETTE[raw[:,:,2][ids==0]%len(PALETTE)];im=Image.fromarray(rgb)
            else:im=Image.fromarray(raw[:,:,[2,1,0]])
        im.thumbnail((width,width));headers['X-Preview-Source-Size']=f'{data.width}x{data.height}'
    elif kind.startswith('sensor.lidar.') or kind=='sensor.other.radar':
        if kind=='sensor.other.radar':
            raw=np.frombuffer(data.raw_data,dtype='<f4').reshape(-1,4) # velocity, azimuth, altitude, depth
            xyz=np.column_stack((raw[:,3]*np.cos(raw[:,2])*np.cos(raw[:,1]),raw[:,3]*np.cos(raw[:,2])*np.sin(raw[:,1]),raw[:,3]*np.sin(raw[:,2])))
            colour=raw[:,0];legend='Red: approaching / blue: receding'
        elif kind.endswith('ray_cast_semantic'):
            raw=np.frombuffer(data.raw_data,dtype=np.dtype([('xyz','<f4',(3,)),('cos','<f4'),('id','<u4'),('tag','<u4')]))
            xyz=raw['xyz'];colour=raw['tag'];legend='Colour: semantic class'
        else:
            raw=np.frombuffer(data.raw_data,dtype='<f4').reshape(-1,4);xyz=raw[:,:3];colour=raw[:,2];legend='Colour: height'
        total=len(xyz);step=max(1,int(np.ceil(total/12000)));xyz=xyz[::step];colour=colour[::step]
        valid=np.isfinite(xyz).all(axis=1)&np.isfinite(colour);xyz=xyz[valid];colour=colour[valid]
        # A fixed 80-metre radius makes scans stable between frames.
        span=80.;size=width;im=Image.new('RGB',(size,size),(10,19,27));draw=ImageDraw.Draw(im);centre=size/2;scale=(size-36)/(span*2)
        for radius in (20,40,60,80):
            r=radius*scale;draw.ellipse((centre-r,centre-r,centre+r,centre+r),outline=(35,52,65));draw.text((centre+3,centre-r),str(radius)+' m',fill=(105,127,145))
        px=np.rint(centre+xyz[:,1]*scale).astype(int);py=np.rint(centre-xyz[:,0]*scale).astype(int);inside=(px>=0)&(px<size)&(py>=0)&(py<size)
        if kind.endswith('ray_cast_semantic'):colours=PALETTE[colour.astype(int)%len(PALETTE)]
        elif kind=='sensor.other.radar':colours=np.where((colour<0)[:,None],np.array([250,112,96]),np.array([85,180,255]))
        else:
            t=np.clip((colour+2)/6,0,1);colours=np.column_stack((60+180*t,220-100*t,240-160*t)).astype(np.uint8)
        pixels=np.array(im);pixels[py[inside],px[inside]]=colours[inside];im=Image.fromarray(pixels);draw=ImageDraw.Draw(im)
        if kind=='sensor.other.radar':
            for x,y,c in zip(px[inside],py[inside],colours[inside]):draw.ellipse((x-2,y-2,x+2,y+2),fill=tuple(c))
        draw.polygon([(centre,centre-6),(centre-4,centre+4),(centre+4,centre+4)],fill=(255,255,255));draw.text((9,7),'SENSOR TOP VIEW | +X forward',fill=(190,211,220));draw.text((9,size-18),legend,fill=(190,211,220))
        headers.update({'X-Preview-Points':str(len(xyz)),'X-Preview-Source-Points':str(total)})
    else:raise ValueError('Preview not supported for '+kind)
    out=io.BytesIO();im.save(out,format='JPEG',quality=72);return out.getvalue(),'image/jpeg',headers

class PreviewCache:
    def __init__(self):self.lock=threading.Lock();self.items=OrderedDict();self.bytes=0;self.encodes=0
    def get(self,key,kind,data,width,**options):
        # Serialize bounded encodes so simultaneous requests cannot duplicate work.
        with self.lock:
            if key in self.items:self.items.move_to_end(key);return self.items[key]
            value=encode_preview(kind,data,width,**options);self.encodes+=1;self.items[key]=value;self.bytes+=len(value[0])
            while len(self.items)>32 or self.bytes>8*1024*1024:
                _,old=self.items.popitem(last=False);self.bytes-=len(old[0])
            return value
