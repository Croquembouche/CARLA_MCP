import ast
import asyncio
import json
import unittest
from pathlib import Path
import httpx
import jsonschema
from mcp_bridge.catalog import TOOLS, SENSOR
from mcp_bridge.server import Bridge, MAX_FILE, ROOT, filename, http_app

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls=[]
        def handler(req):
            self.calls.append(req)
            if req.url.path=='/api/status':return httpx.Response(200,json={'phase':'connected','frame':42,'actors':[{'id':1},{'id':2}],'map':'Carla/Maps/Town10HD_Opt'})
            if req.url.path.startswith('/api/preview/'):
                if req.url.params.get('after')=='42':return httpx.Response(204,headers={'X-CARLA-Frame':'42'})
                return httpx.Response(200,content=b'\0'*9,headers={'content-type':'application/vnd.carla.pointcloud','X-CARLA-Frame':'42','X-Point-Scale':'.01','X-Point-Stride':'9','X-Preview-Points':'1'})
            return httpx.Response(200,json={'ok':True})
        self.bridge=Bridge(transport=httpx.MockTransport(handler))
    async def asyncTearDown(self):await self.bridge.close()
    async def test_forwarding_and_header(self):
        result=await self.bridge.execute('carla_destination',{'id':52,'point':{'x':8,'y':63,'parking_space':'P024'}})
        self.assertEqual(result,{'ok':True});req=self.calls[-1]
        self.assertEqual(req.url.path,'/api/command/destination');self.assertEqual(req.headers['X-Control-Client'],'carla-control-center')
        self.assertEqual(json.loads(req.content)['point']['parking_space'],'P024')
    async def test_invalid_no_write(self):
        for a in ({'id':52,'throttle':2},{'id':52,'brake':True},{'id':52,'unknown':1}):
            with self.assertRaises(jsonschema.ValidationError):await self.bridge.execute('carla_control',a)
        self.assertFalse(self.calls)
    async def test_sensor_constraints(self):
        for name in ('UPPER','space name','a'*41):
            with self.assertRaises(jsonschema.ValidationError):jsonschema.validate({'name':name,'type':'sensor.camera.rgb','mount':{},'attributes':{}},SENSOR)
    async def test_pagination(self):
        v=await self.bridge.execute('carla_inspect',{'source':'status','fields':['actors'],'offset':1,'limit':1})
        self.assertEqual(v['items'],[{'id':2}]);self.assertEqual(v['total'],2)
        with self.assertRaises(ValueError):await self.bridge.execute('carla_inspect',{'source':'status','fields':['typo']})
    async def test_point_metadata_and_unchanged(self):
        v=await self.bridge.execute('carla_sensor_preview',{'sensor_id':4,'format':'points'})
        self.assertEqual(v.structuredContent['x-point-scale'],'.01');self.assertEqual(v.structuredContent['x-preview-points'],'1')
        self.assertEqual(v.content[1].resource.blob,'AAAAAAAAAAAA')
        v=await self.bridge.execute('carla_sensor_preview',{'sensor_id':4,'after':42});self.assertFalse(v['available'])
    async def test_traversal_and_links(self):
        for f in ('../manifest.json','/etc/passwd','a/../../secret','a\\b','a//b','a/./b'):
            with self.assertRaises(ValueError):filename(f)
        self.assertEqual(filename('sensors/my scan.bin'),'sensors/my%20scan.bin')
        v=await self.bridge.execute('carla_download_links',{'kind':'session','session_id':'test','filename':'sensors/a.bin'})
        self.assertTrue(v['url'].endswith('/api/sessions/test/files/sensors/a.bin'));self.assertFalse(self.calls)
        with self.assertRaises(ValueError):await self.bridge.execute('carla_download_links',{'kind':'session'})
    async def test_upstream_error(self):
        await self.bridge.close();self.bridge=Bridge(transport=httpx.MockTransport(lambda r:httpx.Response(409,json={'detail':'Pause simulation before editing'})))
        with self.assertRaisesRegex(ValueError,'409.*Pause'):await self.bridge.execute('carla_delete_actor',{'id':1})
    async def test_timeout_no_retry(self):
        def handler(req):self.calls.append(req);raise httpx.ReadTimeout('timeout')
        await self.bridge.close();self.bridge=Bridge(transport=httpx.MockTransport(handler))
        with self.assertRaisesRegex(ValueError,'Outcome may be unknown'):await self.bridge.execute('carla_start',{})
        self.assertEqual(len(self.calls),1)
    async def test_response_bound(self):
        await self.bridge.close();self.bridge=Bridge(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*(MAX_FILE+1))))
        with self.assertRaisesRegex(ValueError,'exceeds'):await self.bridge.execute('carla_session_file',{'session_id':'test','filename':'huge.bin'})
    async def test_access(self):
        with self.assertRaises(ValueError):http_app(self.bridge,'0.0.0.0')
        app=http_app(self.bridge,token='test-secret')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:8096') as c:
            self.assertEqual((await c.get('/health')).status_code,401)
            self.assertEqual((await c.get('/health',headers={'Authorization':'Bearer test-secret'})).status_code,200)
            self.assertEqual((await c.post('/mcp',headers={'Origin':'https://bad.example','Authorization':'Bearer test-secret'})).status_code,403)
    async def test_no_implicit_run_or_pause(self):
        await self.bridge.execute('carla_weather',{'cloudiness':50})
        self.assertEqual([r.url.path for r in self.calls],['/api/command/weather'])

class CoverageTests(unittest.TestCase):
    def test_controller_actions_covered(self):
        tree=ast.parse((ROOT/'controller.py').read_text());controller=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Controller');method=next(n for n in controller.body if isinstance(n,ast.FunctionDef) and n.name=='command')
        actions=set()
        for node in ast.walk(method):
            if isinstance(node,ast.Compare) and isinstance(node.left,ast.Name) and node.left.id=='action':
                for part in node.comparators:
                    if isinstance(part,ast.Constant) and isinstance(part.value,str):actions.add(part.value)
                    if isinstance(part,(ast.Tuple,ast.List)):actions.update(x.value for x in part.elts if isinstance(x,ast.Constant))
        implemented={s['action'] for s in TOOLS.values()}|{'configuration'}
        self.assertEqual(actions-implemented,set())
    def test_schemas_examples_and_docs(self):
        guide=(ROOT/'docs/mcp.md').read_text()
        for name,s in TOOLS.items():
            jsonschema.Draft202012Validator.check_schema(s['schema'])
            if s['example']:jsonschema.validate(s['example'],s['schema'])
            self.assertIn(name,guide,name)
    def test_no_carla_import(self):
        text=(ROOT/'mcp_bridge/server.py').read_text()
        self.assertNotIn('import carla',text);self.assertNotIn('world.tick(',text)

if __name__=='__main__':unittest.main()
