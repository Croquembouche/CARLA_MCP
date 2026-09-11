import bootstrap
import asyncio
from contextlib import asynccontextmanager
import io
import json
import subprocess
import threading
import time
from verification import verify_session, compare_sessions
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from controller import Controller, ROOT, DATA
from recording import read_frame
from archive import archive_stream

engine=None

@asynccontextmanager
async def lifespan(app):
    global engine
    engine=Controller()
    yield
    await asyncio.to_thread(engine.close)

app=FastAPI(title='CARLA Control Center',version='1.0.0',lifespan=lifespan)

@app.middleware('http')
async def local_controls(request:Request,call_next):
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('origin')
        if origin and urlsplit(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'detail':'Cross-origin controls are disabled'},403)
        if request.headers.get('x-control-client')!='carla-control-center':
            return JSONResponse({'detail':'Control requests require X-Control-Client: carla-control-center'},403)
        if int(request.headers.get('content-length','0'))>1024*1024:
            return JSONResponse({'detail':'Configuration request is too large'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self' blob:; worker-src 'self' blob:; frame-ancestors 'self'"
    return response

@app.get('/api/status')
def status():return engine.state

@app.get('/api/catalog')
def catalog():return engine.catalog

@app.get('/api/map')
def map_data():
    if engine.map_data:return engine.map_data
    cache=DATA/'map-cache.json'
    if cache.exists():return json.loads(cache.read_text())
    return {'name':None,'lanes':[],'spawn_points':[],'buildings':[],'bounds':[-100,-100,100,100]}

@app.get('/api/map.xodr')
def xodr():
    path=DATA/'map-cache.xodr'
    if not path.exists():raise HTTPException(404,'Connect to a scene first')
    return FileResponse(path,media_type='application/xml',filename='scene.xodr')

@app.post('/api/command/{action}',openapi_extra={'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object'},'example':{'id':25,'throttle':0.3,'steer':0.0,'brake':0.0}}}}})
async def command(action:str,request:Request):
    try:
        payload=await request.json()
        if not isinstance(payload,dict):raise ValueError('Expected a JSON object')
        return await asyncio.shield(asyncio.wrap_future(engine.submit(action,payload)))
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
    except RuntimeError as e:raise HTTPException(409,str(e))

@app.get('/api/configuration')
async def configuration():
    try:return await asyncio.wrap_future(engine.submit('configuration',{}))
    except Exception as e:raise HTTPException(409,str(e))

@app.get('/api/preview/{sensor_id}')
def preview(sensor_id:int):
    item=engine.previews.get(sensor_id)
    if not item:raise HTTPException(404,'No captured image yet')
    return Response(item[1],media_type='image/jpeg',headers={'Cache-Control':'no-store','X-CARLA-Frame':str(item[0])})

@app.get('/api/sessions')
def sessions():
    items=[]
    for p in sorted((DATA/'recordings').glob('*/manifest.json'),reverse=True):
        try:
            m=json.loads(p.read_text())
            if m['status']=='recording':
                m['frames']=(p.parent/'frames.idx').stat().st_size//8
                if not engine.recording or engine.recording.path!=p.parent:m['status']='interrupted'
            items.append(m)
        except (OSError,ValueError):pass
    return items

@app.get('/api/sessions/{sid}/frame/{index}')
def frame(sid:str,index:int):
    if index<0:raise HTTPException(400,'Negative frame index')
    try:return read_frame(engine.session(sid),index)
    except ValueError as e:raise HTTPException(404,str(e))

@app.get('/api/sessions/{sid}/preview/{index}')
def recorded_preview(sid:str,index:int):
    try:
        path=engine.session(sid);f=read_frame(path,index)
        item=next(x for x in f['sensor_files'] if x['type']=='sensor.camera.rgb')
        im=Image.frombytes('RGBA',(item['width'],item['height']),(path/item['path']).read_bytes(),'raw','BGRA').convert('RGB')
        im.thumbnail((640,360));b=io.BytesIO();im.save(b,format='JPEG',quality=85)
        return Response(b.getvalue(),media_type='image/jpeg')
    except (ValueError,StopIteration) as e:raise HTTPException(404,'No recorded RGB image at this index')

@app.get('/api/sessions/{sid}/archive')
def session_archive(sid:str):
    try:path=engine.session(sid)
    except ValueError as e:raise HTTPException(404,str(e))
    if engine.recording and engine.recording.path==path:raise HTTPException(409,'Stop recording before downloading the session')
    return StreamingResponse(archive_stream(path),media_type='application/x-tar',headers={'Content-Disposition':f'attachment; filename="{sid}.tar"'})

@app.get('/api/sessions/{sid}/files')
def session_files(sid:str):
    try:path=engine.session(sid)
    except ValueError as e:raise HTTPException(404,str(e))
    return [{'path':str(p.relative_to(path)),'bytes':p.stat().st_size} for p in path.rglob('*') if p.is_file()]

@app.get('/api/sessions/{sid}/files/{filename:path}')
def session_file(sid:str,filename:str):
    try:root=engine.session(sid).resolve()
    except ValueError as e:raise HTTPException(404,str(e))
    path=(root/filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise HTTPException(404,'File not found')
    return FileResponse(path,filename=path.name)

@app.post('/api/sessions/{sid}/verify')
async def verify(sid:str):
    try:path=engine.session(sid)
    except ValueError as e:raise HTTPException(404,str(e))
    if engine.recording and engine.recording.path==path:raise HTTPException(409,'Stop recording before verification')
    return await asyncio.to_thread(verify_session,path)

@app.post('/api/compare')
async def compare(request:Request):
    p=await request.json()
    try:
        a,b=engine.session(p['reference']),engine.session(p['candidate'])
        if engine.recording and engine.recording.path in (a,b):raise ValueError('Stop recording before comparison')
        return await asyncio.to_thread(compare_sessions,a,b)
    except (ValueError,KeyError) as e:raise HTTPException(400,str(e))

@app.post('/api/recover')
async def recover():
    if not engine.proc or engine.state.get('phase')!='error':raise HTTPException(409,'Recovery is available for a failed owned simulator')
    path=DATA/'recovery-checkpoint.json'
    if not path.exists():raise HTTPException(409,'No saved recovery configuration is available')
    config=json.loads(path.read_text())['configuration']
    from recording import dump
    dump(DATA/'restart-live-request.json',{'gpus':'auto','created':time.time(),'configuration':config})
    engine.running=False;engine.state.update(phase='restarting',running=False,recovery_operation={'stage':'restarting','detail':'Restarting from the saved configuration'})
    threading.Timer(.5,lambda:subprocess.Popen(['systemctl','--user','--no-block','restart','carla-control-center.service'])).start()
    return {'restarting':True,'note':'Restores saved configuration, not an exact mid-frame physics checkpoint'}

@app.get('/api/log')
def log():
    path=DATA/'simulator.log'
    if not path.exists():return {'log':''}
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-6000));text=f.read().decode(errors='replace')
    return {'log':text}

app.mount('/vendor/three',StaticFiles(directory=ROOT/'node_modules/three'),name='vendor')
app.mount('/design',StaticFiles(directory=ROOT/'design',html=True),name='design')
app.mount('/',StaticFiles(directory=ROOT/'static',html=True),name='static')
