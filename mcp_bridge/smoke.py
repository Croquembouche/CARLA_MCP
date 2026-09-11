"""Read-only live acceptance for both deployed HTTP and stdio transports."""
import asyncio
import json
from pathlib import Path
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from .catalog import TOOLS
from .server import ROOT, RESOURCES

async def check(read,write,previews=False):
    async with ClientSession(read,write) as client:
        init=await client.initialize()
        listed=await client.list_tools();assert {t.name for t in listed.tools}==set(TOOLS)
        resources=await client.list_resources();assert len(resources.resources)==len(RESOURCES)
        doc=await client.read_resource('carla://documentation');assert 'WebUI feature-to-MCP' in doc.contents[0].text
        status=await client.call_tool('carla_status',{});assert not status.isError,status
        state=status.structuredContent;assert state['phase']=='connected',state.get('phase')
        parking=await client.call_tool('carla_inspect',{'source':'map','fields':['parking_spaces'],'limit':3});assert not parking.isError
        latency=await client.call_tool('carla_latency',{});assert not latency.isError
        scene=await client.call_tool('carla_scene_manifest',{});assert not scene.isError
        invalid=await client.call_tool('carla_control',{'id':52,'throttle':2});assert invalid.isError
        result={'server':init.serverInfo.model_dump(),'tools':len(listed.tools),'resources':len(resources.resources),'frame':state['frame'],'running':state['running'],'map':state['map'],'parking_total':parking.structuredContent['total'],'latency':latency.structuredContent,'invalid_control_rejected':True,'previews':[]}
        if previews:
            for kind in ('sensor.camera.rgb','sensor.lidar.ray_cast','sensor.other.imu','sensor.other.gnss','sensor.other.radar'):
                sensor=next((s for s in state['sensors'] if s['type']==kind),None)
                if not sensor:continue
                args={'sensor_id':sensor['id']}
                if 'lidar' in kind:args.update(format='points',point_limit=512)
                p=await client.call_tool('carla_sensor_preview',args);assert not p.isError,p
                result['previews'].append({'sensor_id':sensor['id'],'kind':kind,'content_types':[x.type for x in p.content],'metadata':p.structuredContent})
        return result

async def main():
    report={}
    # systemd reports process start before uvicorn finishes binding its socket.
    # Readiness polling is bounded and read-only; tool writes are never retried.
    async with httpx.AsyncClient(timeout=2) as probe:
        for attempt in range(25):
            try:
                response=await probe.get('http://127.0.0.1:8096/health')
                if response.status_code==200:break
            except httpx.TransportError:pass
            await asyncio.sleep(.2)
        else:raise RuntimeError('MCP HTTP service did not become ready')
    async with streamable_http_client('http://127.0.0.1:8096/mcp') as (r,w,_):report['http']=await check(r,w,True)
    async with stdio_client(StdioServerParameters(command=str(ROOT/'run-mcp.sh'))) as (r,w):report['stdio']=await check(r,w)
    async with httpx.AsyncClient() as client:
        for origin,code in [('https://untrusted.example',403)]:
            response=await client.post('http://127.0.0.1:8096/mcp',headers={'Origin':origin},json={});assert response.status_code==code
    target=ROOT/'data/mcp-acceptance.json';target.write_text(json.dumps(report,indent=2))
    print(json.dumps({'evidence':str(target),'http':{k:v for k,v in report['http'].items() if k!='previews'},'preview_types':[p['kind'] for p in report['http']['previews']],'stdio':'passed'},indent=2))

if __name__=='__main__':asyncio.run(main())
